"""Recorded output, public boundaries and isolated snapshot replay regressions."""

import copy
import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest
from creditops import investigator
from creditops.settings import PROJECT_ROOT, Settings
from creditops.store import Store
from fastapi.testclient import TestClient


def recorded(directory):
    envelope = json.loads((PROJECT_ROOT / "data/replay/INC-DEMO-001.json").read_text())
    row = envelope["payload"]["investigation"]
    row["assessment"]["limitations"].append("Recorded historical caveat retained at generation.")
    row["provider_proposal"] = copy.deepcopy(row["assessment"])
    row["validation_outcome"] = {"status": "accepted", "changed_fields": []}
    row["provenance"]["showcase"] = {"title": "Recorded test"}
    envelope["sha256"] = investigator.artifact_digest(envelope["payload"])
    (directory / "INC-DEMO-001.json").write_text(json.dumps(envelope))
    return copy.deepcopy(row)


def test_reader_keeps_historical_assessment_proposal_and_validation(tmp_path):
    original = recorded(tmp_path)
    loaded = investigator.read_replay_artifact("INC-DEMO-001", tmp_path)["investigation"]
    for field in ("assessment", "provider_proposal", "validation_outcome"):
        assert loaded[field] == original[field]


def test_reader_rejects_missing_proposal_citation_even_with_valid_integrity(tmp_path):
    recorded(tmp_path)
    path = tmp_path / "INC-DEMO-001.json"
    envelope = json.loads(path.read_text())
    envelope["payload"]["investigation"]["provider_proposal"]["supporting_evidence_ids"].append("LOG-UNRETURNED")
    envelope["sha256"] = investigator.artifact_digest(envelope["payload"])
    path.write_text(json.dumps(envelope))
    with pytest.raises(investigator.InvalidAssessment, match="cited evidence"):
        investigator.read_replay_artifact("INC-DEMO-001", tmp_path)


@pytest.mark.parametrize("contents", ["not json", "{}", '{"payload": {"schema_version": 2}}'])
def test_malformed_recording_has_explicit_replay_error(tmp_path, contents):
    (tmp_path / "INC-DEMO-001.json").write_text(contents)
    with pytest.raises(investigator.InvalidAssessment, match="Replay artifact"):
        investigator.read_replay_artifact("INC-DEMO-001", tmp_path)


@pytest.fixture
async def database(tmp_path):
    store = Store(f"sqlite+aiosqlite:///{(tmp_path / 'showcase.db').as_posix()}")
    await store.initialize()
    yield store
    await store.close()


async def test_playback_uses_effective_replay_dir_and_exact_recorded_output(database, tmp_path, monkeypatch):
    original = recorded(tmp_path)
    session = str(uuid4())
    await database.run_scenario(session, "kafka-pricing-lag")
    configuration = Settings(_env_file=None, replay_dir=tmp_path, public_demo=True)

    def forbidden(*args, **kwargs):
        raise AssertionError("Replay must not instantiate a provider or MCP client")

    async def no_wait(_):
        return None

    monkeypatch.setattr(investigator, "create_provider", forbidden)
    monkeypatch.setattr(investigator, "MCPDiagnosticClient", forbidden)
    monkeypatch.setattr(investigator.asyncio, "sleep", no_wait)
    row = await investigator.create_investigation(database, session, "INC-DEMO-001", "REPLAY", configuration)
    await investigator.run_investigation(database, session, row["id"], configuration)
    loaded = await database.get_investigation(session, row["id"])
    assert loaded["status"] == "complete"
    for field in ("assessment", "provider_proposal", "validation_outcome", "evidence"):
        assert loaded[field] == original[field]
    assert loaded["provenance"]["showcase"]["title"] == "Recorded test"
    assert loaded["provenance"]["playback_model_calls"] == 0
    assert await database.get_investigation(str(uuid4()), row["id"]) is None


async def test_public_live_action_is_denied_with_valid_canary_credentials(database):
    from creditops.main import create_app

    configuration = Settings(_env_file=None, public_demo=True, admin_api_key="offline-canary-admin", openai_api_key="offline-canary-key")
    with TestClient(create_app(store=database, manage_store=False, settings=configuration)) as client:
        headers = {"X-Demo-Session": str(uuid4()), "Authorization": "Bearer offline-canary-admin"}
        client.post("/api/demo/scenarios/kafka-pricing-lag/run", headers=headers)
        response = client.post("/api/investigations", headers=headers, json={"incident_id": "INC-DEMO-001", "mode": "LIVE_AI"})
        assert response.status_code == 403
        assert "public" in response.json()["detail"].lower()


async def test_recorded_evidence_endpoint_uses_snapshot_and_session_scope(database, tmp_path):
    from creditops.main import create_app

    original = recorded(tmp_path)
    session = str(uuid4())
    row = copy.deepcopy(original)
    row.update(id="RECORDED-SNAPSHOT", mode="REPLAY")
    row["evidence"][0]["summary"] = "Historical snapshot text, independently of current store rows"
    await database.save_investigation(session, row)
    identifier = row["evidence"][0]["id"]
    config = Settings(_env_file=None, replay_dir=tmp_path)
    with TestClient(create_app(store=database, manage_store=False, settings=config)) as client:
        endpoint = f"/api/investigations/{row['id']}/evidence/{identifier}"
        response = client.get(endpoint, headers={"X-Demo-Session": session})
        assert response.status_code == 200
        assert response.json() == row["evidence"][0]
        assert client.get(endpoint, headers={"X-Demo-Session": str(uuid4())}).status_code == 404
        assert client.get(f"/api/investigations/{row['id']}/evidence/LOG-ABSENT", headers={"X-Demo-Session": session}).status_code == 404


def test_export_projects_only_allowlisted_receipts_and_preserves_recorded_text(tmp_path):
    path = PROJECT_ROOT / "scripts/export_showcase.py"
    assert path.is_file(), "The focused showcase exporter is not implemented"
    spec = importlib.util.spec_from_file_location("showcase_export", path)
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    source = tmp_path / "sources"
    source.mkdir()
    original = recorded(tmp_path)
    for index, (filename, experiment) in enumerate(exporter.SELECTED_RECEIPTS, start=1):
        result = copy.deepcopy(original)
        result["incident_id"] = f"INC-DEMO-{index:03d}"
        result["provenance"].update(session_id="private-session", source_commit="abc123", workflow="evidence_first_v1")
        result["provider_calls"] = [{"schema": "AvailableAdaptiveDecision", "status": "success", "structured_output": {"action": "assess", "request": None}, "request_id": "private-request", "response_id": "private-response", "requested_model": "recorded-model", "request_started": True}]
        receipt = {"execution": "COMPLETED_APPROVED_CASES", "experiment_id": experiment, "started_at": "2026-10-10T10:00:00Z", "ended_at": "2026-10-10T10:00:25Z", "duration_seconds": 25, "configuration": {"source_commit": "abc123", "model": "recorded-model", "local_resources": {"absolute_path": "C:/private"}}, "results": [result], "approval": "private approval"}
        (source / filename).write_text(json.dumps(receipt))
    (source / "unselected-receipt.json").write_text("must never be loaded")
    destination = tmp_path / "export"
    exporter.export_showcase(source, destination, exported_at="2026-10-11T00:00:00Z")
    envelope = json.loads((destination / "INC-DEMO-001.json").read_text())
    result = envelope["payload"]["investigation"]
    for field in ("assessment", "provider_proposal", "validation_outcome", "evidence"):
        assert result[field] == original[field]
    assert result["provenance"]["showcase"]["original_duration_seconds"] == 25
    assert envelope["payload"]["generated_at"] == "2026-10-10T10:00:00Z"
    assert result["provenance"]["showcase"]["exported_at"] == "2026-10-11T00:00:00Z"
    published = " ".join(p.read_text() for p in destination.glob("*.json"))
    for removed in ("private-session", "private-request", "private-response", "C:/private", "private approval"):
        assert removed not in published
    assert len(json.loads((destination / "manifest.json").read_text())["selected_recordings"]) == 3


async def test_selected_results_are_added_without_replacing_legacy_benchmark(database, tmp_path):
    from creditops.main import create_app

    evaluation = tmp_path / "artifacts/eval"
    evaluation.mkdir(parents=True)
    (evaluation / "latest.json").write_text(json.dumps({"case_count": 15, "legacy_marker": "retained"}))
    replay = tmp_path / "replay"
    replay.mkdir()
    for path in (PROJECT_ROOT / "data/showcase").glob("*.json"):
        (replay / path.name).write_bytes(path.read_bytes())
    config = Settings(_env_file=None, project_root=tmp_path, replay_dir=replay)
    with TestClient(create_app(store=database, manage_store=False, settings=config)) as client:
        response = client.get("/api/evaluations/latest")
        assert response.status_code == 200
        assert response.json()["legacy_marker"] == "retained"
        assert response.json()["selected_recordings"][0]["title"] == "Pricing backlog"
        (replay / "manifest.json").write_text("malformed")
        assert client.get("/api/evaluations/latest").status_code == 503


@pytest.mark.parametrize("index,scenario", [(1, "kafka-pricing-lag"), (2, "fix-connectivity"), (3, "db-pool-exhaustion")])
async def test_packaged_recordings_complete_keyless_without_source_provider_or_mcp(
    database, tmp_path, monkeypatch, index, scenario
):
    directory = tmp_path / "packaged"
    directory.mkdir()
    for path in (PROJECT_ROOT / "data/showcase").glob("*.json"):
        (directory / path.name).write_bytes(path.read_bytes())
    original_open = Path.open

    def isolated_open(path, *args, **kwargs):
        if "live-verification" in path.parts:
            raise AssertionError("Playback must not access the private source receipt directory")
        return original_open(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("Playback must not instantiate a provider or diagnostic client")

    async def no_wait(_):
        return None

    monkeypatch.setattr(Path, "open", isolated_open)
    monkeypatch.setattr(investigator, "create_provider", forbidden)
    monkeypatch.setattr(investigator, "DeterministicProvider", forbidden)
    monkeypatch.setattr(investigator, "MCPDiagnosticClient", forbidden)
    monkeypatch.setattr(investigator, "DirectDiagnosticClient", forbidden)
    monkeypatch.setattr(investigator.asyncio, "sleep", no_wait)
    identifier = f"INC-DEMO-{index:03d}"
    artifact = json.loads((directory / f"{identifier}.json").read_text())["payload"]["investigation"]
    configuration = Settings(_env_file=None, replay_dir=directory, public_demo=True, openai_api_key=None, anthropic_api_key=None, admin_api_key=None)
    owner = str(uuid4())
    await database.run_scenario(owner, scenario)
    row = await investigator.create_investigation(database, owner, identifier, "REPLAY", configuration)
    await investigator.run_investigation(database, owner, row["id"], configuration)
    saved = await database.get_investigation(owner, row["id"])
    assert saved["status"] == "complete"
    for field in ("assessment", "provider_proposal", "validation_outcome", "evidence", "provider_calls"):
        assert saved[field] == artifact[field]
    assert [step["tool"] for step in saved["steps"][:4]] == ["get_incident", "get_service_topology", "query_metrics", "search_logs"]
    assert all(step["selected_by"] == "application_runbook" for step in saved["steps"][:4])
    assert saved["steps"][-1]["selected_by"] == "validator"
    assert [call["schema"] for call in saved["provider_calls"]] == ["AvailableAdaptiveDecision", "Assessment"]
    assert saved["provider_calls"][0]["structured_output"]["action"] == "assess"
    assert saved["provenance"]["playback_model_calls"] == 0
    assert saved["provenance"]["showcase"]["sample_end"] == "2026-10-09T14:02:24Z"
    assert await database.get_investigation(str(uuid4()), row["id"]) is None
    assert len(investigator.read_selected_recordings(directory)) == 3


async def test_failed_replay_keeps_honest_artifact_error_without_provider_fallback(database, tmp_path, monkeypatch):
    (tmp_path / "INC-DEMO-001.json").write_text("malformed")
    session = str(uuid4())
    await database.run_scenario(session, "kafka-pricing-lag")

    def forbidden(*args, **kwargs):
        raise AssertionError("A failed replay must not fall back to a provider")

    monkeypatch.setattr(investigator, "create_provider", forbidden)
    configuration = Settings(_env_file=None, replay_dir=tmp_path)
    row = await investigator.create_investigation(database, session, "INC-DEMO-001", "REPLAY", configuration)
    await investigator.run_investigation(database, session, row["id"], configuration)
    saved = await database.get_investigation(session, row["id"])
    assert saved["status"] == "failed"
    assert "Replay artifact" in saved["error"]
    assert saved["assessment"] is None


async def test_public_embedding_index_is_denied_even_with_canary_credentials(monkeypatch):
    from creditops import embeddings

    settings = Settings(_env_file=None, public_demo=True, openai_api_key="offline-canary-key", embedding_model="offline-canary-model", embeddings_enabled=True)
    monkeypatch.setattr(embeddings, "get_settings", lambda: settings)

    class UnavailableIndex:
        database_url = "postgresql+asyncpg://offline-canary@localhost/synthetic"

        async def evidence(self, *args, **kwargs):
            raise AssertionError("Public indexing must not open database rows or a provider")

    with pytest.raises(ValueError, match="public"):
        await embeddings.index_references(UnavailableIndex())


@pytest.mark.parametrize("field,value", [("original_duration_seconds", 1), ("proposed_domain", "invented diagnosis"), ("model_selected_diagnostic_count", 4), ("source_commit", "invented commit"), ("replay_payload_sha256", None)])
def test_showcase_manifest_rejects_summary_claims_that_disagree_with_recording(tmp_path, field, value):
    for path in (PROJECT_ROOT / "data/showcase").glob("*.json"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    path = tmp_path / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["selected_recordings"][0][field] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(investigator.InvalidAssessment, match="Showcase"):
        investigator.read_selected_recordings(tmp_path)


def test_missing_showcase_manifest_is_an_honest_error(tmp_path):
    for path in (PROJECT_ROOT / "data/showcase").glob("INC-DEMO-*.json"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    with pytest.raises(investigator.InvalidAssessment, match="manifest"):
        investigator.read_selected_recordings(tmp_path)
