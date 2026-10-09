import copy
import json
from pathlib import Path
from uuid import uuid4

import pytest
from creditops.evaluation import run_evaluations
from creditops.investigator import (
    InvalidAssessment,
    collect_investigation,
    create_investigation,
    read_replay_artifact,
    run_investigation,
    stream_events,
    validate_assessment,
    write_replay_artifact,
)
from creditops.providers import DeterministicProvider, diagnose
from creditops.store import Store


@pytest.fixture
async def pipeline_store():
    directory = Path("artifacts/test-tmp")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"pipeline-{uuid4()}.db"
    store = Store(f"sqlite+aiosqlite:///{path.resolve().as_posix()}")
    await store.initialize()
    yield store
    await store.close()
    path.unlink(missing_ok=True)


@pytest.mark.parametrize(
    "identifier,domain",
    [
        ("INC-DEMO-001", "pricing-service / Kafka consumer backlog"),
        ("INC-DEMO-002", "FIX connectivity/session instability"),
        ("INC-DEMO-003", "database connection pool exhaustion following application change"),
    ],
)
async def test_pipeline_discovers_three_incidents_and_replays_exact_evidence(
    pipeline_store, identifier, domain
):
    await pipeline_store.activate_case("pipeline", identifier)
    result = await collect_investigation(pipeline_store, "pipeline", identifier, DeterministicProvider())
    assert result["assessment"]["probable_failure_domain"] == domain
    assert len(result["steps"]) == 11
    assert all(step["status"] == "complete" for step in result["steps"])
    assert not any(
        step["tool"] in {"execute_shell", "delete_record", "restart_service", "rollback_deployment"}
        for step in result["steps"]
    )
    assert set(result["assessment"]["supporting_evidence_ids"]) <= {item["id"] for item in result["evidence"]}
    destination = Path("artifacts/test-tmp") / str(uuid4())
    path = write_replay_artifact(result, destination)
    loaded = read_replay_artifact(identifier, destination)
    assert loaded["provenance"]["model_called"] is False
    assert loaded["investigation"]["assessment"] == result["assessment"]
    envelope = json.loads(path.read_text())
    envelope["payload"]["investigation"]["assessment"]["confidence"] = 0.99
    path.write_text(json.dumps(envelope))
    with pytest.raises(InvalidAssessment, match="integrity"):
        read_replay_artifact(identifier, destination)


async def test_tool_failure_is_visible_and_forces_escalation(pipeline_store, monkeypatch):
    from creditops.tools import DiagnosticTools

    original = DiagnosticTools.call

    async def fail_one(self, name, args):
        if name == "inspect_database_health":
            raise RuntimeError("synthetic dependency unavailable")
        return await original(self, name, args)

    monkeypatch.setattr(DiagnosticTools, "call", fail_one)
    await pipeline_store.activate_case("pipeline", "INC-DEMO-001")
    result = await collect_investigation(pipeline_store, "pipeline", "INC-DEMO-001", DeterministicProvider())
    assert any(step["status"] == "failed" for step in result["steps"])
    assert result["assessment"]["requires_human_review"]
    assert result["assessment"]["confidence"] <= 0.6


async def test_missing_live_key_persists_failure_and_sse_error(pipeline_store, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AI_PROVIDER", "openai")
    await pipeline_store.activate_case("pipeline", "INC-DEMO-001")
    row = await create_investigation(pipeline_store, "pipeline", "INC-DEMO-001", "LIVE_AI")
    await run_investigation(pipeline_store, "pipeline", row["id"])
    saved = await pipeline_store.get_investigation("pipeline", row["id"])
    assert saved["status"] == "failed"
    assert "OPENAI_API_KEY" in saved["error"]
    assert saved["assessment"] is None
    events = "".join([event async for event in stream_events(pipeline_store, "pipeline", row["id"])])
    assert "event: error" in events
    assert await pipeline_store.get_investigation("different-session", row["id"]) is None


async def test_full_evaluation_outputs_are_computed_from_all_cases(pipeline_store):
    destination = Path("artifacts/test-tmp") / str(uuid4())
    artifact = await run_evaluations(pipeline_store, output_dir=destination, generate_replay=False)
    assert artifact["case_count"] == 15
    assert artifact["live_ai_status"] == "not_run"
    assert len(artifact["algorithms"]) == 2
    pipeline = artifact["algorithms"][1]
    assert len(pipeline["results"]) == 15
    assert (
        pipeline["top1_accuracy"] == sum(item["score"]["top1_correct"] for item in pipeline["results"]) / 15
    )
    assert pipeline["invalid_evidence_citations"] == 0
    assert pipeline["total_tokens"] is None
    assert (destination / "latest.json").exists()
    assert (destination / "latest.md").exists()


async def test_conflicting_failure_domains_abstain(pipeline_store):
    from creditops.tools import DiagnosticTools

    await pipeline_store.activate_case("pipeline", "INC-DEMO-001")
    await pipeline_store.activate_case("pipeline", "INC-DEMO-002")
    tools = DiagnosticTools(pipeline_store, "pipeline")
    evidence = [
        item.model_dump()
        for identifier in ("INC-DEMO-001", "INC-DEMO-002")
        for tool in (
            "query_metrics",
            "search_logs",
            "inspect_kafka_lag",
            "inspect_fix_session",
            "inspect_database_health",
        )
        for item in await tools.call(tool, {"incident_id": identifier, "limit": 50})
    ]
    domain, _, confidence = diagnose(evidence)
    assert domain == "insufficient evidence"
    assert confidence < 0.6


async def test_unknown_prose_citation_is_rejected(pipeline_store):
    await pipeline_store.activate_case("pipeline", "INC-DEMO-001")
    result = await collect_investigation(pipeline_store, "pipeline", "INC-DEMO-001", DeterministicProvider())
    from creditops.models import Assessment

    assessment = Assessment.model_validate(copy.deepcopy(result["assessment"]))
    assessment.rca.probable_root_cause += " [KAFKA-INVENTED-999]"
    with pytest.raises(InvalidAssessment):
        validate_assessment(assessment, result["evidence"])


async def test_provider_never_receives_scenario_generator_tag(pipeline_store):
    observed = []

    class RecordingProvider(DeterministicProvider):
        async def plan(self, incident):
            observed.append(incident)
            return await super().plan(incident)

        async def assess(self, incident, evidence):
            observed.append(incident)
            return await super().assess(incident, evidence)

    await pipeline_store.activate_case("pipeline", "INC-DEMO-001")
    await collect_investigation(pipeline_store, "pipeline", "INC-DEMO-001", RecordingProvider())
    assert len(observed) == 2
    assert all("scenario" not in incident for incident in observed)
    assert all("ground_truth_failure_domain" not in incident for incident in observed)
