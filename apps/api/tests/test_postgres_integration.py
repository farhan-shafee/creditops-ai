"""Run against a disposable migrated PostgreSQL database with CREDITOPS_TEST_DATABASE_URL."""

import os
from uuid import uuid4

import pytest
from creditops.store import Store
from creditops.tools import DiagnosticTools

DATABASE_URL = os.getenv("CREDITOPS_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="Disposable PostgreSQL integration URL not configured"
)


async def test_postgresql_persists_fifteen_cases_and_filters_real_relational_signals():
    store = Store(DATABASE_URL)
    await store.initialize()
    try:
        assert len(await store.case_catalog()) == 15
        owner, other = str(uuid4()), str(uuid4())
        await store.activate_case(owner, "INC-DEMO-003")
        assert await store.get_incident(other, "INC-DEMO-003") is None
        records = await DiagnosticTools(store, owner).call(
            "search_logs",
            {"incident_id": "INC-DEMO-003", "service": "quote-service", "severity": "ERROR", "q": "pool"},
        )
        assert [record.id for record in records] == ["LOG-003-002"]
        pool = await store.metrics(
            owner, service="quote-service", metric="db_pool_utilization", incident_id="INC-DEMO-003"
        )
        assert pool[0].points[-1].value == 100
        filtered = await store.metrics(
            owner,
            service="quote-service",
            metric="db_pool_utilization",
            incident_id="INC-DEMO-003",
            start="2026-10-09T14:00:00.100000Z",
            end="2026-10-09T14:03:00Z",
        )
        assert len(filtered[0].points) < len(pool[0].points)
        await store.reset_scenario(owner, "db-pool-exhaustion")
        assert await store.list_incidents(owner) == []
    finally:
        await store.close()


async def test_postgresql_trace_survives_engine_restart_with_session_scope():
    store = Store(DATABASE_URL)
    await store.initialize()
    owner, other = str(uuid4()), str(uuid4())
    id = str(uuid4())
    row = {
        "id": id,
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
    await store.save_investigation(owner, row)
    await store.close()
    reopened = Store(DATABASE_URL)
    try:
        assert (await reopened.get_investigation(owner, id))["status"] == "complete"
        assert await reopened.get_investigation(other, id) is None
    finally:
        await reopened.close()


async def test_postgresql_pgvector_index_orders_parameterized_cosine_distances():
    from creditops.embeddings import vector_literal
    from sqlalchemy import text

    store = Store(DATABASE_URL)
    try:
        async with store.sessions() as session:
            transaction = await session.begin()
            for id, vector in [
                ("RUNBOOK-001", [1.0] + [0.0] * 1535),
                ("RUNBOOK-002", [0.0, 1.0] + [0.0] * 1534),
            ]:
                await session.execute(
                    text(
                        "INSERT INTO reference_embeddings(evidence_id,kind,model,embedding) VALUES(:id,'runbook','synthetic-test-vector',CAST(:vector AS vector)) "
                        "ON CONFLICT(evidence_id) DO UPDATE SET embedding=EXCLUDED.embedding,model=EXCLUDED.model"
                    ),
                    {"id": id, "vector": vector_literal(vector)},
                )
            rows = await session.execute(
                text(
                    "SELECT evidence_id FROM reference_embeddings WHERE model='synthetic-test-vector' ORDER BY embedding <=> CAST(:vector AS vector) LIMIT 2"
                ),
                {"vector": vector_literal([1.0] + [0.0] * 1535)},
            )
            assert list(rows.scalars()) == ["RUNBOOK-001", "RUNBOOK-002"]
            await transaction.rollback()
    finally:
        await store.close()
