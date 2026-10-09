"""Scripted, provider-free checks through the official MCP SDK and real backend.

The in-process MCP transport and ASGI HTTP transport perform the actual local
tool calls. These tests do not measure a live model's diagnostic capability.
"""

import copy
from uuid import uuid4

import httpx
import pytest
from creditops.diagnostic_clients import DiagnosticClientError, MCPDiagnosticClient
from creditops.investigator import collect_adaptive_investigation
from creditops.main import create_app
from creditops.providers import AdaptiveDecision, DeterministicProvider
from creditops.settings import Settings
from creditops.store import Store
from creditops_mcp.server import HttpDiagnosticClient, create_server
from mcp import Client

INCIDENT = "INC-DEMO-001"


@pytest.fixture
async def local_contract_mcp(tmp_path):
    database = Store(f"sqlite+aiosqlite:///{(tmp_path / 'contract.db').as_posix()}")
    await database.initialize()
    session = str(uuid4())
    await database.activate_case(session, INCIDENT)
    cutoff = await database.freeze_snapshot(session, INCIDENT)
    configuration = Settings(_env_file=None, embeddings_enabled=False, telemetry_mode="persisted")
    app = create_app(store=database, manage_store=False, settings=configuration)
    requests = []

    @app.middleware("http")
    async def capture_http(request, call_next):
        requests.append(
            {
                "path": request.url.path,
                "arguments": dict(request.query_params),
                "session": request.headers.get("x-demo-session"),
            }
        )
        return await call_next(request)

    def adapter():
        bridge = HttpDiagnosticClient(
            "http://offline-api",
            session,
            incident_id=INCIDENT,
            as_of=cutoff,
            transport=httpx.ASGITransport(app=app),
        )
        return MCPDiagnosticClient(session, INCIDENT, cutoff, client=Client(create_server(bridge)))

    yield database, session, cutoff, requests, adapter
    await database.close()


async def test_real_mcp_log_search_is_literal_case_insensitive_summary_and_data(local_contract_mcp):
    database, session, cutoff, requests, adapter = local_contract_mcp
    async with adapter() as diagnostics:
        lower = await diagnostics.call("search_logs", {"q": "rfq response"})
        upper = await diagnostics.call("search_logs", {"q": "RFQ RESPONSE"})
        assert lower and [item["id"] for item in lower] == [item["id"] for item in upper]
        assert all(
            "rfq response" in item["summary"].lower() or "rfq response" in str(item["data"]).lower()
            for item in lower
        )
        trace_id = next(item["data"]["trace_id"] for item in lower if item["data"].get("trace_id"))
        data_match = await diagnostics.call("search_logs", {"q": trace_id.upper()})
        assert data_match and any(item["data"].get("trace_id") == trace_id for item in data_match)
        assert await diagnostics.call("search_logs", {"q": "rfq response OR timeout"}) == []
        assert await diagnostics.call("search_logs", {"q": "rfq response%"}) == []
        broad = await diagnostics.call("search_logs", {})
        empty = await diagnostics.call("search_logs", {"q": ""})
        nullable = await diagnostics.call("search_logs", {"q": None})
        assert broad and broad == empty == nullable
        expected = await database.evidence(
            session, incident_id=INCIDENT, kind=("log", "business_event"), as_of=cutoff, limit=50
        )
        assert {item["id"] for item in broad} == {item.id for item in expected}
    assert all(request["session"] == session for request in requests)
    assert all(request["arguments"]["incident_id"] == INCIDENT for request in requests)
    assert all(request["arguments"]["as_of"] == cutoff for request in requests)
    assert all(request["arguments"]["limit"] == "50" for request in requests)


async def test_real_mcp_valid_metric_service_time_filters_reach_backend_unchanged(local_contract_mcp):
    database, session, cutoff, requests, adapter = local_contract_mcp
    candidates = await database.evidence(
        session, incident_id=INCIDENT, kind="metric", service="quote-service", as_of=cutoff, limit=50
    )
    assert candidates
    sample = candidates[0]
    filters = {
        "service": sample.service,
        "metric": sample.data["metric"],
        "start": sample.timestamp,
        "end": sample.timestamp,
    }
    decision = AdaptiveDecision.model_validate(
        {"action": "tool", "request": {"name": "query_metrics", **filters}}
    )
    arguments = decision.request.model_dump(exclude={"name"}, exclude_none=True)
    assert arguments == filters
    async with adapter() as diagnostics:
        returned = await diagnostics.call(decision.request.name, arguments)
    assert returned and all(item["service"] == sample.service for item in returned)
    assert all(item["data"]["metric"] == sample.data["metric"] for item in returned)
    assert all(item["timestamp"] == sample.timestamp for item in returned)
    assert requests == [
        {
            "path": "/api/diagnostics/query_metrics",
            "arguments": {**filters, "incident_id": INCIDENT, "limit": "50", "as_of": cutoff},
            "session": session,
        }
    ]


class ScriptedActions(DeterministicProvider):
    name = "scripted_contract_test"

    def __init__(self, requests):
        self.requests = iter(requests)
        self.observed = []

    async def next_action(self, incident, schemas, observations, evidence):
        self.observed.append(copy.deepcopy({"observations": observations, "evidence": evidence}))
        request = next(self.requests, None)
        return AdaptiveDecision.model_validate(
            {"action": "tool" if request is not None else "assess", "request": request}
        ), {}


async def test_empty_log_matches_remain_unknown_and_broader_typed_action_retrieves_evidence(
    local_contract_mcp,
):
    database, session, _, requests, adapter = local_contract_mcp
    empty = ScriptedActions([{"name": "search_logs", "q": "rfq response OR timeout"}])
    first = await collect_adaptive_investigation(
        database, session, INCIDENT, empty, diagnostic_client=adapter()
    )
    assert first["provenance"]["model_called"] is False
    assert first["assessment"]["probable_failure_domain"] == "insufficient evidence"
    assert first["assessment"]["requires_human_review"] is True
    log_step = next(step for step in first["steps"] if step["tool"] == "search_logs")
    assert log_step["status"] == "complete" and log_step["evidence_ids"] == []
    assert empty.observed[-1]["observations"][-1]["evidence_ids"] == []
    assert empty.observed[-1]["evidence"] == []

    broad = ScriptedActions(
        [{"name": "search_logs", "q": "rfq response OR timeout"}, {"name": "search_logs", "q": ""}]
    )
    second = await collect_adaptive_investigation(
        database, session, INCIDENT, broad, diagnostic_client=adapter()
    )
    log_steps = [step for step in second["steps"] if step["tool"] == "search_logs"]
    assert [step["status"] for step in log_steps] == ["complete", "complete"]
    assert log_steps[0]["evidence_ids"] == [] and log_steps[1]["evidence_ids"]
    assert broad.observed[1]["observations"][-1]["evidence_ids"] == []
    assert broad.observed[2]["evidence"]
    assert second["provenance"]["assessment_source"] == {
        "kind": "scripted_provider",
        "provider": "scripted_contract_test",
    }
    assert all(request["arguments"]["incident_id"] == INCIDENT for request in requests)


@pytest.mark.parametrize(
    "invalid",
    [{"q": "latency"}, {"metric": "not an identifier"}, {"start": "2026-10-09T14:00:00"}],
)
async def test_real_mcp_argument_rejection_never_reaches_backend(local_contract_mcp, invalid):
    _, _, _, requests, adapter = local_contract_mcp
    async with adapter() as diagnostics:
        with pytest.raises(DiagnosticClientError):
            await diagnostics.call("query_metrics", invalid)
    assert requests == []
