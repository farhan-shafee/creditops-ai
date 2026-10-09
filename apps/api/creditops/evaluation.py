"""Reproducible labeled synthetic evaluations; never imports labels into diagnostics."""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any

from .investigator import PROJECT_ROOT, collect_investigation, utc_now, write_replay_artifact
from .providers import (
    ABSTAIN_DOMAIN,
    CPU_DOMAIN,
    DB_DOMAIN,
    FIX_DOMAIN,
    KAFKA_DOMAIN,
    MARKET_DOMAIN,
    RISK_DOMAIN,
    as_dict,
    create_provider,
)


def citations(assessment: dict[str, Any]) -> set[str]:
    identifiers = (
        set(assessment.get("supporting_evidence_ids", []))
        | set(assessment.get("relevant_runbooks", []))
        | set(assessment.get("similar_incidents", []))
    )
    for hypothesis in assessment.get("alternative_hypotheses", []):
        identifiers.update(hypothesis.get("evidence_ids", []))
    return identifiers


def score_case(
    case: dict[str, Any],
    assessment: dict[str, Any],
    evidence_ids: set[str],
    latency_ms: float = 0,
    tool_errors: int = 0,
    tool_calls: int = 0,
) -> dict[str, Any]:
    truth = case["ground_truth_failure_domain"]
    predicted = assessment["probable_failure_domain"]
    supported = set(assessment.get("supporting_evidence_ids", []))
    required = set(case["required_evidence_ids"])
    unknown = citations(assessment) - evidence_ids
    abstention_case = truth == ABSTAIN_DOMAIN
    return {
        "top1_correct": predicted == truth,
        "top3_correct": truth
        in [predicted, *[item["domain"] for item in assessment.get("alternative_hypotheses", [])[:2]]],
        "required_evidence_recall": len(supported & required) / len(required) if required else 1.0,
        "invalid_evidence_citations": len(unknown),
        "hallucinated_evidence_count": len(unknown),
        "abstention_case": abstention_case,
        "correct_abstention": abstention_case
        and predicted == ABSTAIN_DOMAIN
        and assessment.get("requires_human_review", False),
        "escalation_correct": bool(assessment.get("requires_human_review")) == case["requires_human_review"],
        "expected_runbook_retrieved": case.get("expected_runbook") in assessment.get("relevant_runbooks", [])
        if case.get("expected_runbook")
        else True,
        "tool_error_rate": tool_errors / tool_calls if tool_calls else 0.0,
        "tool_errors": tool_errors,
        "tool_calls": tool_calls,
        "latency_ms": latency_ms,
    }


def keyword_baseline(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Cheap first matching log signature, intentionally no independent corroboration."""
    patterns = [
        ("stale pricing", KAFKA_DOMAIN),
        ("heartbeat timeout", FIX_DOMAIN),
        ("connection pool timeout", DB_DOMAIN),
        ("market-data feed stale", MARKET_DOMAIN),
        ("risk dependency timeout", RISK_DOMAIN),
        ("cpu saturation", CPU_DOMAIN),
    ]
    domain, ids = ABSTAIN_DOMAIN, []
    for item in evidence:
        if item["kind"] != "log":
            continue
        text = item["summary"].lower()
        for signature, candidate in patterns:
            if signature in text:
                domain, ids = candidate, [item["id"]]
                break
        if ids:
            break
    book = {
        KAFKA_DOMAIN: "RUNBOOK-001",
        FIX_DOMAIN: "RUNBOOK-002",
        DB_DOMAIN: "RUNBOOK-003",
        CPU_DOMAIN: "RUNBOOK-004",
        MARKET_DOMAIN: "RUNBOOK-005",
        RISK_DOMAIN: "RUNBOOK-006",
    }.get(domain)
    existing = {item["id"] for item in evidence}
    return {
        "probable_failure_domain": domain,
        "supporting_evidence_ids": ids,
        "alternative_hypotheses": [],
        "relevant_runbooks": [book] if book in existing else [],
        "similar_incidents": [],
        "requires_human_review": domain == ABSTAIN_DOMAIN,
    }


def aggregate(name: str, provider: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [item["score"] for item in results]
    abstentions = [score for score in scores if score["abstention_case"]]
    usages = [item.get("usage", {}) for item in results]
    return {
        "name": name,
        "provider": provider,
        "cases": len(scores),
        "top1_accuracy": statistics.mean(score["top1_correct"] for score in scores),
        "top3_accuracy": statistics.mean(score["top3_correct"] for score in scores),
        "required_evidence_recall": statistics.mean(score["required_evidence_recall"] for score in scores),
        "invalid_evidence_citations": sum(score["invalid_evidence_citations"] for score in scores),
        "hallucinated_evidence_count": sum(score["hallucinated_evidence_count"] for score in scores),
        "correct_abstention_rate": statistics.mean(score["correct_abstention"] for score in abstentions)
        if abstentions
        else None,
        "escalation_accuracy": statistics.mean(score["escalation_correct"] for score in scores),
        "runbook_recall": statistics.mean(score["expected_runbook_retrieved"] for score in scores),
        "tool_error_rate": sum(score["tool_errors"] for score in scores)
        / max(1, sum(score["tool_calls"] for score in scores)),
        "mean_latency_ms": statistics.mean(score["latency_ms"] for score in scores),
        "total_tokens": sum(
            usage["total_tokens"] for usage in usages if usage.get("total_tokens") is not None
        )
        if any(usage.get("total_tokens") is not None for usage in usages)
        else None,
        "estimated_cost_usd": sum(
            usage["estimated_cost_usd"] for usage in usages if usage.get("estimated_cost_usd") is not None
        )
        if any(usage.get("estimated_cost_usd") is not None for usage in usages)
        else None,
        "results": results,
    }


async def run_evaluations(
    store: Any,
    provider_name: str = "deterministic",
    output_dir: Path | None = None,
    generate_replay: bool = True,
) -> dict[str, Any]:
    from .tools import DiagnosticTools

    path = PROJECT_ROOT / "data" / "evaluations" / "cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    baseline_results: list[dict[str, Any]] = []
    pipeline_results: list[dict[str, Any]] = []
    provider = create_provider(provider_name)
    for case in cases:
        identifier = case["incident_id"]
        session_id = "evaluation-session"
        await store.activate_case(session_id, identifier)
        tools = DiagnosticTools(store, session_id)
        baseline_started = time.perf_counter()
        logs = [
            as_dict(item)
            for item in await tools.call("search_logs", {"incident_id": identifier, "limit": 50})
        ]
        books = [
            as_dict(item)
            for item in await tools.call("search_runbooks", {"incident_id": identifier, "limit": 50})
        ]
        baseline_evidence = [*logs, *books]
        baseline = keyword_baseline(baseline_evidence)
        baseline_score = score_case(
            case,
            baseline,
            {item["id"] for item in baseline_evidence},
            (time.perf_counter() - baseline_started) * 1000,
            tool_calls=2,
        )
        baseline_results.append(
            {
                "incident_id": identifier,
                "predicted_domain": baseline["probable_failure_domain"],
                "ground_truth": case["ground_truth_failure_domain"],
                "score": baseline_score,
                "usage": {},
            }
        )
        pipeline_started = time.perf_counter()
        result = await asyncio.wait_for(
            collect_investigation(store, session_id, identifier, provider), timeout=120
        )
        score = score_case(
            case,
            result["assessment"],
            {item["id"] for item in result["evidence"]},
            (time.perf_counter() - pipeline_started) * 1000,
            tool_errors=sum(step["status"] == "failed" for step in result["steps"]),
            tool_calls=len(result["steps"]) - 1,
        )
        pipeline_results.append(
            {
                "incident_id": identifier,
                "predicted_domain": result["assessment"]["probable_failure_domain"],
                "ground_truth": case["ground_truth_failure_domain"],
                "score": score,
                "usage": result["usage"],
            }
        )
        if generate_replay and identifier.startswith("INC-DEMO-"):
            write_replay_artifact(result)
    label = (
        "Orchestrated Investigator (deterministic provider)"
        if provider_name == "deterministic"
        else "AI-Assisted Investigator"
    )
    artifact = {
        "schema_version": 1,
        "status": "generated",
        "generated_at": utc_now(),
        "dataset_version": "synthetic-v1",
        "case_count": len(cases),
        "seed": 42,
        "methodology": "15 labeled synthetic cases: 12 diagnosable incidents and 3 insufficient-evidence cases. Labels are available only to the scorer. Complete case telemetry is activated in an isolated evaluation session. Latency measures the synthetic diagnostic pipeline, not human MTTR. The baseline uses first matching log signatures; the investigator requires corroborating independent signals. Deterministic rules are designed for these fixtures; this is an in-distribution functional benchmark, not a generalization study.",
        "limitations": [
            "No real operator study or production MTTR measurement.",
            "Small synthetic in-distribution dataset; no held-out institutional traffic.",
            "Deterministic confidence scores are not calibrated probabilities.",
            "No live model result is claimed unless provider is openai or anthropic.",
            "A failure stops artifact generation; existing artifact remains from its recorded timestamp.",
        ],
        "live_ai_status": "not_run" if provider_name == "deterministic" else "generated",
        "algorithms": [
            aggregate("Deterministic Baseline", "rules-keyword", baseline_results),
            aggregate(label, provider_name, pipeline_results),
        ],
    }
    directory = output_dir or PROJECT_ROOT / "artifacts" / "eval"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "latest.json").write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# CreditOps AI synthetic evaluation",
        "",
        f"Generated: {artifact['generated_at']}. Dataset: {len(cases)} cases; seed 42.",
        "",
        artifact["methodology"],
        "",
        "| Algorithm | Top-1 | Top-3 | Required evidence recall | Invalid citations | Abstention | Mean pipeline ms |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for algorithm in artifact["algorithms"]:
        lines.append(
            f"| {algorithm['name']} | {algorithm['top1_accuracy']:.1%} | {algorithm['top3_accuracy']:.1%} | {algorithm['required_evidence_recall']:.1%} | {algorithm['invalid_evidence_citations']} | {algorithm['correct_abstention_rate']:.1%} | {algorithm['mean_latency_ms']:.2f} |"
        )
    lines += [
        "",
        "Live AI: " + artifact["live_ai_status"],
        "",
        "## Limitations",
        *["- " + limitation for limitation in artifact["limitations"]],
        "",
    ]
    (directory / "latest.md").write_text("\n".join(lines), encoding="utf-8")
    return artifact
