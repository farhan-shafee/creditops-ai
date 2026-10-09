"""Contract tests using a real async SQLite database, with a controllable simulator clock."""

from importlib.util import find_spec
from uuid import uuid4

import pytest


def backend_module():
    try:
        implemented = find_spec("creditops.store")
    except ModuleNotFoundError:
        implemented = None
    assert implemented is not None, "Persisted diagnostic backend has not been implemented"
    from creditops.store import Store

    return Store


@pytest.fixture
async def store(tmp_path):
    Store = backend_module()
    instant = [1000.0]
    database = Store(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", clock=lambda: instant[0])
    from sqlalchemy import event

    @event.listens_for(database.engine.sync_engine, "connect")
    def enable_integrity(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    await database.initialize()
    yield database, instant
    await database.close()


async def test_demo_runs_are_isolated_and_progressively_reveal_telemetry(store):
    database, instant = store
    first, other = str(uuid4()), str(uuid4())
    incident = await database.run_scenario(first, "kafka-pricing-lag")
    assert incident.id == "INC-DEMO-001"
    assert await database.list_incidents(other) == []
    initial = await database.evidence(first, incident_id=incident.id, kind="log", limit=50)
    assert len(initial) == 1
    instant[0] += 30
    later = await database.evidence(first, incident_id=incident.id, kind="log", limit=50)
    assert len(later) > len(initial)
    assert any("stale" in e.summary.lower() for e in later)
    assert await database.get_evidence(other, later[-1].id) is None
    await database.reset_scenario(first, "kafka-pricing-lag")
    assert await database.list_incidents(first) == []


async def test_evidence_search_applies_combined_filters_and_pagination(store):
    database, instant = store
    session = str(uuid4())
    await database.run_scenario(session, "db-pool-exhaustion")
    instant[0] += 30
    records = await database.evidence(
        session,
        incident_id="INC-DEMO-003",
        kind="log",
        service="quote-service",
        severity="ERROR",
        q="pool",
        limit=1,
    )
    assert len(records) == 1
    assert records[0].data["severity"] == "ERROR"
    assert "pool" in records[0].summary.lower()
    assert await database.evidence(session, kind="log", q="nonexistent-error-xyz") == []


async def test_investigation_persists_and_never_crosses_session_scope(store):
    database, _ = store
    first, other = str(uuid4()), str(uuid4())
    trace = {
        "id": "INV-DEMO-TEST",
        "incident_id": "INC-DEMO-001",
        "mode": "REPLAY",
        "status": "complete",
        "provider": "deterministic",
        "created_at": "2026-10-09T14:00:00Z",
        "steps": [],
        "evidence": [],
        "assessment": None,
        "error": None,
        "usage": {},
    }
    await database.save_investigation(first, trace)
    assert (await database.get_investigation(first, trace["id"]))["status"] == "complete"
    assert await database.get_investigation(other, trace["id"]) is None
    assert await database.investigation_count(first) == 1


async def test_diagnostic_tools_reject_mutation_and_unbounded_inputs(store):
    from creditops.tools import DiagnosticTools

    database, instant = store
    session = str(uuid4())
    await database.run_scenario(session, "fix-connectivity")
    instant[0] += 30
    tools = DiagnosticTools(database, session)
    with pytest.raises(ValueError, match="allowlist"):
        await tools.call("restart_service", {"service": "fix-gateway"})
    with pytest.raises(ValueError):
        await tools.call("search_logs", {"limit": 5000})
    rows = await tools.call("inspect_fix_session", {"incident_id": "INC-DEMO-002", "limit": 2})
    assert len(rows) == 2
    assert all(row.kind == "fix" for row in rows)


async def test_seed_contains_fifteen_distinct_incidents_and_no_labels_in_diagnostics(store):
    from creditops.tools import DiagnosticTools

    database, _ = store
    catalog = await database.case_catalog()
    assert len(catalog) == 15
    assert len({case["id"] for case in catalog}) == 15
    session = str(uuid4())
    await database.activate_case(session, "INC-EVAL-015")
    records = await DiagnosticTools(database, session).call("search_logs", {"incident_id": "INC-EVAL-015"})
    assert records
    assert all("ground_truth" not in str(row.model_dump()) for row in records)


async def test_http_api_filters_and_enforces_demo_session(store):
    from creditops.main import create_app
    from fastapi.testclient import TestClient

    database, _ = store
    with TestClient(create_app(store=database, manage_store=False)) as client:
        first = {"X-Demo-Session": str(uuid4())}
        other = {"X-Demo-Session": str(uuid4())}
        assert client.get("/health").status_code == 200
        assert client.post("/api/demo/scenarios/kafka-pricing-lag/run", headers=first).status_code == 200
        assert client.get("/api/incidents", headers=other).json() == []
        assert client.get("/api/logs/search?limit=501", headers=first).status_code == 422
        assert client.get("/api/incidents", headers={"X-Demo-Session": "invalid"}).status_code == 400
        assert len(client.get("/api/scenarios").json()) == 3
        topology = client.get("/api/services/topology", headers=first).json()
        assert len(topology["services"]) == 10
        assert topology["dependencies"]
        assert client.get("/api/diagnostics/restart_service", headers=first).status_code == 400
        diagnostic = client.get(
            "/api/diagnostics/get_incident?incident_id=INC-DEMO-001&limit=20", headers=first
        )
        assert diagnostic.status_code == 200
        assert diagnostic.json()[0]["id"] == "INC-DEMO-001"


async def test_metrics_include_progressive_series_and_preserve_primary_diagnostic_evidence(store):
    from creditops.tools import DiagnosticTools

    database, instant = store
    session = str(uuid4())
    await database.run_scenario(session, "kafka-pricing-lag")
    instant[0] += 30
    series = await database.metrics(
        session, incident_id="INC-DEMO-001", service="quote-service", metric="request_latency_p95_ms"
    )
    assert len(series[0].points) >= 6
    evidence = await DiagnosticTools(database, session).call(
        "query_metrics", {"incident_id": "INC-DEMO-001", "limit": 50}
    )
    assert len(evidence) <= 50
    assert {"METRIC-001-LAG", "METRIC-001-AGE"} <= {record.id for record in evidence}


async def test_api_protects_live_calls_limits_bodies_and_rate_budgets(store):
    from creditops.main import create_app
    from creditops.settings import Settings
    from fastapi.testclient import TestClient

    database, _ = store
    config = Settings(admin_api_key="synthetic-local-admin", max_investigations_per_window=1)
    with TestClient(create_app(store=database, manage_store=False, settings=config)) as client:
        headers = {"X-Demo-Session": str(uuid4())}
        client.post("/api/demo/scenarios/fix-connectivity/run", headers=headers)
        body = {"incident_id": "INC-DEMO-002", "mode": "LIVE_AI"}
        assert client.post("/api/investigations", headers=headers, json=body).status_code == 403
        assert client.post("/api/investigations", headers=headers, content="a" * 17000).status_code == 413
        good = {**headers, "Authorization": "Bearer synthetic-local-admin"}
        started = client.post("/api/investigations", headers=good, json=body)
        assert started.status_code == 200
        assert client.post("/api/investigations", headers=good, json=body).status_code == 429
        client.post("/api/demo/scenarios/fix-connectivity/reset", headers=headers)
        assert client.get(f"/api/investigations/{started.json()['id']}", headers=headers).status_code == 404


async def test_healthy_baseline_contains_real_seeded_sparkline_samples(store):
    database, _ = store
    series = await database.metrics(str(uuid4()), service="quote-service", metric="request_latency_p95_ms")
    assert len(series[0].points) >= 7
    assert len({point.evidence_id for point in series[0].points}) >= 7
    assert series[0].points[-1].value == 85


async def test_fractional_timestamp_bounds_exclude_earlier_whole_second_samples(store):
    from datetime import datetime

    database, _ = store
    owner = str(uuid4())
    await database.activate_case(owner, "INC-DEMO-001")
    records = await database.evidence(
        owner,
        kind="metric",
        service="quote-service",
        metric="request_latency_p95_ms",
        incident_id="INC-DEMO-001",
        start="2026-10-09T14:00:00.100000Z",
    )
    threshold = datetime.fromisoformat("2026-10-09T14:00:00.100000+00:00")
    assert records
    assert all(datetime.fromisoformat(row.timestamp.replace("Z", "+00:00")) >= threshold for row in records)
