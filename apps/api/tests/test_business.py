"""A small event-derived fictional RFQ lifecycle, using the real relational store."""

import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from creditops.store import Store


@pytest.fixture(
    params=[
        "sqlite",
        pytest.param(
            "postgres",
            marks=pytest.mark.skipif(
                not os.getenv("CREDITOPS_TEST_DATABASE_URL"),
                reason="Disposable PostgreSQL URL not configured",
            ),
        ),
    ]
)
async def business_store(tmp_path, request):
    clock = [1000.0]
    url = (
        os.environ["CREDITOPS_TEST_DATABASE_URL"]
        if request.param == "postgres"
        else f"sqlite+aiosqlite:///{tmp_path / 'business.db'}"
    )
    store = Store(url, clock=lambda: clock[0])
    await store.initialize()
    yield store, clock
    await store.close()


def business_method(store):
    method = getattr(store, "business_impact", None)
    assert method is not None, "Event-derived fixed-income impact has not been implemented"
    return method


async def test_pricing_impact_counters_follow_events_and_keep_quote_expiry_separate(business_store):
    store, clock = business_store
    owner = str(uuid4())
    await store.run_scenario(owner, "kafka-pricing-lag")
    early = await business_method(store)(owner, "INC-DEMO-001")
    assert early.counters.rfqs_total == 1
    assert early.counters.rfqs_affected == 0
    clock[0] += 7
    later = await store.business_impact(owner, "INC-DEMO-001")
    assert later.counters.expired_quotes == 1
    assert later.counters.expired_rfqs == 0
    clock[0] += 8
    completed = await store.business_impact(owner, "INC-DEMO-001")
    assert completed.counters.rfqs_total == 2
    assert completed.counters.rfqs_affected == 2
    assert completed.counters.expired_rfqs == 2
    assert completed.counters.stale_quotes == 1
    assert completed.counters.unavailable_quotes == 1
    assert completed.requested_par_by_currency == {"USD": Decimal("1750000.00")}
    assert completed.model_dump(mode="json")["requested_par_by_currency"] == {"USD": "1750000.00"}
    assert all(request.order is None for request in completed.requests)
    assert len(await store.instruments()) == 3
    topology = await store.topology(owner)
    known_services = {service["id"] for service in topology["services"]}
    assert all(
        event.service in known_services for request in completed.requests for event in request.timeline
    )
    assert (await store.get_incident(owner, "INC-DEMO-001")).client_impact == completed.summary


async def test_fix_uncertainty_and_retransmission_never_create_a_failed_or_executed_order(business_store):
    store, clock = business_store
    owner = str(uuid4())
    await store.run_scenario(owner, "fix-connectivity")
    clock[0] += 5
    pending = await business_method(store)(owner, "INC-DEMO-002")
    assert pending.counters.pending_acknowledgements == 2
    clock[0] += 10
    uncertain = await store.business_impact(owner, "INC-DEMO-002")
    assert uncertain.counters.unknown_acknowledgements == 2
    assert {request.order.status for request in uncertain.requests} == {"UNKNOWN"}
    assert len({request.order.id for request in uncertain.requests}) == 2
    assert all(request.order.acknowledged_at is None for request in uncertain.requests)
    assert any(
        event.data["event_type"] == "FIX_RETRANSMISSION"
        for request in uncertain.requests
        for event in request.timeline
    )
    assert all(request.quote.status == "ACCEPTED" for request in uncertain.requests)
    assert all(request.rfq.status == "COMPLETED" for request in uncertain.requests)


async def test_database_timeouts_identify_processing_stage_without_claiming_deployment_cause(business_store):
    store, clock = business_store
    owner = str(uuid4())
    await store.run_scenario(owner, "db-pool-exhaustion")
    clock[0] += 9
    impact = await business_method(store)(owner, "INC-DEMO-003")
    assert impact.counters.processing_timeouts == 2
    assert all(request.processing_state == "TIMED_OUT" for request in impact.requests)
    assert all(request.order is None for request in impact.requests)
    assert "deployment caused" not in impact.summary.lower()
    assert any(
        event.data.get("processing_stage") == "DB_WAIT"
        for request in impact.requests
        for event in request.timeline
    )


async def test_business_events_are_session_scoped_and_frozen_at_original_observation_times(business_store):
    from creditops.tools import DiagnosticTools

    store, clock = business_store
    owner, other = str(uuid4()), str(uuid4())
    await store.run_scenario(owner, "fix-connectivity")
    clock[0] += 3
    freeze = getattr(store, "freeze_snapshot", None)
    assert freeze is not None, "Fixed investigation snapshot is missing"
    cutoff = await freeze(owner, "INC-DEMO-002")
    clock[0] += 20
    snapshot = await business_method(store)(owner, "INC-DEMO-002", as_of=cutoff)
    assert snapshot.counters.unknown_acknowledgements == 0
    assert all(
        datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
        <= datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
        for request in snapshot.requests
        for event in request.timeline
    )
    events = await DiagnosticTools(store, owner, as_of=cutoff).call(
        "search_logs", {"incident_id": "INC-DEMO-002", "limit": 50}
    )
    assert any(event.kind == "business_event" for event in events)
    assert not any(event.data.get("event_type") == "ACK_UNCERTAIN" for event in events)
    assert (
        await store.get_evidence(other, next(event.id for event in events if event.kind == "business_event"))
        is None
    )
    assert await store.business_impact(other, "INC-DEMO-002") is None


async def test_future_dated_evidence_is_excluded_even_when_reveal_time_is_zero(business_store):
    from creditops.db import EvidenceRow, LogRow

    store, clock = business_store
    owner = str(uuid4())
    async with store.sessions.begin() as session:
        from sqlalchemy import delete

        await session.execute(delete(LogRow).where(LogRow.evidence_id == "LOG-FUTURE-TEST"))
        await session.execute(delete(EvidenceRow).where(EvidenceRow.id == "LOG-FUTURE-TEST"))
    await store.run_scenario(owner, "kafka-pricing-lag")
    async with store.sessions.begin() as session:
        session.add(
            EvidenceRow(
                id="LOG-FUTURE-TEST",
                kind="log",
                service="pricing-service",
                timestamp="2026-10-09T16:00:00Z",
                summary="Unavailable future observation",
                data={"severity": "WARN", "message": "future"},
                incident_id="INC-DEMO-001",
                reveal_seconds=0,
            )
        )
        await session.flush()
        session.add(LogRow(evidence_id="LOG-FUTURE-TEST", severity="WARN", trace_id=None, message="future"))
    assert await store.get_evidence(owner, "LOG-FUTURE-TEST") is None
    with pytest.raises(ValueError, match="future"):
        await business_method(store)(owner, "INC-DEMO-001", as_of="2026-10-09T16:00:00Z")


async def test_snapshot_hides_future_references_timeline_and_cannot_be_overridden(business_store):
    from creditops.db import EvidenceRow
    from creditops.tools import DiagnosticTools

    store, clock = business_store
    owner = str(uuid4())
    await store.run_scenario(owner, "kafka-pricing-lag")
    clock[0] += 3
    cutoff = await store.freeze_snapshot(owner, "INC-DEMO-001")
    tools = DiagnosticTools(store, owner, as_of=cutoff)
    async with store.sessions.begin() as session:
        from sqlalchemy import delete

        await session.execute(delete(EvidenceRow).where(EvidenceRow.id == "RUNBOOK-FUTURE-TEST"))
        session.add(
            EvidenceRow(
                id="RUNBOOK-FUTURE-TEST",
                kind="runbook",
                service="pricing-service",
                timestamp="2026-10-09T16:00:00Z",
                summary="future forbidden reference",
                data={"content": "unavailable"},
                incident_id=None,
                reveal_seconds=0,
            )
        )
    clock[0] += 20
    await store.run_scenario(owner, "fix-connectivity")
    incident = await store.get_incident(owner, "INC-DEMO-001", as_of=cutoff)
    assert all(
        datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
        <= datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
        for event in incident.timeline
    )
    history = await tools.call("search_runbooks", {"incident_id": "INC-DEMO-001", "limit": 50})
    assert history and all(row.id != "RUNBOOK-FUTURE-TEST" for row in history)
    metadata = (await tools.call("get_incident", {"incident_id": "INC-DEMO-001", "limit": 1}))[0]
    assert "scenario" not in metadata.data and "title" not in metadata.data
    assert "KAFKA-001-001" not in str(metadata.data)
    with pytest.raises(ValueError, match="override"):
        await tools.call("search_logs", {"incident_id": "INC-DEMO-001", "as_of": "2026-10-09T14:02:00Z"})


async def test_business_http_contract_filters_and_scopes_events(business_store):
    from creditops.main import create_app
    from httpx import ASGITransport, AsyncClient

    store, clock = business_store
    owner, other = {"X-Demo-Session": str(uuid4())}, {"X-Demo-Session": str(uuid4())}
    app = create_app(store=store, manage_store=False)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://synthetic.test") as client,
    ):
        instruments = (await client.get("/api/instruments")).json()
        assert len(instruments) == 3 and all(row["fictional"] for row in instruments)
        assert instruments[0]["coupon_percent"] == "4.250"
        await client.post("/api/demo/scenarios/fix-connectivity/run", headers=owner)
        assert (
            await client.get("/api/incidents/INC-DEMO-002/business-impact", headers=other)
        ).status_code == 404
        clock[0] += 5
        impact = (await client.get("/api/incidents/INC-DEMO-002/business-impact", headers=owner)).json()
        assert impact["counters"]["pending_acknowledgements"] == 2
        assert impact["requested_par_by_currency"] == {"USD": "1750000.00"}
        trace = impact["requests"][0]["rfq"]["trace_id"]
        records = (
            await client.get(
                "/api/diagnostics/search_logs",
                params={"incident_id": "INC-DEMO-002", "trace_id": trace, "limit": 50},
                headers=owner,
            )
        ).json()
        assert records and all(
            row["kind"] == "business_event" and row["data"]["trace_id"] == trace for row in records
        )
        assert (
            await client.get(
                "/api/incidents/INC-DEMO-002/business-impact",
                params={"as_of": "2026-10-09T16:00:00Z"},
                headers=owner,
            )
        ).status_code == 400
        assert (await client.get("/api/diagnostics/search_logs?limit=51", headers=owner)).status_code == 422


def test_rfq_rejects_naive_timestamp_and_invalid_expiry():
    from creditops.models import SyntheticRFQ

    data = dict(
        id="RFQ-DEMO-TEST",
        client_id="CLIENT-DEMO-001",
        instrument_id="BOND-DEMO-001",
        side="BUY",
        par_amount="1.00",
        currency="USD",
        requested_at="2026-10-09T14:00:00Z",
        expires_at="2026-10-09T14:01:00Z",
        trace_id="TRACE-DEMO-TEST",
    )
    with pytest.raises(ValueError, match="timezone"):
        SyntheticRFQ.model_validate({**data, "requested_at": "2026-10-09T14:00:00"})
    with pytest.raises(ValueError, match="expiry"):
        SyntheticRFQ.model_validate({**data, "expires_at": "2026-10-09T13:00:00Z"})


def test_acknowledgement_is_receipt_only_and_order_identity_is_immutable():
    from creditops.business import reduce_request
    from creditops.models import SyntheticRFQ

    rfq = SyntheticRFQ(
        id="RFQ-DEMO-TEST",
        client_id="CLIENT-DEMO-001",
        instrument_id="BOND-DEMO-001",
        side="BUY",
        par_amount="1000000.00",
        requested_at="2026-10-09T14:00:00Z",
        expires_at="2026-10-09T14:03:00Z",
        trace_id="TRACE-DEMO-TEST",
    )

    def event(n, kind, seconds, **data):
        return {
            "id": f"BUSINESS-TEST-{n:03}",
            "timestamp": f"2026-10-09T14:00:{seconds:02}Z",
            "event_type": kind,
            "data": data,
        }

    events = [
        event(1, "RFQ_REQUESTED", 0),
        event(
            2,
            "QUOTE_PUBLISHED",
            12,
            quote_id="QUOTE-DEMO-TEST",
            clean_price_per_100_par="99.875",
            source_timestamp="2026-10-09T14:00:12Z",
            quote_expires_at="2026-10-09T14:00:48Z",
        ),
        event(3, "QUOTE_ACCEPTED", 24, quote_id="QUOTE-DEMO-TEST"),
        event(4, "ORDER_SUBMITTED", 36, order_id="ORDER-DEMO-TEST", quote_id="QUOTE-DEMO-TEST"),
        event(5, "ACK_CONFIRMED", 40, order_id="ORDER-DEMO-TEST"),
    ]
    at = datetime(2026, 10, 9, 14, 1, tzinfo=UTC)
    result = reduce_request(rfq, events, at)
    assert result["order"].status == "ACKNOWLEDGED"
    assert "execution is not established" in result["order"].acknowledgement_meaning
    with pytest.raises(ValueError, match="identity"):
        reduce_request(rfq, events + [event(6, "FIX_RETRANSMISSION", 45, order_id="ORDER-DEMO-OTHER")], at)
    with pytest.raises(ValueError, match="One economic order"):
        reduce_request(rfq, events + [event(6, "ORDER_SUBMITTED", 45, order_id="ORDER-DEMO-OTHER")], at)
    with pytest.raises(ValueError, match="erase"):
        reduce_request(rfq, events + [event(6, "ACK_UNCERTAIN", 45, order_id="ORDER-DEMO-TEST")], at)


def test_lifecycle_rejects_acceptance_after_quote_expiry_and_decimal_floats():
    try:
        from creditops.business import reduce_request
        from creditops.models import SyntheticRFQ
    except ImportError:
        pytest.fail("Typed RFQ event state machine is missing")
    rfq = SyntheticRFQ(
        id="RFQ-DEMO-TEST",
        client_id="CLIENT-DEMO-001",
        instrument_id="BOND-DEMO-001",
        side="BUY",
        par_amount=Decimal("1000000.00"),
        currency="USD",
        requested_at=datetime(2026, 10, 9, 14, tzinfo=UTC),
        expires_at=datetime(2026, 10, 9, 14, 3, tzinfo=UTC),
        trace_id="TRACE-DEMO-TEST",
    )
    with pytest.raises(ValueError, match="decimal"):
        SyntheticRFQ.model_validate({**rfq.model_dump(), "par_amount": 1000000.01})
    events = [
        {
            "id": "BUSINESS-TEST-001",
            "timestamp": "2026-10-09T14:00:00Z",
            "event_type": "RFQ_REQUESTED",
            "data": {},
        },
        {
            "id": "BUSINESS-TEST-002",
            "timestamp": "2026-10-09T14:00:12Z",
            "event_type": "QUOTE_PUBLISHED",
            "data": {
                "quote_id": "QUOTE-DEMO-TEST",
                "clean_price_per_100_par": "99.875",
                "source_timestamp": "2026-10-09T14:00:12Z",
                "quote_expires_at": "2026-10-09T14:00:24Z",
            },
        },
        {
            "id": "BUSINESS-TEST-003",
            "timestamp": "2026-10-09T14:00:25Z",
            "event_type": "QUOTE_ACCEPTED",
            "data": {"quote_id": "QUOTE-DEMO-TEST"},
        },
    ]
    with pytest.raises(ValueError, match="expired quote"):
        reduce_request(rfq, events, datetime(2026, 10, 9, 14, 1, tzinfo=UTC))
