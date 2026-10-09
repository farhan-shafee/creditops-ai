"""Citation checks and a limited synthetic-domain support gate."""

import json
import re
from typing import Any

from .diagnostics import ABSTAIN_DOMAIN, as_dict, build_assessment, diagnose
from .models import Assessment
from .security import sanitize


class InvalidAssessment(ValueError):
    pass


def _neutralize_abstained_narrative(
    assessment: Assessment, support: list[dict], rows: dict[str, dict]
) -> None:
    """Rebuild factual observations when an assessment cannot substantiate a cause.

    Model-authored causal prose cannot survive by moving into another RCA field.
    Diagnostic observations are rebuilt from returned evidence; advisory follow-up
    steps remain intact for human review.
    """
    observations = sorted(
        {item["id"]: item for item in support}.values(), key=lambda item: (item["timestamp"], item["id"])
    )
    assessment.incident_summary = "The collected observations do not independently establish a failure domain. Additional human investigation is required."
    assessment.alternative_hypotheses = []
    assessment.rca.probable_root_cause = (
        "Insufficient evidence. No failure domain passed independent diagnostic corroboration."
    )
    assessment.rca.executive_summary = "Draft — human review required. A causal diagnosis could not be corroborated by the cited observations."
    assessment.rca.impact = (
        "Returned synthetic request events are available for human review; no financial loss or execution is inferred."
        if any(item.get("kind") == "business_event" for item in rows.values())
        else "Business impact is unverified: no RFQ or order event evidence was returned."
    )
    assessment.rca.timeline = [
        f"{item['timestamp']} — recorded {item['kind']} telemetry for {item.get('service', 'unknown')} [{item['id']}]."
        for item in observations
    ]
    assessment.rca.contributing_factors = []
    assessment.rca.observed_evidence = []
    for item in observations:
        data = item.get("data", {})
        detail = (
            f"{data.get('metric', 'metric')}={data.get('value')} {data.get('unit', '')}"
            if item["kind"] == "metric"
            else f"Recorded source text: {json.dumps(sanitize(item.get('summary', '')), ensure_ascii=False)}"
        )
        assessment.rca.observed_evidence.append(f"[{item['id']}] {item.get('service', 'unknown')}: {detail}")


def validate_assessment(assessment: Assessment, evidence: list[Any]) -> Assessment:
    rows = {as_dict(item)["id"]: as_dict(item) for item in evidence}
    referenced = (
        set(assessment.supporting_evidence_ids)
        | set(assessment.relevant_runbooks)
        | set(assessment.similar_incidents)
    )
    for hypothesis in assessment.alternative_hypotheses:
        referenced.update(as_dict(hypothesis).get("evidence_ids", []))
    for claim in [*assessment.observations, *assessment.possible_triggers]:
        referenced.update(claim.evidence_ids)
    if assessment.confirmed_cause:
        referenced.update(assessment.confirmed_cause.evidence_ids)
    # Validate citations embedded in prose as well as structured citation arrays.
    referenced.update(
        re.findall(
            r"\b(?:BUSINESS|LOG|METRIC|DEPLOY|RUNBOOK|FIX(?:-EVID)?|KAFKA(?:-EVID)?|DB(?:-EVID)?|INC-(?:HIST|DEMO|EVAL|EVID)|TOPOLOGY)-[A-Za-z0-9_-]+\b",
            json.dumps(assessment.model_dump(mode="json")),
        )
    )
    missing = referenced - rows.keys()
    if missing:
        raise InvalidAssessment("Assessment cited evidence not returned by diagnostic tools")
    if any(rows[identifier]["kind"] != "runbook" for identifier in assessment.relevant_runbooks):
        raise InvalidAssessment("Runbook citation has the wrong evidence type")
    if any(
        rows[identifier]["kind"] not in ("history", "historical_incident")
        for identifier in assessment.similar_incidents
    ):
        raise InvalidAssessment("Historical incident citation has the wrong evidence type")
    support = [rows[identifier] for identifier in assessment.supporting_evidence_ids]
    corroborated_domain, _, _ = diagnose(support)
    all_observed_domain, _, _ = diagnose(list(rows.values()))
    if assessment.probable_failure_domain != ABSTAIN_DOMAIN and (
        len(set(assessment.supporting_evidence_ids)) < 2
        or not any(item["kind"] in ("metric", "kafka", "fix", "database") for item in support)
        or corroborated_domain != assessment.probable_failure_domain
        or all_observed_domain != assessment.probable_failure_domain
    ):
        assessment.probable_failure_domain = ABSTAIN_DOMAIN
        assessment.confidence = min(assessment.confidence, 0.4)
        assessment.limitations.append(
            "The conservative synthetic-domain support gate could not corroborate the proposed domain. Human investigation is required."
        )
    if assessment.probable_failure_domain == ABSTAIN_DOMAIN:
        assessment.confidence = min(assessment.confidence, 0.4)
        _neutralize_abstained_narrative(assessment, support, rows)
        assessment.observations = []
        assessment.supported_failure_condition = None
        assessment.possible_triggers = []
        assessment.confirmed_cause = None
        assessment.unknowns = [
            "Returned observations do not establish one independently corroborated failure condition.",
            "The initiating cause and business impact require further investigation.",
        ]
    else:
        # Matching identifiers alone cannot substantiate arbitrary surrounding prose.
        # Normalize the bounded, known-domain display fields; this is intentionally
        # not a general factuality verifier for arbitrary model-generated claims.
        safe, _ = build_assessment({}, list(rows.values()))
        for field in (
            "incident_summary",
            "probable_failure_domain",
            "confidence",
            "supporting_evidence_ids",
            "alternative_hypotheses",
            "recommended_next_steps",
            "rca",
            "observations",
            "supported_failure_condition",
            "possible_triggers",
            "confirmed_cause",
            "unknowns",
            "score_kind",
        ):
            setattr(assessment, field, getattr(safe, field))
        assessment.limitations = [
            "Displayed known-domain observations, hypotheses and causal fields are normalized by a conservative rule gate. This is not a general factuality guarantee.",
            "The support score is uncalibrated. Historical similarity and a preceding deployment do not prove causation.",
        ]
    assessment.requires_human_review = True
    return assessment
