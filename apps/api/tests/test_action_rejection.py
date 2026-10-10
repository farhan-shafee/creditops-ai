"""Scripted local rejections are observable and never counted as MCP calls."""

import copy

import pytest
from creditops.diagnostic_clients import DiagnosticClientError
from creditops.investigator import collect_adaptive_investigation
from creditops.providers import AdaptiveDecision, DeterministicProvider, DiagnosticRequest
from test_adaptive_investigator import FakeStore, ScriptedClient

INITIAL_CALLS = [(name, {}) for name in ("get_incident", "get_service_topology", "query_metrics", "search_logs")]


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "query_metrics", "service": "quote-service", "q": "cpu utilization"},
        {"name": "get_service_topology", "service": "quote-service"},
        {"name": "search_logs", "q": "timeout", "session_id": "override"},
    ],
)
async def test_rejected_structured_action_has_local_provenance_without_mcp_dispatch(payload):
    class InvalidScript(DeterministicProvider):
        name = "scripted_invalid_action"

        async def next_action(self, *args):
            return {"action": "tool", "request": payload}, {}

    snapshots = []

    async def retain(result):
        snapshots.append(copy.deepcopy(result))

    client = ScriptedClient()
    with pytest.raises(ValueError):
        await collect_adaptive_investigation(
            FakeStore(), "test", "INC-DEMO-001", InvalidScript(), retain, diagnostic_client=client
        )
    result = snapshots[-1]
    assert result["status"] == "failed"
    assert client.calls == INITIAL_CALLS
    assert len(result["steps"]) == 4
    assert result["provenance"]["tool_calls"] == 4
    rejection = result["provenance"]["action_rejections"][0]
    assert rejection["stage"] == "parsed_decision"
    assert rejection["reason"] == "invalid_tool_contract"
    assert rejection["provider_turn"] == 1
    assert rejection["mcp_dispatched"] is False
    assert result["assessment"] is None and result["provider_proposal"] is None
    assert result["validation_outcome"]["status"] == "not_validated"
    assert client.closed


async def test_offline_http_guard_rejects_provider_transport_before_network():
    import httpx

    async with httpx.AsyncClient(trust_env=False) as client:
        with pytest.raises(AssertionError, match="Offline tests forbid external"):
            await client.post("https://api.openai.com/v1/responses", json={})


async def test_offline_guard_also_blocks_anthropic_sdk_transport(monkeypatch):
    import httpx2

    async def unexpected_network(*args, **kwargs):
        raise RuntimeError("Network pool must never be reached")

    async with httpx2.AsyncHTTPTransport() as transport:
        monkeypatch.setattr(transport._pool, "handle_async_request", unexpected_network)
        with pytest.raises(AssertionError, match="Offline tests forbid external"):
            await transport.handle_async_request(httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))


async def test_runtime_argument_guard_rejection_retains_local_provenance(monkeypatch):
    from creditops import investigator

    original = investigator.safe_arguments

    def guard(name, arguments):
        if name == "query_metrics" and arguments:
            raise DiagnosticClientError("Local execution guard rejected action")
        return original(name, arguments)

    monkeypatch.setattr(investigator, "safe_arguments", guard)

    class FilteredScript(DeterministicProvider):
        async def next_action(self, *args):
            return AdaptiveDecision(action="tool", request=DiagnosticRequest(name="query_metrics", metric="latency")), {}

    snapshots = []

    async def retain(result):
        snapshots.append(copy.deepcopy(result))

    client = ScriptedClient()
    with pytest.raises(DiagnosticClientError):
        await collect_adaptive_investigation(
            FakeStore(), "test", "INC-DEMO-001", FilteredScript(), retain, diagnostic_client=client
        )
    result = snapshots[-1]
    assert client.calls == INITIAL_CALLS
    assert result["provenance"]["tool_calls"] == 4
    assert result["provenance"]["action_rejections"] == [
        {"stage": "argument_guard", "reason": "invalid_tool_contract", "provider_turn": 1, "mcp_dispatched": False}
    ]
    assert [step["safe_arguments"] for step in result["steps"] if step["tool"] == "query_metrics"] == [{}]
    assert result["assessment"] is None


async def test_provider_parse_error_is_recorded_before_any_diagnostic_dispatch():
    from pydantic import ValidationError

    class MalformedScript(DeterministicProvider):
        name = "scripted_malformed_output"

        async def next_action(self, *args):
            raise ValidationError.from_exception_data(
                "AdaptiveDecision", [{"type": "extra_forbidden", "loc": ("q",), "input": "invalid"}]
            )

    snapshots = []

    async def retain(result):
        snapshots.append(copy.deepcopy(result))

    client = ScriptedClient()
    with pytest.raises(ValidationError):
        await collect_adaptive_investigation(
            FakeStore(), "test", "INC-DEMO-001", MalformedScript(), retain, diagnostic_client=client
        )
    result = snapshots[-1]
    assert result["provenance"]["action_rejections"] == [
        {"stage": "provider_structured_output", "reason": "invalid_tool_contract", "provider_turn": 1, "mcp_dispatched": False}
    ]
    assert client.calls == INITIAL_CALLS
    assert result["provenance"]["tool_calls"] == 4
    assert result["assessment"] is None
