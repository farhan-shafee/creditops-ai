"""Scripted/offline providers prove control flow, not live-model quality."""

import pytest
from creditops.diagnostic_clients import DiagnosticClientError, DiagnosticConnectionError
from creditops.investigator import collect_adaptive_investigation
from creditops.providers import AdaptiveDecision, DeterministicProvider, DiagnosticRequest

CUTOFF = "2026-01-15T14:30:00Z"


def metric(name, value):
    return {
        "id": f"METRIC-{name}",
        "kind": "metric",
        "service": "pricing-service",
        "timestamp": CUTOFF,
        "summary": name,
        "data": {"metric": name, "value": value},
    }


class FakeStore:
    async def freeze_snapshot(self, session_id, incident_id):
        return CUTOFF

    async def get_incident(self, *args, **kwargs):
        return {
            "id": "INC-DEMO-001",
            "scenario": "hidden-label",
            "title": "Pretend DB cause",
            "summary": "Response latency",
            "started_at": CUTOFF,
            "client_impact": "Future answer leak",
            "affected_services": ["pricing-service"],
            "timeline": [],
        }


class ScriptedClient:
    transport = "scripted_test"
    schemas = []
    provenance = {"transport": transport, "snapshot_cutoff": CUTOFF, "tool_schema_verified": True}

    def __init__(self, metrics=None, fail=None):
        self.metrics = metrics or []
        self.fail = fail
        self.calls = []
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        if name == self.fail:
            raise DiagnosticClientError("Scripted missing telemetry")
        return self.metrics if name == "query_metrics" else []


async def run(client, provider=None, **kwargs):
    return await collect_adaptive_investigation(
        FakeStore(),
        "test",
        "INC-DEMO-001",
        provider or DeterministicProvider(),
        diagnostic_client=client,
        **kwargs,
    )


async def test_identical_symptoms_different_results_change_the_next_tool():
    kafka = ScriptedClient([metric("consumer_lag", 18000), metric("execution_ack_latency_ms", 80)])
    database = ScriptedClient([metric("db_pool_utilization", 99)])
    database.metrics[0]["data"]["unit"] = "%"
    await run(kafka)
    await run(database)
    assert [name for name, _ in kafka.calls][:5] == ["get_incident", "get_service_topology", "query_metrics", "search_logs", "inspect_kafka_lag"]
    assert [name for name, _ in database.calls][:5] == [
        "get_incident",
        "get_service_topology",
        "query_metrics",
        "search_logs",
        "inspect_database_health",
    ]
    assert kafka.closed and database.closed


async def test_empty_evidence_and_failed_tool_are_not_healthy_telemetry():
    result = await run(ScriptedClient(fail="query_metrics"))
    assert result["assessment"]["probable_failure_domain"] == "insufficient evidence"
    assert result["assessment"]["requires_human_review"]
    failed = next(step for step in result["steps"] if step["tool"] == "query_metrics")
    assert failed["status"] == "failed" and failed["error"] and not failed["evidence_ids"]


async def test_repeated_unproductive_calls_terminate_with_abstention():
    class Repeats(DeterministicProvider):
        name = "scripted_repeat"

        async def next_action(self, *args):
            return AdaptiveDecision(
                action="tool", request=DiagnosticRequest(name="query_metrics", service=None)
            ), {}

    adapter = ScriptedClient()
    result = await run(adapter, Repeats())
    assert len(adapter.calls) == 4
    assert result["assessment"]["probable_failure_domain"] == "insufficient evidence"
    assert "duplicate" in " ".join(result["assessment"]["limitations"]).lower()


async def test_connection_loss_cannot_report_completed_mcp_investigation():
    class Disconnected(ScriptedClient):
        transport = "mcp_stdio"

        async def call(self, name, arguments):
            raise DiagnosticConnectionError("MCP connection lost")

    client = Disconnected()
    with pytest.raises(DiagnosticConnectionError):
        await run(client)
    assert client.closed


async def test_provider_never_receives_generator_tags_or_future_impact():
    contexts = []

    class Capture(DeterministicProvider):
        async def next_action(self, incident, schemas, observations, evidence):
            contexts.append(incident)
            return await super().next_action(incident, schemas, observations, evidence)

    await run(ScriptedClient(), Capture())
    assert contexts
    assert all(
        not {"scenario", "title", "client_impact", "timeline"} & context.keys() for context in contexts
    )


async def test_invalid_provider_tool_arguments_are_rejected_before_call():
    class Invalid(DeterministicProvider):
        async def next_action(self, *args):
            return {
                "action": "tool",
                "request": {"name": "query_metrics", "service": None, "q": None, "incident_id": "another"},
            }, {}

    adapter = ScriptedClient()
    with pytest.raises(ValueError):
        await run(adapter, Invalid())
    assert [name for name, _ in adapter.calls] == ["get_incident", "get_service_topology", "query_metrics", "search_logs"]


async def test_cancellation_closes_diagnostics_and_never_completes():
    import asyncio

    started = asyncio.Event()

    class Waiting(ScriptedClient):
        async def call(self, name, arguments):
            started.set()
            await asyncio.Event().wait()

    client = Waiting()
    task = asyncio.create_task(run(client))
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert client.closed


async def test_provider_deadline_is_finite_and_closes_transport():
    import asyncio

    from creditops.settings import Settings

    class Waiting(DeterministicProvider):
        async def next_action(self, *args):
            await asyncio.Event().wait()

    client = ScriptedClient()
    with pytest.raises(TimeoutError):
        await run(client, Waiting(), limits=Settings(provider_timeout_seconds=0.1))
    assert client.closed


async def test_tool_deadline_is_visible_unknown_and_total_calls_are_bounded():
    import asyncio

    from creditops.settings import Settings

    class Slow(ScriptedClient):
        async def call(self, name, arguments):
            if name == "query_metrics":
                await asyncio.Event().wait()
            return await super().call(name, arguments)

    result = await run(Slow(), limits=Settings(diagnostic_timeout_seconds=0.1, max_diagnostic_calls=3))
    failed = [step for step in result["steps"] if step["status"] == "failed"]
    assert len(failed) == 1 and failed[0]["tool"] == "query_metrics"
    assert result["assessment"]["probable_failure_domain"] == "insufficient evidence"
    assert result["provenance"]["tool_calls"] == 3


@pytest.mark.parametrize(
    "data,expected",
    [
        ({"pool_utilization": 0.99, "unit": "%"}, "inspect_kafka_lag"),
        ({"pool_utilization": 0.99}, "inspect_database_health"),
        ({"metric": "db_pool_utilization", "value": 0.99, "unit": "ratio"}, "inspect_database_health"),
        ({"metric": "db_pool_utilization", "value": 0.99, "unit": "%"}, "inspect_kafka_lag"),
    ],
)
async def test_adaptive_pool_priority_respects_explicit_metric_units(data, expected):
    observation = metric("pool_utilization", 0)
    observation["data"] = data
    decision, _ = await DeterministicProvider().next_action(
        {}, [], [{"tool": "query_metrics"}], [observation]
    )
    assert decision.request.name == expected
