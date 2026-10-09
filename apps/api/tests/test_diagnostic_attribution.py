"""Expected causal boundaries specified before the second-pass diagnostic change."""

import pytest
from creditops.investigator import validate_assessment
from creditops.providers import DeterministicProvider


def pool_evidence():
    return [
        {
            "id": "METRIC-POOL",
            "kind": "metric",
            "service": "audit-service",
            "timestamp": "2026-01-15T14:30:00Z",
            "summary": "Pool utilization",
            "data": {"metric": "db_pool_utilization_pct", "value": 99, "unit": "%"},
        },
        {
            "id": "METRIC-WAIT",
            "kind": "metric",
            "service": "audit-service",
            "timestamp": "2026-01-15T14:30:00Z",
            "summary": "Connection wait",
            "data": {"metric": "pool_wait_ms", "value": 1900, "unit": "ms"},
        },
    ]


def deployment(service, timestamp):
    return {
        "id": "DEPLOY-CONTROL",
        "kind": "deployment",
        "service": service,
        "timestamp": timestamp,
        "summary": "Application release",
        "data": {"service": service, "version": "synthetic-2"},
    }


@pytest.mark.parametrize(
    "change",
    [
        None,
        deployment("notification-service", "2026-01-15T14:20:00Z"),
        deployment("audit-service", "2026-01-15T14:40:00Z"),
    ],
)
async def test_pool_exhaustion_without_a_relevant_preceding_change_has_no_trigger(change):
    evidence = pool_evidence() + ([change] if change else [])
    result, _ = await DeterministicProvider().assess({"title": "Untrusted incident title"}, evidence)
    assert result.probable_failure_domain == "database connection pool exhaustion"
    assert result.possible_triggers == []
    assert result.confirmed_cause is None
    assert "following application change" not in result.model_dump_json()
    assert result.unknowns


async def test_relevant_preceding_change_is_only_a_candidate_trigger():
    evidence = pool_evidence() + [deployment("audit-service", "2026-01-15T14:20:00Z")]
    result, _ = await DeterministicProvider().assess({}, evidence)
    assert result.probable_failure_domain == "database connection pool exhaustion"
    assert len(result.possible_triggers) == 1
    assert result.possible_triggers[0].status == "candidate"
    assert result.possible_triggers[0].evidence_ids == ["DEPLOY-CONTROL"]
    assert result.confirmed_cause is None


async def test_valid_evidence_ids_do_not_validate_an_unsupported_causal_sentence():
    evidence = pool_evidence()
    result, _ = await DeterministicProvider().assess({}, evidence)
    result.rca.probable_root_cause = "The application deployment caused exhaustion [METRIC-POOL]."
    result.incident_summary = result.rca.probable_root_cause
    checked = validate_assessment(result, evidence)
    assert "deployment caused" not in checked.model_dump_json()
    assert checked.confirmed_cause is None


async def test_cited_healthy_pool_source_contradicts_exhaustion_claim():
    evidence = pool_evidence()
    evidence[0]["data"]["value"] = 12
    result, _ = await DeterministicProvider().assess({}, evidence)
    result.probable_failure_domain = "database connection pool exhaustion"
    result.supporting_evidence_ids = [row["id"] for row in evidence]
    checked = validate_assessment(result, evidence)
    assert checked.probable_failure_domain == "insufficient evidence"
    assert checked.requires_human_review


async def test_pool_and_wait_signals_from_unrelated_services_do_not_corroborate():
    evidence = pool_evidence()
    evidence[1]["service"] = "another-service"
    result, _ = await DeterministicProvider().assess({}, evidence)
    assert result.probable_failure_domain == "insufficient evidence"


async def test_newer_healthy_observation_prevents_cherry_picking_old_saturation():
    evidence = pool_evidence()
    newer = {
        **evidence[0],
        "id": "METRIC-POOL-NEW",
        "timestamp": "2026-01-15T14:31:00Z",
        "data": {**evidence[0]["data"], "value": 12},
    }
    proposed, _ = await DeterministicProvider().assess({}, evidence)
    checked = validate_assessment(proposed, [*evidence, newer])
    assert checked.probable_failure_domain == "insufficient evidence"


async def test_deployment_after_old_failure_is_not_a_trigger_when_later_bad_samples_supersede_it():
    earlier = pool_evidence()
    latest = [{**row, "id": row["id"] + "-LATEST", "timestamp": "2026-01-15T14:40:00Z"} for row in earlier]
    evidence = [*earlier, deployment("audit-service", "2026-01-15T14:35:00Z"), *latest]
    result, _ = await DeterministicProvider().assess({}, evidence)
    assert result.probable_failure_domain == "database connection pool exhaustion"
    assert result.possible_triggers == []
    assert result.confirmed_cause is None


async def test_earlier_healthy_or_unrelated_observations_do_not_move_failure_onset():
    healthy = {
        **pool_evidence()[0],
        "id": "METRIC-POOL-HEALTHY",
        "timestamp": "2026-01-15T14:00:00Z",
        "data": {"metric": "db_pool_utilization_pct", "value": 12, "unit": "%"},
    }
    unrelated = {
        **pool_evidence()[0],
        "id": "METRIC-UNRELATED",
        "service": "notification-service",
        "timestamp": "2026-01-15T14:00:00Z",
    }
    evidence = [healthy, unrelated, *pool_evidence(), deployment("audit-service", "2026-01-15T14:20:00Z")]
    result, _ = await DeterministicProvider().assess({}, evidence)
    assert result.probable_failure_domain == "database connection pool exhaustion"
    assert len(result.possible_triggers) == 1
    assert result.possible_triggers[0].evidence_ids == ["DEPLOY-CONTROL"]


@pytest.mark.parametrize(
    "data,saturated",
    [
        ({"metric": "db_pool_utilization_pct", "value": 0.99, "unit": "%"}, False),
        ({"metric": "db_pool_utilization_pct", "value": 99, "unit": "%"}, True),
        ({"pool_utilization": 0.99}, True),
        ({"pool_utilization": 0.99, "unit": "%"}, False),
        ({"metric": "db_pool_utilization", "value": 0.99, "unit": "ratio"}, True),
        ({"metric": "db_pool_utilization", "value": 99, "unit": "unknown"}, False),
        ({"metric": "db_pool_utilization", "value": 99, "unit": {"kind": "%"}}, False),
        ({"metric": "db_pool_utilization", "value": 0.99}, False),
        ({"metric": "db_pool_utilization_pct", "value": 0.99, "unit": "ratio"}, False),
        ({"pool_utilization": 99}, False),
        ({"metric": "db_pool_utilization_pct", "value": 199, "unit": "%"}, False),
    ],
)
async def test_pool_utilization_respects_units_before_diagnosing_exhaustion(data, saturated):
    evidence = pool_evidence()
    evidence[0]["data"] = data
    result, _ = await DeterministicProvider().assess({}, evidence)
    assert result.probable_failure_domain == (
        "database connection pool exhaustion" if saturated else "insufficient evidence"
    )


@pytest.mark.parametrize(
    "data,saturated",
    [
        ({"metric": "cpu_percent", "value": 0.99, "unit": "%"}, False),
        ({"metric": "cpu_percent", "value": 99, "unit": "%"}, True),
        ({"cpu_utilization": 0.99}, True),
        ({"metric": "cpu_utilization", "value": 0.99, "unit": "ratio"}, True),
        ({"metric": "cpu_percent", "value": 99, "unit": "unknown"}, False),
        ({"metric": "cpu_percent", "value": 0.99, "unit": "ratio"}, False),
        ({"metric": "cpu_utilization", "value": 99}, False),
        ({"metric": "cpu_percent", "value": 199, "unit": "%"}, False),
    ],
)
async def test_cpu_utilization_respects_units_before_diagnosing_saturation(data, saturated):
    evidence = [
        {
            "id": "METRIC-CPU",
            "kind": "metric",
            "service": "quote-service",
            "timestamp": "2026-01-15T14:30:00Z",
            "summary": "CPU observation",
            "data": data,
        },
        {
            "id": "METRIC-LATENCY",
            "kind": "metric",
            "service": "quote-service",
            "timestamp": "2026-01-15T14:30:00Z",
            "summary": "Request latency",
            "data": {"metric": "request_latency_p95_ms", "value": 1000, "unit": "ms"},
        },
    ]
    result, _ = await DeterministicProvider().assess({}, evidence)
    assert result.probable_failure_domain == (
        "quote-service / CPU saturation" if saturated else "insufficient evidence"
    )
