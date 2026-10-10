"""Explicit case selection through the actual runner and local stdio MCP.

Provider decisions, assessments and reservations are scripted offline fixtures.
The real runner, SQLite persistence, MCP client/server, HTTP diagnostic tools,
strict failure policy and cleanup are exercised. Parent and child interpreters
disable dotenv and block external inference transports.
"""

import json
from decimal import Decimal
from uuid import uuid4

import pytest
from creditops.diagnostic_clients import DiagnosticClientError
from creditops.store import Store
from test_strict_runner_mcp import (
    FIXTURE_RESERVATION,
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


def execution_arguments(selection, output, *, experiment_id=None, stage="first", reviewed=False):
    """Enter the public parser; every identity belongs to temporary test output."""
    arguments = [
        "--provider", "openai",
        "--model", "gpt-5.4-mini-2026-03-17",
        *selection,
        "--max-tool-calls", "12",
        "--max-provider-turns", "12",
        "--max-spend-usd", "2",
        "--timeout-seconds", "30",
        "--provider-timeout-seconds", "5",
        "--diagnostic-timeout-seconds", "10",
        "--total-timeout-seconds", "33",
        "--input-price-ceiling", "0.75",
        "--output-price-ceiling", "4.50",
        "--experiment-id", experiment_id or str(uuid4()),
        "--stage", stage,
        "--execute-paid",
        "--output-directory", str(output),
    ]
    if reviewed:
        arguments.append("--continue-reviewed")
    return runner.parse_args(arguments)


def observe_real_activation(monkeypatch):
    activated = []
    original = Store.activate_case

    async def activate(self, session_id, incident_id):
        activated.append((session_id, incident_id))
        return await original(self, session_id, incident_id)

    monkeypatch.setattr(Store, "activate_case", activate)
    return activated


def assert_selected_scope(receipt, ledger, dispatched, activated, incident_id):
    result = receipt["results"][0]
    session_id = result["provenance"]["session_id"]
    assert activated == [(session_id, incident_id)]
    assert receipt["configuration"]["case_ids"] == [incident_id]
    assert ledger["configuration"] == receipt["configuration"]
    assert receipt["configuration"]["stop_on_tool_error"] is True
    assert receipt["configuration"]["workflow"] == "evidence_first_v1"
    assert len(ledger["attempts"]) == len(receipt["results"]) == 1
    assert ledger["attempts"][0]["incident_id"] == result["incident_id"] == incident_id
    assert ledger["attempts"][0]["run_id"] == receipt["run_id"]
    assert result["provenance"]["experiment_id"] == receipt["experiment_id"]
    assert result["provenance"]["source_commit"] == receipt["configuration"]["source_commit"]
    assert result["provenance"]["snapshot_cutoff"] == FROZEN_CUTOFF
    assert all(item["session"] == session_id for item in dispatched)
    assert all(item["arguments"]["incident_id"] == incident_id for item in dispatched)
    assert all(item["arguments"]["as_of"] == FROZEN_CUTOFF for item in dispatched)
    assert result["steps"][0]["evidence_ids"] == [incident_id]
    assert any(item["id"] == incident_id for item in result["evidence"])
    assert all(item["id"] != "INC-DEMO-001" for item in result["evidence"])
    assert all(item["data"].get("incident_id", incident_id) == incident_id for item in result["evidence"])
    assert Decimal(receipt["reserved_spend_usd"]) == Decimal(ledger["reserved_spend_usd"]) == FIXTURE_RESERVATION
    assert receipt["provider_calls"][0]["fixture_only"] is True
    assert receipt["estimated_cost_usd"] is None  # No fabricated usage/billing.


def assert_owned_cleanup(provider, adapters, marker, closed_stores, output):
    assert provider.closed and closed_stores == [True]
    assert len(adapters) == 1 and adapters[0]._entered is False
    assert marker.exists() and not process_is_running(int(marker.read_text()))
    assert not list(output.glob("*.lock"))


@pytest.mark.parametrize("isolated_failure_api", [None], indirect=True)
@pytest.mark.parametrize("incident_id", ["INC-DEMO-002", "INC-DEMO-003"])
async def test_explicit_case_investigates_only_selected_case_through_real_mcp(
    isolated_failure_api, incident_id, monkeypatch, tmp_path
):
    provider = ScriptedRunnerActions([])
    _, output, adapters, marker, closed_stores = owned_runner_path(
        isolated_failure_api, provider, monkeypatch, tmp_path
    )
    activated = observe_real_activation(monkeypatch)
    arguments = execution_arguments(["--case-id", incident_id], output)
    returned = await runner.run(arguments)
    receipt = json.loads(next(output.glob("run-*.json")).read_text())
    ledger = json.loads(next(output.glob("experiment-*.json")).read_text())
    store, _, _, requests_path, _ = isolated_failure_api
    dispatched = [json.loads(line) for line in requests_path.read_text().splitlines()]
    assert_selected_scope(receipt, ledger, dispatched, activated, incident_id)
    assert returned["execution"] == receipt["execution"] == ledger["state"] == "COMPLETED_APPROVED_CASES"
    assert ledger["attempts"][0]["status"] == "complete"
    assert provider.decisions == provider.assessments == 1
    assert [item["path"].rsplit("/", 1)[-1] for item in dispatched] == INITIAL_TOOLS
    result = receipt["results"][0]
    assert result["status"] == "complete" and result["assessment"] is not None
    assert result["provenance"]["tool_calls"] == 4
    assert all(step["selected_by"] == "application_runbook" for step in result["steps"][:4])
    saved = await store.get_investigation(result["provenance"]["session_id"], result["id"])
    assert saved["incident_id"] == incident_id and saved["status"] == "complete"
    assert saved["provider_proposal"] == result["provider_proposal"]
    assert saved["assessment"] == result["assessment"]
    assert saved["provenance"] == result["provenance"]
    identity = receipt["local_identity"]
    marker_record = await store.get_investigation(identity["session_id"], identity["record_id"])
    assert marker_record["incident_id"] == incident_id
    assert_owned_cleanup(provider, adapters, marker, closed_stores, output)


@pytest.mark.parametrize("isolated_failure_api", ["query_metrics_follow_up"], indirect=True)
@pytest.mark.parametrize("incident_id", ["INC-DEMO-002", "INC-DEMO-003"])
async def test_strict_selected_case_failure_retains_case_reservation_and_never_retries(
    isolated_failure_api, incident_id, monkeypatch, tmp_path
):
    provider = ScriptedRunnerActions([{"name": "query_metrics", "metric": "offline-controlled-failure"}])
    _, output, adapters, marker, closed_stores = owned_runner_path(
        isolated_failure_api, provider, monkeypatch, tmp_path
    )
    activated = observe_real_activation(monkeypatch)
    arguments = execution_arguments(["--case-id", incident_id], output)
    with pytest.raises(DiagnosticClientError):
        await runner.run(arguments)
    receipt = json.loads(next(output.glob("run-*.json")).read_text())
    ledger = json.loads(next(output.glob("experiment-*.json")).read_text())
    store, _, _, requests_path, _ = isolated_failure_api
    dispatched = [json.loads(line) for line in requests_path.read_text().splitlines()]
    assert_selected_scope(receipt, ledger, dispatched, activated, incident_id)
    assert receipt["execution"] == ledger["state"] == "STOPPED"
    assert ledger["attempts"][0]["status"] == "interrupted_or_failed"
    assert provider.decisions == 1 and provider.assessments == 0
    assert len(receipt["provider_calls"]) == 1
    assert [item["path"].rsplit("/", 1)[-1] for item in dispatched] == [*INITIAL_TOOLS, "query_metrics"]
    assert dispatched[-1]["arguments"]["metric"] == "offline-controlled-failure"
    result = receipt["results"][0]
    assert result["status"] == "failed"
    assert result["assessment"] is None and result["provider_proposal"] is None
    assert result["provenance"]["tool_calls"] == 5
    assert result["provenance"]["provider_turns"] == 1
    assert result["provenance"]["stop_on_tool_error"] is True
    assert result["provenance"]["diagnostic_failure"]["tool"] == "query_metrics"
    assert result["provenance"]["stop_reason"]
    assert result["validation_outcome"]["provider_response"] == "not_requested_due_to_diagnostic_failure"
    assert result["steps"][-1]["status"] == "failed"
    assert result["steps"][-1]["selected_by"] == "scripted_provider"
    saved = await store.get_investigation(result["provenance"]["session_id"], result["id"])
    assert saved["incident_id"] == incident_id and saved["status"] == "failed"
    assert saved["assessment"] is None and saved["provider_proposal"] is None
    assert saved["provider_calls"] == receipt["provider_calls"]
    identity = receipt["local_identity"]
    marker_record = await store.get_investigation(identity["session_id"], identity["record_id"])
    assert marker_record["incident_id"] == incident_id
    assert_owned_cleanup(provider, adapters, marker, closed_stores, output)


@pytest.mark.parametrize("isolated_failure_api", [None], indirect=True)
async def test_legacy_first_and_reviewed_remaining_keep_original_prefix_behavior(
    isolated_failure_api, monkeypatch, tmp_path
):
    class ScriptedStagedProvider(ScriptedRunnerActions):
        def enable_budget(self, maximum, *, reserved_spend, reservation_callback):
            assert maximum == 2
            self.reserve = lambda current: reservation_callback(reserved_spend + current)

    first_provider = ScriptedStagedProvider([])
    _, output, adapters, marker, closed_stores = owned_runner_path(
        isolated_failure_api, first_provider, monkeypatch, tmp_path
    )
    activated = observe_real_activation(monkeypatch)
    experiment_id = str(uuid4())
    first_args = execution_arguments(["--case-count", "3"], output, experiment_id=experiment_id)
    first = await runner.run(first_args)
    assert first["execution"] == "AWAITING_FIRST_CASE_REVIEW"
    assert [result["incident_id"] for result in first["results"]] == ["INC-DEMO-001"]
    assert [incident for _, incident in activated] == ["INC-DEMO-001"]
    assert first_provider.decisions == first_provider.assessments == 1
    assert_owned_cleanup(first_provider, adapters, marker, closed_stores, output)

    remaining_provider = ScriptedStagedProvider([])
    monkeypatch.setattr(runner, "create_provider", lambda name: remaining_provider)
    remaining_args = execution_arguments(
        ["--case-count", "3"], output, experiment_id=experiment_id, stage="remaining", reviewed=True
    )
    remaining = await runner.run(remaining_args)
    ledger = json.loads(next(output.glob("experiment-*.json")).read_text())
    assert remaining["execution"] == ledger["state"] == "COMPLETED_APPROVED_CASES"
    assert remaining["configuration"] == first["configuration"] == ledger["configuration"]
    assert remaining["configuration"]["case_ids"] == ["INC-DEMO-001", "INC-DEMO-002", "INC-DEMO-003"]
    assert [result["incident_id"] for result in remaining["results"]] == ["INC-DEMO-002", "INC-DEMO-003"]
    assert [incident for _, incident in activated] == ["INC-DEMO-001", "INC-DEMO-002", "INC-DEMO-003"]
    assert [attempt["incident_id"] for attempt in ledger["attempts"]] == ["INC-DEMO-001", "INC-DEMO-002", "INC-DEMO-003"]
    assert all(attempt["status"] == "complete" for attempt in ledger["attempts"])
    assert remaining_provider.decisions == remaining_provider.assessments == 2
    assert Decimal(ledger["reserved_spend_usd"]) == Decimal(remaining["reserved_spend_usd"]) == FIXTURE_RESERVATION * 3
    _, _, _, requests_path, _ = isolated_failure_api
    dispatched = [json.loads(line) for line in requests_path.read_text().splitlines()]
    assert [item["path"].rsplit("/", 1)[-1] for item in dispatched] == INITIAL_TOOLS * 3
    assert [item["arguments"]["incident_id"] for item in dispatched] == ["INC-DEMO-001"] * 4 + ["INC-DEMO-002"] * 4 + ["INC-DEMO-003"] * 4
    assert first_provider.closed and remaining_provider.closed
    assert closed_stores == [True, True]
    assert len(adapters) == 3 and all(adapter._entered is False for adapter in adapters)
    assert marker.exists() and not process_is_running(int(marker.read_text()))
    assert not list(output.glob("*.lock"))
