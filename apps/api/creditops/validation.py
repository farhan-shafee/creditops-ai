"""Citation checks and a limited synthetic-domain support gate."""

import copy
import json
import re
from typing import Any

from .diagnostics import ABSTAIN_DOMAIN, as_dict, build_assessment, diagnose
from .models import Assessment
from .security import sanitize


class InvalidAssessment(ValueError):
    """Rejected assessments retain a sanitized comparison for partial receipts."""

    provider_proposal: dict[str, Any] | None = None
    validation_outcome: dict[str, Any] | None = None


EVIDENCE_REFERENCE = re.compile(
    r"\b(?:BUSINESS|LOG|METRIC|DEPLOY|RUNBOOK|FIX(?:-EVID)?|KAFKA(?:-EVID)?|DB(?:-EVID)?|INC-(?:HIST|DEMO|EVAL|EVID)|TOPOLOGY)-[A-Za-z0-9_-]+\b"
)


def _reference_fields(proposal: dict[str, Any]) -> dict[str, set[str]]:
    """Locate both structured citations and identifiers embedded in prose."""
    fields: dict[str, set[str]] = {}

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                visit(item, f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]")
        elif isinstance(value, str):
            found = set(EVIDENCE_REFERENCE.findall(value))
            # Structured reference arrays must reject arbitrary invented IDs too.
            if any(field in path for field in ("evidence_ids[", "relevant_runbooks[", "similar_incidents[")):
                found.add(value)
            if found:
                fields[path] = found

    visit(proposal, "")
    return fields


def _changed_fields(before: Any, after: Any, reason: str, path: str = "") -> list[dict[str, str]]:
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        return [
            change
            for key in sorted(before.keys() | after.keys())
            for change in _changed_fields(
                before.get(key), after.get(key), reason, f"{path}.{key}" if path else key
            )
        ]
    return [
        {
            "field": path,
            "reason": "mandatory_human_review" if path == "requires_human_review" else reason,
            "stage": "diagnostic_validation",
        }
    ]


def validate_assessment_with_outcome(
    assessment: Assessment, evidence: list[Any]
) -> tuple[Assessment, dict[str, Any], dict[str, Any]]:
    """Observe the existing in-place gate without treating rewrites as model claims.

    Only public structured advisory fields are retained, sanitized as untrusted data.
    This deliberately leaves the diagnostic rules in validate_assessment unchanged.
    """
    proposal = sanitize(copy.deepcopy(assessment.model_dump(mode="json")))
    references = _reference_fields(proposal)
    rows = {as_dict(item)["id"]: as_dict(item) for item in evidence}
    missing = sorted(set().union(*references.values()) - rows.keys()) if references else []
    outcome: dict[str, Any] = {
        "status": "pending",
        "structurally_parsed": True,
        "proposal_sanitized": True,
        "proposed_domain": proposal["probable_failure_domain"],
        "final_domain": None,
        "diagnostic_domain_supported": None,
        "original_claims_independently_verified": False,
        "scope": "Citation validity and conservative known synthetic-domain support only; normalized fields are rule-authored and do not independently confirm every original claim.",
        "invalid_evidence_ids": missing,
        "invalid_citation_count": len(missing),
        "changed_fields": [],
        "rejected_fields": [],
    }
    try:
        final = validate_assessment(assessment, evidence)
    except InvalidAssessment as error:
        rejected = [
            {"field": field, "reason": "evidence_not_returned", "evidence_ids": sorted(ids & set(missing))}
            for field, ids in references.items()
            if ids & set(missing)
        ]
        if not rejected:
            for field, expected in (
                ("relevant_runbooks", {"runbook"}),
                ("similar_incidents", {"history", "historical_incident"}),
            ):
                ids = [
                    identifier
                    for identifier in proposal[field]
                    if identifier in rows and rows[identifier]["kind"] not in expected
                ]
                if ids:
                    rejected.append({"field": field, "reason": "wrong_evidence_type", "evidence_ids": ids})
        outcome.update(status="rejected", rejected_fields=rejected)
        error.provider_proposal = proposal
        error.validation_outcome = outcome
        raise
    downgraded = (
        proposal["probable_failure_domain"] != ABSTAIN_DOMAIN
        and final.probable_failure_domain == ABSTAIN_DOMAIN
    )
    reason = (
        "unsupported_domain_abstention"
        if downgraded
        else (
            "abstention_narrative_normalization"
            if final.probable_failure_domain == ABSTAIN_DOMAIN
            else "known_domain_rule_normalization"
        )
    )
    changed = _changed_fields(proposal, sanitize(final.model_dump(mode="json")), reason)
    outcome.update(
        status="downgraded"
        if downgraded
        else (
            "abstained"
            if final.probable_failure_domain == ABSTAIN_DOMAIN
            else ("accepted_normalized" if changed else "accepted")
        ),
        final_domain=final.probable_failure_domain,
        diagnostic_domain_supported=final.probable_failure_domain != ABSTAIN_DOMAIN
        and final.probable_failure_domain == proposal["probable_failure_domain"],
        changed_fields=changed,
    )
    return final, proposal, outcome


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
