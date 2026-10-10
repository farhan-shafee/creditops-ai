"""Scripted evidence-first orchestration checks; no live-model capability claim."""

import copy

import pytest
from creditops.diagnostic_clients import DiagnosticClientError
from creditops.investigator import collect_adaptive_investigation
from creditops.providers import (
    AdaptiveDecision,
    DeterministicProvider,
    DiagnosticRequest,
    ProviderUnavailable,
    data_message,
)
from creditops.settings import Settings
from test_adaptive_investigator import CUTOFF, FakeStore, ScriptedClient, metric

INITIAL = ["get_incident", "get_service_topology", "query_metrics", "search_logs"]


class CaptureScript(DeterministicProvider):
    name = "scripted_evidence_first"

    def __init__(self, requests=()):
        self.requests = list(requests)
        self.decisions = []
        self.assessments = []

    async def next_action(self, incident, schemas, observations, evidence):
        self.decisions.append(copy.deepcopy((incident, schemas, observations, evidence)))
        if self.requests:
            return AdaptiveDecision(action="tool", request=self.requests.pop(0)), {}
        return AdaptiveDecision(action="assess", request=None), {}

    async def assess(self, incident, evidence):
        self.assessments.append(copy.deepcopy((incident, evidence)))
        return await super().assess(incident, evidence)


class PacketClient(ScriptedClient):
    schemas = [{"name": name} for name in INITIAL[1:]]

    def __init__(self, *, fail=None, rows=None):
        super().__init__(fail=fail)
        self.rows = rows or {}

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        if name == self.fail:
            raise DiagnosticClientError("Scripted diagnostic failure")
        return self.rows.get(name, [])


async def collect(client, provider, *, strict=True, limits=None, snapshots=None, incident_id="INC-DEMO-001"):
    async def save(row):
        if snapshots is not None:
            snapshots.append(copy.deepcopy(row))

    return await collect_adaptive_investigation(
        FakeStore(), "test", incident_id, provider, save,
        diagnostic_client=client, limits=limits, stop_on_tool_error=strict,
    )


@pytest.mark.parametrize("incident_id", ["INC-DEMO-001", "INC-DEMO-002", "INC-DEMO-003"])
async def test_same_initial_packet_precedes_first_decision_and_is_application_selected(incident_id):
    provider = CaptureScript()
    client = PacketClient(rows={"query_metrics": [metric("consumer_lag", 20)]})
    result = await collect(client, provider, incident_id=incident_id)
    assert client.calls == [(name, {}) for name in INITIAL]
    assert [item["tool"] for item in provider.decisions[0][2]] == INITIAL
    assert all(step["selected_by"] == "application_runbook" for step in result["steps"][:4])
    assert all(step["provider_turn"] == 0 for step in result["steps"][:4])
    assert result["provenance"]["workflow"] == "evidence_first_v1"
    assert result["provenance"]["initial_diagnostics"] == INITIAL
    assert result["provenance"]["tool_calls"] == 4
    assert result["steps"][-1]["selected_by"] == "validator"
    assert len(provider.decisions) == len(provider.assessments) == 1
    assert client.closed


@pytest.mark.parametrize("failure", INITIAL)
async def test_every_initial_failure_stops_before_any_provider_request(failure):
    provider = CaptureScript()
    client = PacketClient(fail=failure)
    snapshots = []
    with pytest.raises(DiagnosticClientError):
        await collect(client, provider, snapshots=snapshots)
    assert provider.decisions == provider.assessments == []
    assert client.calls == [(name, {}) for name in INITIAL[: INITIAL.index(failure) + 1]]
    assert snapshots[-1]["status"] == "failed"
    assert snapshots[-1]["assessment"] is None
    assert snapshots[-1]["steps"][-1]["selected_by"] == "application_runbook"
    assert client.closed


async def test_initial_empties_do_not_force_guard_or_fallback_and_abstention_is_preserved():
    provider = CaptureScript()
    result = await collect(PacketClient(), provider, limits=Settings(max_no_progress_calls=1))
    assert len(provider.decisions) == len(provider.assessments) == 1
    assert result["status"] == "complete"
    assert result["assessment"]["probable_failure_domain"] == "insufficient evidence"
    assert result["provenance"]["assessment_source"]["kind"] == "scripted_provider"
    assert all(obs["status"] == "complete" and obs["evidence_ids"] == [] for obs in provider.decisions[0][2])


async def test_temporal_context_describes_actual_samples_and_incident_evidence_is_supplied():
    incident = {
        "id": "INC-DEMO-001", "kind": "incident", "service": "quote-service", "timestamp": CUTOFF,
        "summary": "Reported incident context", "data": {"timeline": [{"evidence_ids": ["NOT-FETCHED"]}]},
    }
    old = metric("db_pool_utilization", 35)
    old["timestamp"] = "2026-01-15T14:00:00Z"
    provider = CaptureScript()
    result = await collect(PacketClient(rows={"get_incident": [incident], "query_metrics": [old]}), provider)
    context, _, _, rows = provider.decisions[0]
    assert rows == [incident, old]
    assert provider.assessments[0][1] == rows
    assert "NOT-FETCHED" not in {row["id"] for row in rows}
    temporal = context["temporal_context"]
    assert temporal["snapshot_cutoff"] == CUTOFF
    assert temporal["investigation_window"] == {"start": CUTOFF, "end": CUTOFF}
    assert temporal["window_basis"] == "reported_incident_start_to_frozen_cutoff"
    assert temporal["initial_queries_apply_lower_time_bound"] is False
    coverage = temporal["returned_sample_coverage"]
    assert coverage["kind"] == "returned_samples_only"
    assert coverage["continuous_coverage"] is False
    assert coverage["total_samples"] == 2
    metric_coverage = next(item for item in coverage["by_kind"] if item["kind"] == "metric")
    assert metric_coverage["earliest_timestamp"] == metric_coverage["latest_timestamp"] == old["timestamp"]
    assert metric_coverage["count"] == metric_coverage["distinct_timestamps"] == 1
    assert result["provenance"]["snapshot_cutoff"] == CUTOFF


async def test_initial_calls_honor_a_smaller_total_budget_without_model_calls():
    provider = CaptureScript()
    client = PacketClient()
    snapshots = []
    with pytest.raises(DiagnosticClientError):
        await collect(client, provider, limits=Settings(max_diagnostic_calls=2), snapshots=snapshots)
    assert client.calls == [(name, {}) for name in INITIAL[:2]]
    assert provider.decisions == provider.assessments == []
    assert snapshots[-1]["provenance"]["guard_stop"] == "diagnostic_call_limit"
    assert snapshots[-1]["assessment"] is None


async def test_scripted_follow_up_attribution_and_completed_signatures_remain_visible():
    provider = CaptureScript([DiagnosticRequest(name="query_metrics", metric="latency")])
    client = PacketClient()
    result = await collect(client, provider)
    assert client.calls == [*((name, {}) for name in INITIAL), ("query_metrics", {"metric": "latency"})]
    assert result["steps"][4]["selected_by"] == "scripted_provider"
    assert [obs["safe_arguments"] for obs in provider.decisions[0][2]] == [{}, {}, {}, {}]
    assert "get_service_topology" not in {item["name"] for item in provider.decisions[0][1]}
    assert "query_metrics" in {item["name"] for item in provider.decisions[0][1]}


def test_model_packet_refuses_silent_evidence_list_truncation():
    rows = [{"id": f"ROW-{index}"} for index in range(101)]
    with pytest.raises(ProviderUnavailable, match="bounded model packet capacity"):
        data_message({"evidence": rows})
    assert "ROW-99" in data_message({"evidence": rows[:100]})


async def test_normal_initial_error_is_observed_before_permitted_follow_up():
    provider = CaptureScript([DiagnosticRequest(name="inspect_database_health")])
    client = PacketClient(fail="query_metrics")
    result = await collect(client, provider, strict=False)
    assert client.calls == [*((name, {}) for name in INITIAL), ("inspect_database_health", {})]
    assert provider.decisions[0][2][2]["status"] == "failed"
    assert len(provider.decisions) == 2 and len(provider.assessments) == 1
    assert result["status"] == "complete"
    assert result["assessment"]["requires_human_review"]
    assert result["assessment"]["probable_failure_domain"] == "insufficient evidence"


@pytest.mark.parametrize("record_source", [True, False])
async def test_evidence_first_recording_preserves_explicit_assessment_source_on_playback(
    tmp_path, monkeypatch, record_source
):
    from creditops import investigator

    trace = await collect(PacketClient(), CaptureScript())
    source = copy.deepcopy(trace["provenance"]["assessment_source"])
    if not record_source:
        trace["provenance"].pop("assessment_source")
    investigator.write_replay_artifact(trace, tmp_path)
    row = copy.deepcopy(trace)
    row.update(id="PLAYBACK-TEST", mode="REPLAY", status="running", steps=[], evidence=[], assessment=None, provenance={})

    class ReplayStore:
        async def get_investigation(self, *_):
            return row

        async def save_investigation(self, *args):
            assert args[-1] is row

    async def no_wait(_):
        pass

    monkeypatch.setattr(investigator, "Settings", lambda: Settings(replay_dir=tmp_path))
    monkeypatch.setattr(investigator.asyncio, "sleep", no_wait)
    await investigator.run_investigation(ReplayStore(), "test", row["id"])
    assert row["status"] == "complete"
    assert row["provenance"]["original_workflow"] == "evidence_first_v1"
    assert row["provenance"]["assessment_source"] == (source if record_source else None)
    assert row["provenance"]["playback_model_calls"] == 0
    assert all(step["selected_by"] == "application_runbook" for step in row["steps"][:4])


@pytest.mark.parametrize("condition", ["unrelated", "conflicting"])
async def test_unrelated_or_conflicting_initial_evidence_can_complete_with_scripted_abstention(condition):
    rows = [metric("unrelated_counter", 7)]
    if condition == "conflicting":
        rows = [metric("consumer_lag", 18000), metric("consumer_lag", 2)]
        rows[0]["id"] = "METRIC-EARLIER"
        rows[0]["timestamp"] = "2026-01-15T14:00:00Z"
        rows[1]["id"] = "METRIC-LATER"

    class AbstainingScript(CaptureScript):
        async def assess(self, incident, evidence):
            self.assessments.append(copy.deepcopy((incident, evidence)))
            # Explicit scripted abstention verifies orchestration permits it;
            # no domain answer is derived or required from these returned rows.
            proposal, usage = await DeterministicProvider().assess(incident, [])
            proposal.supporting_evidence_ids = [item["id"] for item in evidence]
            return proposal, usage

    provider = AbstainingScript()
    result = await collect(PacketClient(rows={"query_metrics": rows}), provider)
    assert provider.decisions[0][3] == rows
    assert len(provider.decisions) == len(provider.assessments) == 1
    assert result["status"] == "complete"
    assert result["provider_proposal"]["probable_failure_domain"] == "insufficient evidence"
    assert result["assessment"]["probable_failure_domain"] == "insufficient evidence"
    assert result["validation_outcome"]["status"] == "abstained"
