"""Scripted offline checks of verification stopping, not live-model capability."""

import asyncio
import copy

import pytest
from creditops.diagnostic_clients import (
    DiagnosticClientError,
    DiagnosticConnectionError,
    safe_arguments,
    validate_items,
)
from creditops.investigator import collect_adaptive_investigation
from creditops.providers import AdaptiveDecision, DeterministicProvider, DiagnosticRequest
from creditops.settings import Settings
from test_adaptive_investigator import CUTOFF, FakeStore, ScriptedClient

INITIAL_CALLS = [(name, {}) for name in ("get_incident", "get_service_topology", "query_metrics", "search_logs")]


class CountingScript(DeterministicProvider):
    name = "scripted_strict_stop"

    def __init__(self, requests):
        self.requests = list(requests)
        self.decision_calls = 0
        self.assessment_calls = 0
        self.observed = []
        self.catalogs = []

    async def next_action(self, incident, schemas, observations, evidence):
        self.decision_calls += 1
        self.observed.append(copy.deepcopy(observations))
        self.catalogs.append(copy.deepcopy(schemas))
        if self.requests:
            return AdaptiveDecision(action="tool", request=self.requests.pop(0)), {}
        return AdaptiveDecision(action="assess", request=None), {}

    async def assess(self, incident, evidence):
        self.assessment_calls += 1
        return await super().assess(incident, evidence)


def evidence(identifier, kind, summary):
    return {
        "id": identifier,
        "kind": kind,
        "service": "quote-service",
        "timestamp": CUTOFF,
        "summary": summary,
        "data": {},
    }


class ValidatingScriptClient(ScriptedClient):
    """Scripted I/O retains the production argument/result validation boundary."""

    def __init__(self, *, fail=None, failure="error", rows=None):
        super().__init__(fail=fail)
        self.failure = failure
        self.rows = rows or {}
        self.timeout_cancelled = False

    async def call(self, name, arguments):
        arguments = safe_arguments(name, arguments)
        self.calls.append((name, arguments))
        if name == self.fail:
            if self.failure == "timeout":
                try:
                    await asyncio.Event().wait()
                finally:
                    self.timeout_cancelled = True
            if self.failure == "invalid_result":
                return validate_items([{"id": "BAD-RESULT"}], CUTOFF)
            if self.failure == "connection":
                raise DiagnosticConnectionError("Scripted transport disconnected")
            if self.failure == "cancellation":
                raise asyncio.CancelledError()
            raise DiagnosticClientError("password=do-not-retain-test-fixture")
        rows = (
            [evidence("INC-DEMO-001", "incident", "Incident context")]
            if name == "get_incident"
            else self.rows.get((name, arguments.get("q")), [])
        )
        return validate_items(rows, CUTOFF)


async def collect_script(client, provider, snapshots, *, strict=True, limits=None, retain=None):
    async def save(result):
        snapshots.append(copy.deepcopy(result))
        if retain:
            await retain(result)

    return await collect_adaptive_investigation(
        FakeStore(),
        "test",
        "INC-DEMO-001",
        provider,
        save,
        diagnostic_client=client,
        limits=limits,
        stop_on_tool_error=strict,
    )


def assert_stopped(result, *, tool, category, error_category, tool_calls):
    assert result["status"] == "failed"
    assert result["provenance"]["stop_on_tool_error"] is True
    assert result["provenance"]["stop_reason"]
    assert result["provenance"]["diagnostic_failure"] == {
        "tool": tool,
        "category": category,
        "error_category": error_category,
    }
    assert result["provenance"]["tool_calls"] == tool_calls
    assert result["steps"][-1]["tool"] == tool
    assert result["steps"][-1]["status"] == "failed"
    assert result["steps"][-1]["error"]
    assert result["steps"][-1]["duration_ms"] >= 0
    assert result["assessment"] is None
    assert result["provider_proposal"] is None
    outcome = result["validation_outcome"]
    assert outcome["status"] == "not_validated"
    assert outcome["structurally_parsed"] is False
    assert outcome["provider_response"] == "not_requested_due_to_diagnostic_failure"
    assert outcome["rejected_fields"] == []
    assert "do-not-retain-test-fixture" not in str(result)


async def test_strict_failure_stops_before_the_next_provider_decision_or_assessment():
    provider = CountingScript([DiagnosticRequest(name="inspect_database_health")])
    client = ScriptedClient(fail="inspect_database_health")
    snapshots = []

    async def retain(result):
        snapshots.append(copy.deepcopy(result))

    try:
        await collect_adaptive_investigation(
            FakeStore(),
            "test",
            "INC-DEMO-001",
            provider,
            retain,
            diagnostic_client=client,
            stop_on_tool_error=True,
        )
    except DiagnosticClientError:
        pass

    assert provider.decision_calls == 1
    assert provider.assessment_calls == 0
    assert client.calls == [*INITIAL_CALLS, ("inspect_database_health", {})]
    assert client.closed
    stopped = snapshots[-1]
    assert stopped["status"] == "failed"
    assert stopped["steps"][-1]["status"] == "failed"
    assert stopped["assessment"] is None
    assert stopped["provider_proposal"] is None
    assert stopped["validation_outcome"]["status"] == "not_validated"
    assert stopped["validation_outcome"]["assessment_source"] is None


async def test_initial_context_failure_stops_before_any_provider_call():
    provider = CountingScript([DiagnosticRequest(name="inspect_database_health")])
    client = ValidatingScriptClient(fail="get_incident")
    snapshots = []
    with pytest.raises(DiagnosticClientError):
        await collect_script(client, provider, snapshots)
    assert provider.decision_calls == provider.assessment_calls == 0
    assert client.calls == [("get_incident", {})]
    assert client.closed
    assert_stopped(
        snapshots[-1],
        tool="get_incident",
        category="error",
        error_category="DiagnosticClientError",
        tool_calls=1,
    )
    assert snapshots[-1]["evidence"] == []


@pytest.mark.parametrize(
    "failure,category,error_category",
    [
        ("error", "error", "DiagnosticClientError"),
        ("timeout", "timeout", "TimeoutError"),
        ("invalid_result", "error", "DiagnosticClientError"),
    ],
)
async def test_strict_diagnostic_failure_retains_context_and_stops(failure, category, error_category):
    provider = CountingScript(
        [DiagnosticRequest(name="inspect_database_health"), DiagnosticRequest(name="search_runbooks")]
    )
    client = ValidatingScriptClient(fail="inspect_database_health", failure=failure)
    snapshots = []
    with pytest.raises(DiagnosticClientError):
        await collect_script(client, provider, snapshots, limits=Settings(diagnostic_timeout_seconds=0.1))
    assert provider.decision_calls == 1
    assert provider.assessment_calls == 0
    assert client.calls == [*INITIAL_CALLS, ("inspect_database_health", {})]
    assert client.closed
    if failure == "timeout":
        assert client.timeout_cancelled
    assert_stopped(
        snapshots[-1],
        tool="inspect_database_health",
        category=category,
        error_category=error_category,
        tool_calls=5,
    )
    assert [item["id"] for item in snapshots[-1]["evidence"]] == ["INC-DEMO-001"]
    assert snapshots[-1]["usage"]["total_tokens"] is None


@pytest.mark.parametrize(
    "limit_overrides",
    [{"max_diagnostic_calls": 5}, {"max_provider_turns": 2}],
)
async def test_failure_in_final_slot_cannot_fall_through_to_assessment_or_fallback(limit_overrides):
    provider = CountingScript([DiagnosticRequest(name="inspect_database_health")])
    client = ValidatingScriptClient(fail="inspect_database_health")
    snapshots = []
    with pytest.raises(DiagnosticClientError):
        await collect_script(client, provider, snapshots, limits=Settings(**limit_overrides))
    assert provider.decision_calls == 1
    assert provider.assessment_calls == 0
    assert [name for name, _ in client.calls] == [*(name for name, _ in INITIAL_CALLS), "inspect_database_health"]
    assert client.closed
    assert_stopped(
        snapshots[-1],
        tool="inspect_database_health",
        category="error",
        error_category="DiagnosticClientError",
        tool_calls=5,
    )
    assert "assessment_source" not in snapshots[-1]["provenance"]


async def test_successful_empty_result_permits_a_distinct_broader_query():
    provider = CountingScript(
        [
            DiagnosticRequest(name="search_logs", q="timeout OR dropped"),
            DiagnosticRequest(name="search_logs", q=""),
        ]
    )
    client = ValidatingScriptClient(
        rows={("search_logs", ""): [evidence("LOG-BROAD-001", "log", "A bounded retrieved log")]}
    )
    snapshots = []
    result = await collect_script(client, provider, snapshots)
    assert provider.decision_calls == 3
    assert provider.assessment_calls == 1
    assert client.calls == [
        *INITIAL_CALLS,
        ("search_logs", {"q": "timeout OR dropped"}),
        ("search_logs", {"q": ""}),
    ]
    assert client.closed
    empty_observation = provider.observed[1][-1]
    assert empty_observation["status"] == "complete"
    assert empty_observation["evidence_ids"] == []
    assert empty_observation["error"] is None
    assert provider.observed[2][-1]["evidence_ids"] == ["LOG-BROAD-001"]
    assert "healthy" not in str(empty_observation).lower()
    assert result["assessment"]["probable_failure_domain"] == "insufficient evidence"
    assert result["status"] == "complete"
    assert "diagnostic_failure" not in result["provenance"]


async def test_default_recovery_still_observes_error_and_selects_another_tool():
    provider = CountingScript(
        [DiagnosticRequest(name="inspect_database_health"), DiagnosticRequest(name="search_runbooks")]
    )
    client = ValidatingScriptClient(
        fail="inspect_database_health",
        rows={("search_runbooks", None): [evidence("RUNBOOK-001", "runbook", "Bounded runbook")]},
    )
    snapshots = []

    async def retain(result):
        snapshots.append(copy.deepcopy(result))

    # Omission must preserve the normal application's recovery behavior.
    result = await collect_adaptive_investigation(
        FakeStore(), "test", "INC-DEMO-001", provider, retain, diagnostic_client=client
    )
    assert provider.decision_calls == 3
    assert provider.assessment_calls == 1
    assert [name for name, _ in client.calls] == [*(name for name, _ in INITIAL_CALLS), "inspect_database_health", "search_runbooks"]
    assert provider.observed[1][-1]["status"] == "failed"
    assert provider.observed[1][-1]["evidence_ids"] == []
    assert provider.observed[1][-1]["error"]
    assert client.closed
    assert result["provenance"]["stop_on_tool_error"] is False
    assert result["status"] == "complete"
    assert result["assessment"]["requires_human_review"]
    assert any("unknown, not healthy" in item for item in result["assessment"]["limitations"])


@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("failure", ["connection", "cancellation"])
async def test_existing_fatal_transport_and_cancellation_never_recover(strict, failure):
    provider = CountingScript([DiagnosticRequest(name="inspect_database_health")])
    client = ValidatingScriptClient(fail="inspect_database_health", failure=failure)
    snapshots = []
    expected = DiagnosticConnectionError if failure == "connection" else asyncio.CancelledError
    with pytest.raises(expected):
        await collect_script(client, provider, snapshots, strict=strict)
    assert provider.decision_calls == 1
    assert provider.assessment_calls == 0
    assert [name for name, _ in client.calls] == [*(name for name, _ in INITIAL_CALLS), "inspect_database_health"]
    assert client.closed
    assert snapshots[-1]["status"] == "failed"
    assert snapshots[-1]["assessment"] is None


async def test_partial_persistence_failure_cannot_resume_investigation():
    provider = CountingScript(
        [DiagnosticRequest(name="inspect_database_health"), DiagnosticRequest(name="search_runbooks")]
    )
    client = ValidatingScriptClient(fail="inspect_database_health")
    snapshots = []

    async def cannot_persist_failed_step(result):
        if result["steps"] and result["steps"][-1]["status"] == "failed":
            raise OSError("Scripted local receipt persistence unavailable")

    with pytest.raises(OSError):
        await collect_script(client, provider, snapshots, retain=cannot_persist_failed_step)
    assert provider.decision_calls == 1
    assert provider.assessment_calls == 0
    assert [name for name, _ in client.calls] == [*(name for name, _ in INITIAL_CALLS), "inspect_database_health"]
    assert client.closed
    assert_stopped(
        snapshots[-1],
        tool="inspect_database_health",
        category="error",
        error_category="DiagnosticClientError",
        tool_calls=5,
    )


@pytest.mark.parametrize("strict", [True, False])
async def test_model_policy_override_and_scope_injection_remain_fatal(strict):
    class InjectingScript(CountingScript):
        def __init__(self, payload):
            super().__init__([])
            self.payload = payload

        async def next_action(self, *args):
            self.decision_calls += 1
            return self.payload, {}

    for payload in (
        {
            "action": "tool",
            "request": {"name": "query_metrics"},
            "stop_on_tool_error": False,
        },
        {
            "action": "tool",
            "request": {"name": "query_metrics", "incident_id": "INC-DEMO-002"},
        },
    ):
        provider = InjectingScript(payload)
        client = ValidatingScriptClient()
        snapshots = []
        with pytest.raises(ValueError):
            await collect_script(client, provider, snapshots, strict=strict)
        assert provider.decision_calls == 1
        assert provider.assessment_calls == 0
        assert client.calls == INITIAL_CALLS
        assert client.closed
        stopped = snapshots[-1]
        assert stopped["status"] == "failed"
        assert stopped["provenance"]["stop_on_tool_error"] is strict
        assert stopped["provenance"]["action_rejections"] == [
            {
                "stage": "parsed_decision",
                "reason": "invalid_tool_contract",
                "provider_turn": 1,
                "mcp_dispatched": False,
            }
        ]
        assert stopped["assessment"] is None


async def test_strict_duplicate_stops_without_substitute_assessment_or_complete_outcome():
    class ReceiptScript(CountingScript):
        def __init__(self, requests):
            super().__init__(requests)
            self.execution_receipts = []

        async def next_action(self, *args):
            decision = await super().next_action(*args)
            # Offline receipt fixtures test that successful decision metadata
            # never overwrites the fact no assessment was requested.
            self.execution_receipts.append(
                {"status": "success", "request_started": False, "usage": {"total_tokens": None}}
            )
            return decision

    provider = ReceiptScript(
        [DiagnosticRequest(name="get_service_topology")]
    )
    client = ValidatingScriptClient(
        rows={("get_service_topology", None): [evidence("TOPOLOGY-001", "topology", "Bounded topology")]}
    )
    snapshots = []
    with pytest.raises(DiagnosticClientError):
        await collect_script(client, provider, snapshots)

    assert provider.decision_calls == 1
    assert provider.assessment_calls == 0
    assert client.calls == INITIAL_CALLS
    assert client.closed
    stopped = snapshots[-1]
    assert stopped["status"] == "failed"
    assert stopped["assessment"] is None
    assert stopped["provider_proposal"] is None
    assert stopped["validation_outcome"]["provider_response"] == "not_requested_due_to_guard_stop"
    assert stopped["validation_outcome"]["status"] == "not_validated"
    assert stopped["validation_outcome"]["assessment_source"] is None
    assert stopped["validation_outcome"]["rejected_fields"] == []
    assert stopped["provenance"]["tool_calls"] == 4
    assert len(stopped["provider_calls"]) == 1
    assert stopped["provenance"]["action_rejections"] == [
        {
            "stage": "investigation_guard",
            "reason": "duplicate_diagnostic_request",
            "provider_turn": 1,
            "mcp_dispatched": False,
            "action": {"name": "get_service_topology", "arguments": {}},
        }
    ]
    assert [item["id"] for item in stopped["evidence"]] == ["INC-DEMO-001", "TOPOLOGY-001"]
    assert all(item["tool"] != "assessment_validation" for item in stopped["steps"])


@pytest.mark.parametrize(
    "limit_overrides,requests,reason,decision_calls,diagnostic_calls,rejected_action",
    [
        (
            {"max_no_progress_calls": 2},
            [DiagnosticRequest(name="search_logs", q="narrow"), DiagnosticRequest(name="search_logs", q="")],
            "no_progress_limit",
            2,
            6,
            None,
        ),
        (
            {"max_diagnostic_calls": 5},
            [DiagnosticRequest(name="inspect_database_health"), DiagnosticRequest(name="search_logs", q="")],
            "diagnostic_call_limit",
            2,
            5,
            {"name": "search_logs", "arguments": {"q": ""}},
        ),
        (
            {"max_provider_turns": 2},
            [DiagnosticRequest(name="query_metrics", metric="latency")],
            "provider_turn_limit",
            1,
            5,
            None,
        ),
    ],
)
async def test_strict_control_limits_stop_before_assessment(
    limit_overrides, requests, reason, decision_calls, diagnostic_calls, rejected_action
):
    provider = CountingScript(requests)
    client = ValidatingScriptClient()
    snapshots = []
    with pytest.raises(DiagnosticClientError):
        await collect_script(client, provider, snapshots, limits=Settings(**limit_overrides))
    assert provider.decision_calls == decision_calls
    assert provider.assessment_calls == 0
    assert len(client.calls) == diagnostic_calls
    assert client.closed
    stopped = snapshots[-1]
    assert stopped["status"] == "failed"
    assert stopped["assessment"] is None
    assert stopped["provider_proposal"] is None
    assert stopped["provenance"]["guard_stop"] == reason
    assert stopped["validation_outcome"]["provider_response"] == "not_requested_due_to_guard_stop"
    if rejected_action:
        assert stopped["provenance"]["action_rejections"][0]["action"] == rejected_action
        assert stopped["provenance"]["action_rejections"][0]["mcp_dispatched"] is False
    else:
        assert stopped["provenance"]["action_rejections"] == []


async def test_completed_topology_is_removed_from_catalog_but_distinct_queries_remain_available():
    provider = CountingScript(
        [
            DiagnosticRequest(name="search_logs", q="narrow"),
            DiagnosticRequest(name="search_logs", q=""),
            DiagnosticRequest(name="query_metrics", metric="latency"),
        ]
    )
    client = ValidatingScriptClient(
        rows={
            ("get_service_topology", None): [evidence("TOPOLOGY-001", "topology", "Bounded topology")],
            ("search_logs", ""): [evidence("LOG-001", "log", "Retrieved broader log")],
            ("query_metrics", None): [evidence("METRIC-001", "metric", "Retrieved metric")],
        }
    )
    client.schemas = [{"name": name} for name in ("get_service_topology", "search_logs", "query_metrics")]
    snapshots = []
    result = await collect_script(client, provider, snapshots)
    assert all(
        {item["name"] for item in catalog} == {"search_logs", "query_metrics"}
        for catalog in provider.catalogs
    )
    assert [name for name, _ in client.calls] == [
        *(name for name, _ in INITIAL_CALLS), "search_logs", "search_logs", "query_metrics"
    ]
    assert provider.decision_calls == 4
    assert provider.assessment_calls == 1
    assert "TOPOLOGY-001" in {item["id"] for item in result["evidence"]}
    assert result["status"] == "complete"


async def test_failed_topology_remains_available_to_normal_recovery():
    provider = CountingScript([DiagnosticRequest(name="search_runbooks")])
    client = ValidatingScriptClient(fail="get_service_topology")
    client.schemas = [{"name": "get_service_topology"}, {"name": "search_logs"}]
    snapshots = []
    result = await collect_script(client, provider, snapshots, strict=False)
    assert [item["name"] for item in provider.catalogs[1]] == ["get_service_topology", "search_logs"]
    assert result["status"] == "complete"
    assert provider.decision_calls == 2
    assert provider.assessment_calls == 1


async def test_default_duplicate_recovery_keeps_transparent_deterministic_fallback():
    provider = CountingScript([DiagnosticRequest(name="query_metrics", metric="latency"), DiagnosticRequest(name="query_metrics", metric="latency")])
    client = ValidatingScriptClient()
    snapshots = []
    result = await collect_script(client, provider, snapshots, strict=False)
    assert result["status"] == "complete"
    assert provider.decision_calls == 2
    assert provider.assessment_calls == 0
    assert result["provider_proposal"] is None
    assert result["provenance"]["assessment_source"]["kind"] == "orchestrator_fallback"
    assert client.closed


async def test_strict_runtime_guard_retains_the_sanitized_parsed_action(monkeypatch):
    from creditops import investigator

    original = investigator.safe_arguments

    def reject_metric(name, arguments):
        if name == "query_metrics" and arguments:
            raise DiagnosticClientError("Runtime contract rejected parsed action")
        return original(name, arguments)

    monkeypatch.setattr(investigator, "safe_arguments", reject_metric)
    provider = CountingScript([DiagnosticRequest(name="query_metrics", metric="latency", service="quote-service")])
    client = ValidatingScriptClient()
    snapshots = []
    with pytest.raises(DiagnosticClientError):
        await collect_script(client, provider, snapshots)
    assert provider.decision_calls == 1
    assert provider.assessment_calls == 0
    assert client.calls == INITIAL_CALLS
    rejection = snapshots[-1]["provenance"]["action_rejections"][0]
    assert rejection["action"] == {
        "name": "query_metrics", "arguments": {"metric": "latency", "service": "quote-service"}
    }
    assert rejection["stage"] == "argument_guard"
    assert rejection["mcp_dispatched"] is False
    assert snapshots[-1]["validation_outcome"]["provider_response"] == "not_requested_due_to_guard_stop"
    assert snapshots[-1]["validation_outcome"]["assessment_source"] is None
    assert snapshots[-1]["assessment"] is None
    assert client.closed
