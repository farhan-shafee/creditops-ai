"""Evidence-first orchestration with actual local MCP and offline SDK responses.

Every provider response in this module is a scripted/MockTransport fixture.
No real credential, provider HTTP transport, usage, billing or live receipt is
used. API/MCP children own only a temporary synthetic SQLite and loopback port.
"""

import copy
import json
from collections import Counter
from uuid import uuid4

import httpx
import pytest
from creditops import investigator
from creditops.db import EvidenceRow
from creditops.diagnostic_clients import MAX_RESULT_BYTES, DiagnosticClientError
from creditops.diagnostics import build_assessment
from creditops.providers import AdaptiveDecision, DeterministicProvider, OpenAIProvider
from creditops.settings import PROJECT_ROOT, Settings
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaError
from sqlalchemy import func, select
from test_strict_runner_mcp import (
    ScriptedRunnerActions,
    owned_runner_path,
    process_is_running,
    runner,
)
from test_strict_runner_mcp import (
    isolated_failure_api as isolated_failure_api_fixture,
)

isolated_failure_api = isolated_failure_api_fixture
INITIAL_TOOLS = ["get_incident", "get_service_topology", "query_metrics", "search_logs"]
FROZEN_CUTOFF = "2026-10-09T15:00:00Z"


async def mock_sdk_provider(monkeypatch, resources):
    """Capture installed official SDK requests after real MCP results, offline."""
    from openai import AsyncOpenAI

    for key, value in {
        "OPENAI_API_KEY": "offline-evidence-first-fixture-key",
        "OPENAI_MODEL": "gpt-5.4-mini-2026-03-17",
        "OPENAI_INPUT_USD_PER_MILLION": "0.75",
        "OPENAI_OUTPUT_USD_PER_MILLION": "4.50",
    }.items():
        monkeypatch.setenv(key, value)
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if payload["text"]["format"]["name"] == "Assessment":
            # An explicit scripted abstention, with no expected answer supplied.
            output = build_assessment({}, [])[0].model_dump(mode="json")
        else:
            # At the first provider boundary all initial tools must have finished.
            _, _, _, diagnostic_path, _ = resources
            dispatched = [json.loads(line) for line in diagnostic_path.read_text().splitlines()]
            assert [item["path"].rsplit("/", 1)[-1] for item in dispatched] == INITIAL_TOOLS
            output = {"action": "assess", "request": None}
        return httpx.Response(
            200,
            json={
                "id": "resp_offline_evidence_first_fixture",
                "object": "response",
                "created_at": 1,
                "status": "completed",
                "model": "gpt-5.4-mini-2026-03-17",
                "output": [{
                    "id": "msg_offline_evidence_first_fixture",
                    "type": "message",
                    "status": "completed",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": json.dumps(output), "annotations": []}],
                }],
                # Usage intentionally absent: fixture responses are not billing.
            },
        )

    provider = OpenAIProvider()
    await provider.client.close()
    provider.client = AsyncOpenAI(
        api_key="offline-evidence-first-fixture-key",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    provider.enable_budget(2)
    return provider, requests


@pytest.mark.parametrize("isolated_failure_api", [None], indirect=True)
@pytest.mark.parametrize("incident_id", ["INC-DEMO-001", "INC-DEMO-002", "INC-DEMO-003"])
async def test_initial_packet_reaches_actual_sdk_after_four_real_scoped_mcp_calls(
    isolated_failure_api, incident_id, monkeypatch, tmp_path
):
    resources = isolated_failure_api
    store, _, _, diagnostic_path, _ = resources
    session_id = str(uuid4())
    await store.activate_case(session_id, incident_id)
    # The completed synthetic case has exactly the historical frozen cutoff.
    assert await store.freeze_snapshot(session_id, incident_id) == FROZEN_CUTOFF
    provider, wire = await mock_sdk_provider(monkeypatch, resources)
    _, _, adapters, marker, _ = owned_runner_path(resources, provider, monkeypatch, tmp_path)
    progress = []
    async def save(result):
        progress.append(copy.deepcopy(result))
        await store.save_investigation(session_id, result)
    try:
        result = await investigator.collect_adaptive_investigation(
            store, session_id, incident_id, provider, save,
            limits=Settings(_env_file=None, max_diagnostic_calls=12, max_provider_turns=12),
            stop_on_tool_error=True,
        )
    finally:
        await provider.client.close()
    assert result["status"] == "complete"
    assert result["provenance"]["workflow"] == "evidence_first_v1"
    assert result["provenance"]["tool_calls"] == 4
    assert result["provenance"]["provider_turns"] == 2  # one decision plus assessment
    assert [step["tool"] for step in result["steps"][:4]] == INITIAL_TOOLS
    assert all(step["selected_by"] == "application_runbook" for step in result["steps"][:4])
    assert all(step["provider_turn"] == 0 and step["safe_arguments"] == {} for step in result["steps"][:4])
    assert len(wire) == 2  # one scripted decision and one scripted SDK assessment
    first = json.loads(wire[0]["input"][1]["content"].split("\n", 1)[-1])
    assert [item["tool"] for item in first["observations"]] == INITIAL_TOOLS
    assert all(item["selected_by"] == "application_runbook" for item in first["observations"])
    assert first["incident"]["workflow"] == "evidence_first_v1"
    temporal = first["incident"]["temporal_context"]
    assert temporal["snapshot_cutoff"] == FROZEN_CUTOFF
    assert temporal["investigation_window"] == {"start": first["incident"]["started_at"], "end": FROZEN_CUTOFF}
    coverage = temporal["returned_sample_coverage"]
    assert coverage["kind"] == "returned_samples_only" and coverage["continuous_coverage"] is False
    assert coverage["total_samples"] == len(first["evidence"])
    assert {item["id"] for item in first["evidence"]} == {item["id"] for item in result["evidence"]}
    assert first["evidence"] == result["evidence"]  # no sanitizer sampling loss
    assert "[TRUNCATED]" not in json.dumps(first)
    assert all(item["timestamp"] <= FROZEN_CUTOFF for item in first["evidence"])
    assert all(item["data"].get("incident_id", incident_id) == incident_id for item in first["evidence"])
    assert "get_service_topology" not in {item["name"] for item in first["available_tools"]}
    schema = wire[0]["text"]["format"]["schema"]
    with pytest.raises(SchemaError):
        Draft202012Validator(schema).validate({"action": "tool", "request": {"name": "get_service_topology"}})
    assert all(not key.startswith("expected") and key != "scenario" for key in first["incident"])
    requests = [json.loads(line) for line in diagnostic_path.read_text().splitlines()]
    assert len(requests) == 4
    assert all(item["session"] == session_id for item in requests)
    assert all(item["arguments"]["incident_id"] == incident_id for item in requests)
    assert all(item["arguments"]["as_of"] == FROZEN_CUTOFF for item in requests)
    assert result["provider_proposal"]["probable_failure_domain"] == "insufficient evidence"
    assert result["assessment"]["probable_failure_domain"] == "insufficient evidence"
    assert result["validation_outcome"]["status"] == "abstained"
    assert result["provenance"]["action_rejections"] == []
    assert len(adapters) == 1 and adapters[0]._entered is False
    assert marker.exists() and not process_is_running(int(marker.read_text()))
    assert progress[-1]["status"] == "complete"
    directory = PROJECT_ROOT / "artifacts/test-results"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"evidence-first-sdk-{incident_id}.json").write_text(
        json.dumps({"kind": "offline_mock_sdk_request_after_actual_local_mcp",
                    "live_model_quality_measured": False, "incident_id": incident_id,
                    "request": wire[0], "input_message_bytes": len(wire[0]["input"][1]["content"].encode()),
                    "evidence_json_bytes": len(json.dumps(first["evidence"], ensure_ascii=True).encode()),
                    "input_evidence_count": len(first["evidence"]),
                    "sanitizer_sample_truncation": False}, indent=2) + "\n", encoding="utf-8"
    )


@pytest.mark.parametrize("isolated_failure_api", [None], indirect=True)
@pytest.mark.parametrize("incident_id", ["INC-DEMO-001", "INC-DEMO-002", "INC-DEMO-003"])
async def test_operational_fixture_availability_is_verified_through_mcp_without_oracle_selection(
    isolated_failure_api, incident_id, monkeypatch, tmp_path
):
    """Artifact labels fixture rows, available rows and retrieved rows separately."""
    resources = isolated_failure_api
    store, _, _, diagnostic_path, _ = resources
    session_id = str(uuid4())
    await store.activate_case(session_id, incident_id)
    provider = ScriptedRunnerActions([])
    provider.enable_budget(2, reserved_spend=0, reservation_callback=lambda total: None)
    _, _, adapters, marker, _ = owned_runner_path(resources, provider, monkeypatch, tmp_path)
    result = await investigator.collect_adaptive_investigation(
        store, session_id, incident_id, provider,
        limits=Settings(_env_file=None, max_diagnostic_calls=12, max_provider_turns=12),
        stop_on_tool_error=True,
    )
    assert [step["tool"] for step in result["steps"][:4]] == INITIAL_TOOLS
    first = provider.inputs[0]
    assert Counter(item["kind"] for item in first["evidence"])["metric"] > 0
    assert Counter(item["kind"] for item in first["evidence"])["log"] > 0
    report = {"kind": "scripted_offline_real_mcp_evidence_availability", "incident_id": incident_id,
              "snapshot_cutoff": FROZEN_CUTOFF, "live_model_quality_measured": False, "tools": []}
    for step in result["steps"][:4]:
        name = step["tool"]
        kinds = {"query_metrics": "metric", "search_logs": ("log", "business_event")}.get(name)
        if kinds:
            all_visible = await store.evidence(session_id, incident_id=incident_id, kind=kinds,
                                               as_of=FROZEN_CUTOFF, limit=50)
            available_count = await store.evidence_count(session_id, incident_id=incident_id,
                                                         kind=kinds, as_of=FROZEN_CUTOFF)
            async with store.sessions() as fixture_session:
                fixture_count = await fixture_session.scalar(
                    select(func.count()).select_from(EvidenceRow).where(
                        EvidenceRow.incident_id == incident_id,
                        EvidenceRow.kind.in_(kinds if isinstance(kinds, tuple) else [kinds]),
                    )
                )
            available_ids = [item.id for item in all_visible]
            assert step["evidence_ids"] == available_ids[:50]
        else:
            available_ids = step["evidence_ids"]
            available_count = len(available_ids)
            fixture_count = available_count
        returned = [item for item in result["evidence"] if item["id"] in step["evidence_ids"]]
        assert len(returned) <= 50
        assert len(json.dumps(returned, ensure_ascii=True).encode()) < MAX_RESULT_BYTES
        report["tools"].append({"name": name, "model_filters": step["safe_arguments"],
                                "selected_by": step["selected_by"], "fixture_row_count": fixture_count,
                                "available_count_at_cutoff": available_count,
                                "returned_count": len(returned), "result_limit": 50 if name != "get_incident" else 1,
                                "result_limit_truncation": available_count > len(returned),
                                "returned_samples": [{"id": item["id"], "kind": item["kind"],
                                                      "timestamp": item["timestamp"], "data": item["data"]} for item in returned],
                                "diagnosis_claim_independently_scored": False})
    assert len(json.dumps(first["evidence"], ensure_ascii=True).encode()) < 90000
    assert len(first["evidence"]) <= 250
    assert all(item["timestamp"] <= FROZEN_CUTOFF for item in first["evidence"])
    assert len(adapters) == 1 and adapters[0]._entered is False
    assert marker.exists() and not process_is_running(int(marker.read_text()))
    # New test-only capture; never a live-verification run/ledger/replay artifact.
    directory = PROJECT_ROOT / "artifacts/test-results"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"evidence-first-mcp-{incident_id}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (directory / f"evidence-first-initial-context-{incident_id}.json").write_text(
        json.dumps({"kind": "scripted_offline_provider_context", **first}, indent=2) + "\n", encoding="utf-8"
    )


@pytest.mark.parametrize("isolated_failure_api", [None], indirect=True)
@pytest.mark.parametrize("incident_id", ["INC-DEMO-001", "INC-DEMO-002", "INC-DEMO-003"])
async def test_scripted_signal_follow_up_reaches_real_mcp_and_next_decision(
    isolated_failure_api, incident_id, monkeypatch, tmp_path
):
    """Operational values select a follow-up, without an incident-to-answer map."""
    class ScriptedSignalProvider(DeterministicProvider):
        name = "scripted_returned_signal_fixture"

        def __init__(self):
            self.inputs = []
            self.assessments = 0
            self.selected_tool = None

        async def next_action(self, incident, schemas, observations, evidence):
            self.inputs.append(copy.deepcopy({"observations": observations, "evidence": evidence}))
            if len(self.inputs) > 1:
                assert observations[-1]["tool"] == self.selected_tool
                assert observations[-1]["selected_by"] == "scripted_provider"
                assert observations[-1]["status"] == "complete"
                assert observations[-1]["evidence_ids"]
                assert set(observations[-1]["evidence_ids"]) <= {item["id"] for item in evidence}
                return AdaptiveDecision(action="assess", request=None), {}
            values = {}
            for item in evidence:
                if item["kind"] == "metric":
                    metric, value = item["data"].get("metric"), item["data"].get("value")
                    if isinstance(value, (int, float)):
                        values[metric] = max(values.get(metric, 0), value)
            if values.get("db_pool_utilization", 0) >= 95:
                self.selected_tool = "inspect_database_health"
            elif values.get("execution_ack_latency_ms", 0) >= 1000:
                self.selected_tool = "inspect_fix_session"
            elif values.get("kafka_consumer_lag", 0) >= 1000:
                self.selected_tool = "inspect_kafka_lag"
            else:
                return AdaptiveDecision(action="assess", request=None), {}
            return AdaptiveDecision.model_validate({"action": "tool", "request": {"name": self.selected_tool}}), {}

        async def assess(self, incident, evidence):
            self.assessments += 1
            # Scripted abstention remains available even after a useful follow-up.
            return build_assessment(incident, [])

    resources = isolated_failure_api
    store, _, _, diagnostic_path, _ = resources
    session_id = str(uuid4())
    await store.activate_case(session_id, incident_id)
    provider = ScriptedSignalProvider()
    _, _, adapters, marker, _ = owned_runner_path(resources, provider, monkeypatch, tmp_path)
    result = await investigator.collect_adaptive_investigation(
        store, session_id, incident_id, provider,
        limits=Settings(_env_file=None, max_diagnostic_calls=12, max_provider_turns=12),
        stop_on_tool_error=True,
    )
    assert result["status"] == "complete"
    assert len(provider.inputs) == 2 and provider.assessments == 1
    assert result["provenance"]["tool_calls"] == 5
    assert [step["tool"] for step in result["steps"][:4]] == INITIAL_TOOLS
    follow_up = result["steps"][4]
    assert follow_up["tool"] == provider.selected_tool
    assert follow_up["selected_by"] == "scripted_provider" and follow_up["provider_turn"] == 1
    assert result["provider_proposal"]["probable_failure_domain"] == "insufficient evidence"
    assert result["assessment"]["probable_failure_domain"] == "insufficient evidence"
    requests = [json.loads(line) for line in diagnostic_path.read_text().splitlines()]
    assert len(requests) == 5
    assert requests[-1]["path"].endswith(provider.selected_tool)
    assert all(item["session"] == session_id and item["arguments"]["incident_id"] == incident_id for item in requests)
    assert all(item["arguments"]["as_of"] == FROZEN_CUTOFF for item in requests)
    assert adapters[0]._entered is False and not process_is_running(int(marker.read_text()))
    directory = PROJECT_ROOT / "artifacts/test-results"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"evidence-first-scripted-follow-up-{incident_id}.json").write_text(
        json.dumps({"kind": "scripted_offline_actual_mcp_follow_up", "case": incident_id,
                    "selection_input": "returned metric values, no scenario labels or expected domains",
                    "selected_tool": provider.selected_tool, "returned_ids": follow_up["evidence_ids"],
                    "next_decision_received_ids": provider.inputs[1]["observations"][-1]["evidence_ids"],
                    "diagnostic_calls": 5, "decisions": 2, "assessments": 1,
                    "live_model_quality_measured": False}, indent=2) + "\n", encoding="utf-8"
    )


@pytest.mark.parametrize("isolated_failure_api", ["query_metrics"], indirect=True)
async def test_runner_strict_initial_failure_has_zero_provider_calls_and_retained_partial_receipt(
    isolated_failure_api, monkeypatch, tmp_path
):
    provider = ScriptedRunnerActions([])
    arguments, output, adapters, marker, closed_stores = owned_runner_path(
        isolated_failure_api, provider, monkeypatch, tmp_path
    )
    with pytest.raises(DiagnosticClientError):
        await runner.run(arguments)
    receipt = json.loads(next(output.glob("run-*.json")).read_text())
    ledger = json.loads(next(output.glob("experiment-*.json")).read_text())
    assert receipt["execution"] == ledger["state"] == "STOPPED"
    assert provider.decisions == provider.assessments == 0
    assert receipt["provider_calls"] == []
    assert receipt["reserved_spend_usd"] == ledger["reserved_spend_usd"] == "0"
    assert receipt["estimated_cost_usd"] is None
    partial = receipt["results"][0]
    assert partial["status"] == "failed" and partial["assessment"] is None and partial["provider_proposal"] is None
    assert partial["provenance"]["tool_calls"] == 3 and partial["provenance"]["provider_turns"] == 0
    assert [step["tool"] for step in partial["steps"]] == INITIAL_TOOLS[:3]
    assert [step["status"] for step in partial["steps"]] == ["complete", "complete", "failed"]
    assert all(step["selected_by"] == "application_runbook" for step in partial["steps"])
    assert partial["validation_outcome"]["provider_response"] == "not_requested_due_to_diagnostic_failure"
    assert partial["provenance"]["diagnostic_failure"]["tool"] == "query_metrics"
    assert {item["id"] for item in partial["evidence"]} == {"INC-DEMO-001", "TOPOLOGY-001"}
    store, _, _, _, _ = isolated_failure_api
    saved = await store.get_investigation(partial["provenance"]["session_id"], partial["id"])
    assert saved["status"] == "failed" and saved["assessment"] is None
    assert provider.closed and closed_stores == [True]
    assert len(adapters) == 1 and adapters[0]._entered is False
    assert marker.exists() and not process_is_running(int(marker.read_text()))
    assert not list(output.glob("*.lock"))
