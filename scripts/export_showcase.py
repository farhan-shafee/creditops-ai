"""Export only the three authorized completed receipts as keyless replay derivatives.

This offline projection imports no live runner, creates no provider and reads no
environment file. Source receipts remain private and unchanged.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "apps/api"))

from creditops.investigator import (  # noqa: E402
    artifact_digest,
    read_replay_artifact,
    utc_now,
    write_replay_artifact,
)
from creditops.security import sanitize  # noqa: E402

SELECTED_RECEIPTS = (
    ("run-3f4d7391-f31c-47b9-93cb-da7d02354782.json", "38ec45c9-71aa-4323-91cb-c5a0360d11ce"),
    ("run-75c7bf12-0bb1-4ca8-b386-721d886f50ad.json", "77ad110d-913d-4002-b81b-a5648e068d4f"),
    ("run-b36007b2-4680-44d5-b67c-69a3d255242e.json", "d731255e-15db-4a97-a331-c74bdaac5327"),
)
EXPORT_VERSION = 1
CASE_LABELS = (
    ("Pricing backlog", "kafka-pricing-lag"),
    ("FIX session instability", "fix-connectivity"),
    ("Database pool exhaustion", "db-pool-exhaustion"),
)
REDACTIONS = [
    "Provider request, response and call identifiers omitted.",
    "Session, experiment and internal local-resource identity metadata omitted.",
    "Local paths, environment/configuration data, approval records and credential fingerprints omitted.",
    "Reservation, configured price ceiling, service-tier and protocol inventory metadata omitted.",
    "Public advisory text and evidence use the existing secret/text sanitizer; model errors are retained.",
]
PROVENANCE_FIELDS = (
    "workflow", "initial_diagnostics", "transport", "provider", "model_called", "snapshot_cutoff",
    "snapshot_kind", "recorded", "provider_turns", "tool_calls", "assessment_source", "source_commit",
)
CALL_FIELDS = (
    "provider", "requested_model", "returned_model", "schema", "status", "request_started",
    "response_received", "started_at", "ended_at", "duration_ms", "usage", "charge_status",
    "structured_output", "provider_status",
)
REVIEW_NOTES = (
    {
        "identified": [
            "Pricing backlog and stale/unavailable quotes align with the returned lag, latency and RFQ events [METRIC-001-LAG, BUSINESS-001-004, BUSINESS-001-010, BUSINESS-001-011].",
        ],
        "overstatements": [
            "Lag is high in sparse samples and rises from 15200.6 at 14:01:48 to 19000 at 14:02:24, but it previously dips from 18923 at 14:01:36; these rows do not establish continuous growth [METRIC-001-LAG, METRIC-001-SERIES-PRICING-SERVICE-KAFKA_CONSUMER_LAG-4, METRIC-001-SERIES-PRICING-SERVICE-KAFKA_CONSUMER_LAG-5].",
            "Its confirmed-cause and causal-chain prose exceeds what concurrent symptoms prove. Normal CPU/DB/FIX samples exclude neither intermittent problems nor health after the last returned sample.",
            "References to health 'at the cutoff' conflate samples ending at 14:02:24 UTC with the 15:00 UTC collection cutoff.",
        ],
        "unknowns": [
            "The initiating trigger, upstream market/reference-data health and behavior after 14:02:24 UTC remain unknown. No fills, executed trades or financial loss are established.",
        ],
    },
    {
        "identified": [
            "The proposal identifies FIX instability and distinguishes pending/uncertain acknowledgements from completion [LOG-002-002, BUSINESS-002-006, BUSINESS-002-007, BUSINESS-002-014, BUSINESS-002-015].",
            "Recorded retransmissions retain the same economic order identities; no new economic order or confirmed fill is established [BUSINESS-002-008, BUSINESS-002-016].",
        ],
        "overstatements": [
            "Its executive summary says acknowledgements were delayed 'because' of FIX instability; concurrent observations support the failure condition but do not prove that causal chain.",
            "Its quote-service CPU exclusion cites database/stale-price rows, but no quote-service CPU sample was returned. Normal pricing/database rows cannot rule out intermittent alternatives or establish health through the 15:00 UTC cutoff.",
            "The cited standalone acknowledgement sample is 4650 ms; the separate last series row establishes 4900 ms. A valid citation does not make every surrounding numerical claim supported [METRIC-002-ACK, METRIC-002-SERIES-EXECUTION-SERVICE-EXECUTION_ACK_LATENCY_MS-5].",
        ],
        "unknowns": [
            "The initiating session failure, counterparty processing state and acknowledgement outcome after 14:02:24 UTC remain unknown. Blind order resubmission is unsafe without reconciliation.",
        ],
    },
    {
        "identified": [
            "Pool saturation, long DB wait and processing timeouts align with RFQ expiry [METRIC-003-SERIES-QUOTE-SERVICE-DB_POOL_UTILIZATION-5, METRIC-003-SERIES-QUOTE-SERVICE-DB_WAIT_MS-5, LOG-003-002, BUSINESS-003-004, BUSINESS-003-005].",
        ],
        "overstatements": [
            "The proposal asserts degradation through 15:00 UTC, although returned samples end at 14:02:24 UTC; the cutoff is not continuous time coverage.",
            "Its confirmed-cause and 'caused' wording overstates causal evidence. The recorded timeout log reports pool_size=40 and in_use=40, but it does not prove the initiating saturation mechanism [LOG-003-002].",
            "Pool utilization is 100% at 14:01:36, 87% at 14:01:48 and 100% at 14:02:24. Request rate falls from 256 to 240 between the last two samples, so a continuous rising-load story is unsupported [METRIC-003-POOL, METRIC-003-SERIES-QUOTE-SERVICE-DB_POOL_UTILIZATION-4, METRIC-003-SERIES-QUOTE-SERVICE-DB_POOL_UTILIZATION-5, METRIC-003-SERIES-QUOTE-SERVICE-REQUEST_RATE_PER_SECOND-4, METRIC-003-SERIES-QUOTE-SERVICE-REQUEST_RATE_PER_SECOND-5].",
            "CPU/pricing/FIX exclusions apply only to the returned rows. The incident timeline mentions a deployment, but no deployment object was retrieved; higher request load does not independently prove the trigger.",
        ],
        "unknowns": [
            "The initiating load/query/lock/connection-ownership mechanism, any preceding change, recovery and state after 14:02:24 UTC remain unknown. The events establish RFQ expiry, not financial loss.",
        ],
    },
)


def project_receipt(receipt, index, source_name, source_hash, exported_at):
    """Keep recorded advisory/evidence objects, projecting operational metadata."""
    incident_id = f"INC-DEMO-{index + 1:03d}"
    if receipt.get("execution") != "COMPLETED_APPROVED_CASES" or len(receipt.get("results", [])) != 1:
        raise ValueError(f"Selected receipt {source_name} is not a single completed recording")
    original = receipt["results"][0]
    if original.get("incident_id") != incident_id or original.get("status") != "complete":
        raise ValueError(f"Selected receipt {source_name} has a mismatched incident or execution state")
    if not original.get("assessment") or not original.get("provider_proposal") or not original.get("validation_outcome"):
        raise ValueError(f"Selected receipt {source_name} lacks recorded proposal/validation/final output")
    result = sanitize(copy.deepcopy(original))
    result["provenance"] = {
        key: sanitize(copy.deepcopy(original.get("provenance", {}).get(key)))
        for key in PROVENANCE_FIELDS if key in original.get("provenance", {})
    }
    result["provider_calls"] = [
        {key: sanitize(copy.deepcopy(call[key])) for key in CALL_FIELDS if key in call}
        for call in original.get("provider_calls", [])
    ]
    times = [item["timestamp"] for item in result["evidence"]]
    review = copy.deepcopy(REVIEW_NOTES[index])
    diagnostic_fields = {
        change["field"] for change in result["validation_outcome"].get("changed_fields", [])
        if change.get("stage") == "diagnostic_validation"
    }
    review["validator_changes"] = [
        f"The recorded gate accepted the failure domain and normalized {len(diagnostic_fields)} fields, including causal prose and observations. Its rewrites are rule-authored; they do not independently establish that each original field was erroneous.",
        "The final advisory leaves the initiating cause unconfirmed and requires human review. Model and rule support scores are distinct and uncalibrated.",
    ]
    title, scenario = CASE_LABELS[index]
    source_commit = receipt["configuration"]["source_commit"]
    showcase = {
        "title": title,
        "scenario_id": scenario,
        "source_receipt": source_name,
        "source_sha256": source_hash,
        "source_commit": source_commit,
        "export_version": EXPORT_VERSION,
        "exported_at": exported_at,
        "generated_at": receipt["started_at"],
        "generation_ended_at": receipt["ended_at"],
        "original_duration_seconds": receipt["duration_seconds"],
        "recorded_execution_outcome": receipt["execution"],
        "sample_start": min(times),
        "sample_end": max(times),
        "snapshot_label": "Complete recorded evidence snapshot; independent of simulated animation progress. Cutoff is not continuous sample coverage.",
        "review_notes": review,
        "review_scope": "Project review notes; not an independent human audit or automatically proven factuality assessment.",
        "usage_scope": "Recorded token usage and estimated API cost; not confirmed billing, hosting cost or measured human time saved.",
    }
    result["provenance"]["showcase"] = showcase
    result["provenance"]["source_commit"] = source_commit
    summary = {
        "incident_id": incident_id,
        "title": title,
        "scenario_id": scenario,
        "execution_outcome": receipt["execution"],
        "proposed_domain": result["provider_proposal"]["probable_failure_domain"],
        "final_domain": result["assessment"]["probable_failure_domain"],
        "validation_status": result["validation_outcome"]["status"],
        "model": next((call.get("returned_model") or call.get("requested_model") for call in result["provider_calls"] if call.get("request_started")), None),
        "workflow": result["provenance"].get("workflow"),
        "application_selected_diagnostic_count": sum(step.get("selected_by") == "application_runbook" for step in result["steps"]),
        "model_selected_diagnostic_count": sum(step.get("selected_by") == "model" and step.get("tool") != "assessment_validation" for step in result["steps"]),
        "model_decision_count": sum(call.get("schema") == "AvailableAdaptiveDecision" for call in result["provider_calls"]),
        "model_assessment_count": sum(call.get("schema") == "Assessment" for call in result["provider_calls"]),
        "original_duration_seconds": receipt["duration_seconds"],
        "major_limitations": [*review["overstatements"], *review["unknowns"]],
        "sample_start": showcase["sample_start"],
        "sample_end": showcase["sample_end"],
        "snapshot_cutoff": result["provenance"].get("snapshot_cutoff"),
        "source_commit": source_commit,
        "source_receipt": source_name,
        "source_sha256": source_hash,
        "generated_at": receipt["started_at"],
        "exported_at": exported_at,
    }
    return result, summary


def export_showcase(source_directory, destination, exported_at=None):
    """Read the explicit allowlist only; fail honestly if any selected source fails."""
    exported_at = exported_at or utc_now()
    projected = []
    for index, (name, experiment) in enumerate(SELECTED_RECEIPTS):
        raw = (Path(source_directory) / name).read_bytes()
        receipt = json.loads(raw)
        if receipt.get("experiment_id") != experiment:
            raise ValueError(f"Selected receipt {name} has unexpected experiment provenance")
        projected.append(project_receipt(receipt, index, name, hashlib.sha256(raw).hexdigest(), exported_at))
    destination = Path(destination)
    summaries = []
    for result, summary in projected:
        path = write_replay_artifact(result, destination)
        envelope = json.loads(path.read_text(encoding="utf-8"))
        # Existing envelope semantics now distinguish original generation and
        # derivative export in showcase provenance; observations are unchanged.
        envelope["payload"]["generated_at"] = result["provenance"]["showcase"]["generated_at"]
        envelope["sha256"] = artifact_digest(envelope["payload"])
        path.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")
        read_replay_artifact(result["incident_id"], destination)
        summary["replay_payload_sha256"] = envelope["sha256"]
        summaries.append(summary)
    manifest = {
        "export_version": EXPORT_VERSION,
        "exported_at": exported_at,
        "label": "Selected recorded synthetic examples",
        "scope": "Selected completed development examples, not autonomous investigations or a general-accuracy benchmark. Earlier failed and abstained attempts remain preserved separately.",
        "redactions": REDACTIONS,
        "selected_recordings": summaries,
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-directory", type=Path, default=PROJECT_ROOT / "artifacts/live-verification")
    parser.add_argument("--output-directory", type=Path, default=PROJECT_ROOT / "data/showcase")
    args = parser.parse_args()
    manifest = export_showcase(args.source_directory, args.output_directory)
    print(f"Exported {len(manifest['selected_recordings'])} selected recordings to {args.output_directory}")
