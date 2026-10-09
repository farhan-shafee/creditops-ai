"""Offline proposals exercise observability, never claim live-model execution."""

import copy

import pytest
from creditops.investigator import InvalidAssessment, collect_adaptive_investigation, merge_usage
from creditops.providers import AdaptiveDecision, DeterministicProvider, DiagnosticRequest
from creditops.validation import validate_assessment_with_outcome

CUTOFF = "2026-01-15T14:30:00Z"
UNSUPPORTED_CAUSE = "The application deployment caused exhaustion [METRIC-POOL]."
EVIDENCE = [
    {
        "id": "METRIC-POOL",
        "kind": "metric",
        "service": "audit-service",
        "timestamp": CUTOFF,
        "summary": "Pool utilization",
        "data": {"metric": "db_pool_utilization_pct", "value": 99, "unit": "%"},
    },
    {
        "id": "METRIC-WAIT",
        "kind": "metric",
        "service": "audit-service",
        "timestamp": CUTOFF,
        "summary": "Connection wait",
        "data": {"metric": "pool_wait_ms", "value": 1900, "unit": "ms"},
    },
]


class LocalStore:
    async def freeze_snapshot(self, *_):
        return CUTOFF

    async def get_incident(self, *_, **__):
        return {"id": "INC-DEMO-003", "summary": "Delayed requests", "started_at": CUTOFF}


class LocalClient:
    transport = "scripted_offline"
    schemas = []
    provenance = {"transport": transport, "snapshot_cutoff": CUTOFF}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def call(self, name, _):
        return copy.deepcopy(EVIDENCE) if name == "query_metrics" else []


class ProposalProvider(DeterministicProvider):
    name = "scripted_proposal"

    def __init__(self, invalid=False):
        self.invalid = invalid
        self.proposed = None

    async def next_action(self, incident, schemas, observations, evidence):
        if evidence:
            return AdaptiveDecision(action="assess", request=None), {}
        return AdaptiveDecision(
            action="tool", request=DiagnosticRequest(name="query_metrics", service=None, q=None)
        ), {}

    async def assess(self, incident, evidence):
        proposal, usage = await super().assess(incident, evidence)
        proposal.rca.probable_root_cause = UNSUPPORTED_CAUSE
        proposal.recommended_next_steps = ["Review secret=do-not-persist-this before any action."]
        if self.invalid:
            proposal.supporting_evidence_ids.append("LOG-INVENTED")
        self.proposed = proposal
        return proposal, usage


async def investigate(provider, on_progress=None):
    return await collect_adaptive_investigation(
        LocalStore(), "offline", "INC-DEMO-003", provider, on_progress, diagnostic_client=LocalClient()
    )


async def test_original_proposal_survives_in_place_normalization_and_is_sanitized():
    provider = ProposalProvider()
    result = await investigate(provider)
    assert result["provider_proposal"]["rca"]["probable_root_cause"] == UNSUPPORTED_CAUSE
    assert "do-not-persist-this" not in str(result["provider_proposal"])
    assert "[REDACTED]" in str(result["provider_proposal"])
    assert "deployment caused" not in str(result["assessment"])
    assert provider.proposed.rca.probable_root_cause != UNSUPPORTED_CAUSE
    provider.proposed.rca.probable_root_cause = "Later mutation"
    assert result["provider_proposal"]["rca"]["probable_root_cause"] == UNSUPPORTED_CAUSE
    outcome = result["validation_outcome"]
    assert outcome["status"] == "accepted_normalized"
    assert outcome["diagnostic_domain_supported"] is True
    assert {change["field"]: change["reason"] for change in outcome["changed_fields"]}[
        "rca.probable_root_cause"
    ] == "known_domain_rule_normalization"
    assert outcome["original_claims_independently_verified"] is False
    assert outcome["assessment_source"]["provider"] == "scripted_proposal"
    assert result["provenance"]["model_called"] is False


async def test_invented_citation_is_retained_as_rejected_in_partial_result():
    updates = []

    async def save(result):
        updates.append(copy.deepcopy(result))

    with pytest.raises(InvalidAssessment):
        await investigate(ProposalProvider(invalid=True), save)
    partial = updates[-1]
    assert partial["status"] == "failed"
    assert partial["assessment"] is None
    assert "LOG-INVENTED" in partial["provider_proposal"]["supporting_evidence_ids"]
    assert partial["validation_outcome"]["status"] == "rejected"
    assert partial["validation_outcome"]["invalid_evidence_ids"] == ["LOG-INVENTED"]
    assert partial["validation_outcome"]["invalid_citation_count"] == 1
    assert partial["validation_outcome"]["rejected_fields"]


async def test_no_progress_fallback_is_not_attributed_to_the_scripted_provider():
    class Repeat(ProposalProvider):
        async def next_action(self, *_):
            return AdaptiveDecision(
                action="tool", request=DiagnosticRequest(name="query_metrics", service=None, q=None)
            ), {}

    result = await investigate(Repeat())
    assert result["provider_proposal"] is None
    assert result["validation_outcome"]["assessment_source"]["provider"] == "deterministic"
    assert result["validation_outcome"]["assessment_source"]["kind"] == "orchestrator_fallback"
    assert result["validation_outcome"]["status"] == "fallback_abstained"
    assert result["assessment"]["probable_failure_domain"] == "insufficient evidence"
    assert result["provenance"]["assessment_source"] == result["validation_outcome"]["assessment_source"]


def test_missing_usage_cannot_turn_a_partial_total_into_zero_cost_success():
    usage = merge_usage(
        [
            {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14, "estimated_cost_usd": 0.01},
            {"input_tokens": None, "output_tokens": None, "total_tokens": None, "estimated_cost_usd": None},
        ]
    )
    assert usage["input_tokens"] is None
    assert usage["estimated_cost_usd"] is None
    assert usage["known_subtotals"]["total_tokens"] == 14
    assert usage["usage_status"] == "partial_unknown"


async def test_unsupported_original_domain_is_recorded_as_downgraded():
    evidence = copy.deepcopy(EVIDENCE)
    evidence[0]["data"]["value"] = 12
    proposed, _ = await DeterministicProvider().assess({}, evidence)
    proposed.probable_failure_domain = "database connection pool exhaustion"
    proposed.supporting_evidence_ids = ["METRIC-POOL", "METRIC-WAIT"]
    final, original, outcome = validate_assessment_with_outcome(proposed, evidence)
    assert original["probable_failure_domain"] == "database connection pool exhaustion"
    assert outcome["status"] == "downgraded"
    assert outcome["diagnostic_domain_supported"] is False
    assert final.probable_failure_domain == "insufficient evidence"
    assert {item["field"]: item["reason"] for item in outcome["changed_fields"]}[
        "probable_failure_domain"
    ] == "unsupported_domain_abstention"


async def test_interrupted_provider_receipt_survives_the_investigator_failure():
    import asyncio

    from creditops.settings import Settings

    class InterruptedSDK(ProposalProvider):
        # Deliberate offline transport fixture; never persisted as an actual live run.
        execution_receipts = []

        async def next_action(self, *_):
            self.execution_receipts = [{"request_started": True, "status": "in_progress", "usage": {}}]
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.execution_receipts[0]["status"] = "cancelled"
                raise

    updates = []

    async def save(result):
        updates.append(copy.deepcopy(result))

    with pytest.raises(TimeoutError):
        await collect_adaptive_investigation(
            LocalStore(),
            "offline",
            "INC-DEMO-003",
            InterruptedSDK(),
            save,
            diagnostic_client=LocalClient(),
            limits=Settings(provider_timeout_seconds=0.1),
        )
    partial = updates[-1]
    assert partial["status"] == "failed"
    assert partial["provider_calls"][0]["status"] == "cancelled"
    assert partial["usage"]["estimated_cost_usd"] is None
    assert partial["usage"]["total_tokens"] is None
    assert partial["validation_outcome"]["provider_response"] == "cancelled"
    assert partial["provider_proposal"] is None


async def test_reused_provider_does_not_charge_previous_case_usage_to_the_new_case():
    class SharedOfflineSDK(ProposalProvider):
        def __init__(self):
            super().__init__()
            self.execution_receipts = [
                {
                    "request_started": True,
                    "status": "success",
                    "usage": {
                        "input_tokens": 10000,
                        "output_tokens": 10000,
                        "total_tokens": 20000,
                        "estimated_cost_usd": 2.0,
                    },
                }
            ]

        def record(self):
            self.execution_receipts.append(
                {
                    "request_started": True,
                    "status": "success",
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 2,
                        "total_tokens": 12,
                        "estimated_cost_usd": 0.01,
                    },
                }
            )

        async def next_action(self, *args):
            self.record()
            return await super().next_action(*args)

        async def assess(self, *args):
            self.record()
            return await super().assess(*args)

    provider = SharedOfflineSDK()
    result = await investigate(provider)
    assert len(result["provider_calls"]) == 3
    assert len(provider.execution_receipts) == 4
    assert result["usage"]["input_tokens"] == 30
    assert result["usage"]["total_tokens"] == 36
    assert result["usage"]["estimated_cost_usd"] == 0.03


async def test_final_tool_failure_adjustments_are_distinct_from_validator_rewrites():
    from creditops.diagnostic_clients import DiagnosticClientError

    class FailedDiagnostic(LocalClient):
        async def call(self, name, arguments):
            if name == "inspect_database_health":
                raise DiagnosticClientError("Offline missing database response")
            return await super().call(name, arguments)

    class CheckDatabase(ProposalProvider):
        async def next_action(self, incident, schemas, observations, evidence):
            if observations[-1]["tool"] == "query_metrics":
                return AdaptiveDecision(
                    action="tool",
                    request=DiagnosticRequest(name="inspect_database_health", service=None, q=None),
                ), {}
            return await super().next_action(incident, schemas, observations, evidence)

    result = await collect_adaptive_investigation(
        LocalStore(), "offline", "INC-DEMO-003", CheckDatabase(), diagnostic_client=FailedDiagnostic()
    )
    assert result["provider_proposal"]["confidence"] > 0.6
    assert result["assessment"]["confidence"] == 0.6
    changes = result["validation_outcome"]["changed_fields"]
    assert {item["reason"] for item in changes if item.get("stage") == "orchestration"} == {
        "diagnostic_failure_confidence_cap",
        "diagnostic_failure_limitation",
        "execution_provenance_limitation",
    }
    assert any(
        item["field"] == "confidence" and item["reason"] == "diagnostic_failure_confidence_cap"
        for item in changes
    )
    assert any(item["stage"] == "diagnostic_validation" for item in changes)
