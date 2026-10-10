"""Citation contracts through actual local MCP and offline official SDK transport.

Responses and usage below are explicitly scripted fixtures, never live-model
quality or billing evidence. The existing isolated-resource fixture disables
dotenv and forbids provider network access in parent and child interpreters.
"""

import copy
import json
from decimal import Decimal

import httpx
import pytest
from creditops import investigator
from creditops.diagnostics import build_assessment
from creditops.models import Assessment
from creditops.providers import OpenAIProvider
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaError
from pydantic import ValidationError
from test_strict_runner_mcp import (
    isolated_failure_api as isolated_failure_api_fixture,
)
from test_strict_runner_mcp import owned_runner_path, process_is_running, runner

isolated_failure_api = isolated_failure_api_fixture
INITIAL_TOOLS = ["get_incident", "get_service_topology", "query_metrics", "search_logs"]
ABSENT_RUNBOOK_PROSE = "No returned runbook IDs available in the provided evidence."
ABSENT_HISTORY_PROSE = "No returned historical incident IDs available in the provided evidence."
MISLEADING_CLAIM = "CPU stayed healthy throughout the entire incident and at the later cutoff."


async def offline_sdk(monkeypatch, resources, assessment_kind):
    """The real SDK serializes/parses; MockTransport supplies scripted responses."""
    from openai import AsyncOpenAI

    for key, value in {
        "OPENAI_API_KEY": "offline-citation-integration-fixture-key",
        "OPENAI_MODEL": "gpt-5.4-mini-2026-03-17",
        "OPENAI_INPUT_USD_PER_MILLION": "0.75",
        "OPENAI_OUTPUT_USD_PER_MILLION": "4.50",
    }.items():
        monkeypatch.setenv(key, value)
    wire, outputs = [], []

    def respond(request):
        payload = json.loads(request.content)
        wire.append(payload)
        _, _, _, diagnostic_path, _ = resources
        dispatched = [json.loads(line) for line in diagnostic_path.read_text().splitlines()]
        assert [item["path"].rsplit("/", 1)[-1] for item in dispatched] == INITIAL_TOOLS
        if len(wire) == 1:
            output = {"action": "assess", "request": None}
        else:
            assert len(wire) == 2, "No post-failure or repeated provider request is allowed"
            packet = json.loads(payload["input"][1]["content"].split("\n", 1)[1])
            assert not any(item["kind"] in {"runbook", "history", "historical_incident"} for item in packet["evidence"])
            if assessment_kind == "misleading":
                output = build_assessment(packet["incident"], packet["evidence"])[0].model_dump(mode="json")
                assert output["supporting_evidence_ids"]
                output["rca"]["probable_root_cause"] = MISLEADING_CLAIM
            else:
                # Abstention is independent of any expected scenario answer.
                output = build_assessment({}, [])[0].model_dump(mode="json")
            if assessment_kind == "invalid":
                output["relevant_runbooks"] = [ABSENT_RUNBOOK_PROSE]
                output["similar_incidents"] = [ABSENT_HISTORY_PROSE]
            outputs.append(copy.deepcopy(output))
        return httpx.Response(
            200,
            headers={"x-request-id": f"req_offline_citation_fixture_{len(wire)}"},
            json={
                "id": f"resp_offline_citation_fixture_{len(wire)}",
                "object": "response",
                "created_at": 1,
                "status": "completed",
                "model": "gpt-5.4-mini-2026-03-17",
                "output": [{
                    "id": "msg_offline_citation_fixture",
                    "type": "message",
                    "status": "completed",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": json.dumps(output), "annotations": []}],
                }],
                # Explicit fixture metadata exercises retention, not real billing.
                "usage": {"input_tokens": 101, "output_tokens": 7, "total_tokens": 108},
            },
        )

    provider = OpenAIProvider()
    await provider.client.close()
    provider.client = AsyncOpenAI(
        api_key="offline-citation-integration-fixture-key",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    return provider, wire, outputs


def assert_clean_resources(resources, adapters, marker, closed_stores, output):
    _, _, _, diagnostic_path, _ = resources
    dispatched = [json.loads(line) for line in diagnostic_path.read_text().splitlines()]
    assert [item["path"].rsplit("/", 1)[-1] for item in dispatched] == INITIAL_TOOLS
    assert len(adapters) == 1 and adapters[0]._entered is False
    assert marker.exists() and not process_is_running(int(marker.read_text()))
    assert closed_stores == [True]
    assert not list(output.glob("*.lock"))


@pytest.mark.parametrize("isolated_failure_api", [None], indirect=True)
async def test_real_mcp_packet_accepts_empty_optional_citations_and_preserves_abstention(
    isolated_failure_api, monkeypatch, tmp_path
):
    resources = isolated_failure_api
    provider, wire, outputs = await offline_sdk(monkeypatch, resources, "abstention")
    arguments, output, adapters, marker, closed_stores = owned_runner_path(resources, provider, monkeypatch, tmp_path)
    await runner.run(arguments)
    receipt = json.loads(next(output.glob("run-*.json")).read_text())
    result = receipt["results"][0]
    assert result["status"] == "complete"
    assert receipt["execution"] == "COMPLETED_APPROVED_CASES"
    assert len(wire) == len(receipt["provider_calls"]) == 2
    assert result["provenance"]["workflow"] == "evidence_first_v1"
    assert result["provenance"]["model_called"] is True
    assert result["provenance"]["provider_turns"] == 2
    assert result["provenance"]["tool_calls"] == 4
    assert all(step["selected_by"] == "application_runbook" and step["provider_turn"] == 0 for step in result["steps"][:4])
    assert result["provider_proposal"] == outputs[0]
    assert result["assessment"]["probable_failure_domain"] == "insufficient evidence"
    assert result["validation_outcome"]["status"] == "abstained"
    assessment_schema = wire[1]["text"]["format"]["schema"]
    Draft202012Validator(assessment_schema).validate(outputs[0])
    for field in ("relevant_runbooks", "similar_incidents"):
        assert assessment_schema["properties"][field]["maxItems"] == 0
        assert outputs[0][field] == []
        invalid = {**outputs[0], field: ["NONE"]}
        with pytest.raises(SchemaError):
            Draft202012Validator(assessment_schema).validate(invalid)
    parsed = Assessment.model_validate(result["assessment"])
    assert parsed.relevant_runbooks == parsed.similar_incidents == []
    assert all(call["status"] == "success" for call in receipt["provider_calls"])
    assert_clean_resources(resources, adapters, marker, closed_stores, output)


@pytest.mark.parametrize("isolated_failure_api", [None], indirect=True)
async def test_real_runner_preserves_sdk_metadata_and_partial_receipt_after_invalid_citations(
    isolated_failure_api, monkeypatch, tmp_path
):
    resources = isolated_failure_api
    provider, wire, outputs = await offline_sdk(monkeypatch, resources, "invalid")
    arguments, output, adapters, marker, closed_stores = owned_runner_path(resources, provider, monkeypatch, tmp_path)
    with pytest.raises(ValidationError):
        await runner.run(arguments)
    receipt = json.loads(next(output.glob("run-*.json")).read_text())
    ledger = json.loads(next(output.glob("experiment-*.json")).read_text())
    partial = receipt["results"][0]
    assert receipt["execution"] == ledger["state"] == "STOPPED"
    assert len(wire) == len(receipt["provider_calls"]) == 2
    # Public/historical serialization stays readable; only this request narrows IDs.
    historical = Assessment.model_validate(outputs[0])
    assert historical.relevant_runbooks == [ABSENT_RUNBOOK_PROSE]
    assert historical.similar_incidents == [ABSENT_HISTORY_PROSE]
    with pytest.raises(SchemaError):
        Draft202012Validator(wire[1]["text"]["format"]["schema"]).validate(outputs[0])
    assert partial["status"] == "failed"
    assert partial["assessment"] is None
    assert partial["provider_proposal"] == outputs[0]
    assert partial["validation_outcome"]["status"] == "not_validated"
    assert partial["validation_outcome"]["stage"] == "assessment_structured_output"
    assert partial["validation_outcome"]["provider_response"] == "parse_error"
    # Public-shape parsing makes the rejected proposal observable; it does not
    # mean the provider-facing citation contract or semantic validator accepted it.
    assert partial["validation_outcome"]["structurally_parsed"] is True
    assert partial["validation_outcome"]["provider_schema_accepted"] is False
    assert partial["validation_outcome"]["changed_fields"] == []
    assert {field["field"] for field in partial["validation_outcome"]["rejected_fields"]} == {
        "relevant_runbooks", "similar_incidents"
    }
    assert all(field["reason"] == "assessment_response_schema_violation" for field in partial["validation_outcome"]["rejected_fields"])
    assert partial["provenance"]["provider_turns"] == 2
    assert partial["provenance"]["tool_calls"] == 4
    assert partial["provenance"]["model_called"] is True
    assert partial["provenance"].get("assessment_source") is None
    assert [step["tool"] for step in partial["steps"]] == INITIAL_TOOLS
    calls = receipt["provider_calls"]
    assert calls[0]["status"] == "success" and calls[1]["status"] == "parse_error"
    assert calls[1]["response_id"] == "resp_offline_citation_fixture_2"
    assert calls[1]["request_id"] == "req_offline_citation_fixture_2"
    assert calls[1]["returned_model"] == "gpt-5.4-mini-2026-03-17"
    assert calls[1]["response_received"] is True
    assert calls[1]["structured_output"] is None
    assert calls[1]["rejected_assessment_proposal"] == outputs[0]
    assert calls[1]["usage"]["input_tokens"] == 101 and calls[1]["usage"]["output_tokens"] == 7
    assert calls[1]["usage"]["estimated_cost_usd"] is not None
    assert calls[1]["duration_ms"] > 0 and calls[1]["ended_at"]
    assert Decimal(receipt["reserved_spend_usd"]) == Decimal(ledger["reserved_spend_usd"]) > 0
    assert Decimal(receipt["reserved_spend_usd"]) == sum(Decimal(call["reserved_cost_usd"]) for call in calls)
    assert partial["provider_calls"] == calls
    store, _, _, _, _ = resources
    saved = await store.get_investigation(partial["provenance"]["session_id"], partial["id"])
    assert saved["status"] == "failed" and saved["assessment"] is None
    assert saved["provider_calls"] == calls
    # The UI's existing stream path reports failure, never a complete event.
    streamed = [event async for event in investigator.stream_events(store, partial["provenance"]["session_id"], partial["id"])]
    assert any("event: error" in event for event in streamed)
    assert not any("event: complete" in event for event in streamed)
    assert_clean_resources(resources, adapters, marker, closed_stores, output)


@pytest.mark.parametrize("isolated_failure_api", [None], indirect=True)
async def test_valid_citations_do_not_claim_factual_verification_of_scripted_narrative(
    isolated_failure_api, monkeypatch, tmp_path
):
    resources = isolated_failure_api
    provider, wire, outputs = await offline_sdk(monkeypatch, resources, "misleading")
    arguments, output, adapters, marker, closed_stores = owned_runner_path(resources, provider, monkeypatch, tmp_path)
    await runner.run(arguments)
    receipt = json.loads(next(output.glob("run-*.json")).read_text())
    result = receipt["results"][0]
    Draft202012Validator(wire[1]["text"]["format"]["schema"]).validate(outputs[0])
    assert set(outputs[0]["supporting_evidence_ids"]) <= {item["id"] for item in result["evidence"]}
    assert result["provider_proposal"]["rca"]["probable_root_cause"] == MISLEADING_CLAIM
    assert result["assessment"]["rca"]["probable_root_cause"] != MISLEADING_CLAIM
    assert result["validation_outcome"]["original_claims_independently_verified"] is False
    assert any(field["field"] == "rca.probable_root_cause" for field in result["validation_outcome"]["changed_fields"])
    assert result["validation_outcome"]["invalid_evidence_ids"] == []
    assert len(wire) == 2 and result["provenance"]["tool_calls"] == 4
    assert_clean_resources(resources, adapters, marker, closed_stores, output)
