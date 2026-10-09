"""Bounded read-only investigation orchestration, evidence validation and honest replay."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import Assessment
from .providers import (
    ABSTAIN_DOMAIN,
    AssessmentProvider,
    ProviderUnavailable,
    as_dict,
    create_provider,
    diagnose,
)
from .security import sanitize
from .settings import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPLAY_DIR = PROJECT_ROOT / "data" / "replay"
LOGGER = logging.getLogger("creditops.investigator")
ACTION_LABELS = {
    "get_incident": "Retrieved incident context",
    "query_metrics": "Queried service latency and freshness",
    "inspect_kafka_lag": "Inspected Kafka consumer lag",
    "inspect_fix_session": "Inspected FIX sessions and heartbeats",
    "inspect_database_health": "Inspected database pool and wait times",
    "search_logs": "Searched bounded service logs",
    "get_recent_deployments": "Compared deployment timestamps",
    "get_service_topology": "Mapped service dependencies",
    "find_similar_incidents": "Retrieved similar historical incidents",
    "search_runbooks": "Retrieved relevant diagnostic runbooks",
}
ALLOWED_TOOLS = frozenset(ACTION_LABELS)


class InvalidAssessment(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


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
    impact = next(
        (
            item.get("data", {}).get("client_impact")
            for item in rows.values()
            if item.get("kind") == "incident" and isinstance(item.get("data", {}).get("client_impact"), str)
        ),
        None,
    )
    assessment.rca.impact = (
        sanitize(impact)
        if impact
        else "Client impact requires confirmation against incident metadata, service telemetry and response deadlines."
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
    # Validate citations embedded in prose as well as structured citation arrays.
    referenced.update(
        re.findall(
            r"\b(?:LOG|METRIC|DEPLOY|RUNBOOK|FIX(?:-EVID)?|KAFKA(?:-EVID)?|DB(?:-EVID)?|INC-(?:HIST|DEMO|EVAL|EVID)|TOPOLOGY)-[A-Za-z0-9_-]+\b",
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
    if assessment.probable_failure_domain != ABSTAIN_DOMAIN and (
        len(set(assessment.supporting_evidence_ids)) < 2
        or not any(item["kind"] in ("metric", "kafka", "fix", "database") for item in support)
        or corroborated_domain != assessment.probable_failure_domain
    ):
        assessment.probable_failure_domain = ABSTAIN_DOMAIN
        assessment.confidence = min(assessment.confidence, 0.4)
        assessment.limitations.append(
            "The conservative synthetic-domain support gate could not corroborate the proposed domain. Human investigation is required."
        )
    if assessment.probable_failure_domain == ABSTAIN_DOMAIN:
        assessment.confidence = min(assessment.confidence, 0.4)
        _neutralize_abstained_narrative(assessment, support, rows)
    if assessment.confidence < 0.7 or assessment.probable_failure_domain == ABSTAIN_DOMAIN:
        assessment.requires_human_review = True
    return assessment


def merge_usage(records: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ("input_tokens", "output_tokens", "total_tokens", "estimated_cost_usd")
    return {
        key: sum(record[key] for record in records if record.get(key) is not None)
        if any(record.get(key) is not None for record in records)
        else None
        for key in keys
    }


async def collect_investigation(
    store: Any,
    session_id: str,
    incident_id: str,
    provider: AssessmentProvider,
    on_progress: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    from .tools import DiagnosticTools

    incident = await store.get_incident(session_id, incident_id)
    if incident is None:
        raise ValueError("Incident not found in this demo session")
    # Generator tags are UI simulation controls, never diagnostic/model context.
    incident_context = sanitize({key: value for key, value in as_dict(incident).items() if key != "scenario"})
    result: dict[str, Any] = {
        "id": str(uuid4()),
        "incident_id": incident_id,
        "mode": "PIPELINE",
        "status": "running",
        "provider": provider.name,
        "created_at": utc_now(),
        "steps": [],
        "evidence": [],
        "assessment": None,
        "error": None,
        "usage": {},
    }
    tools = DiagnosticTools(store, session_id)
    seen: set[str] = set()
    usages: list[dict[str, Any]] = []

    async def publish() -> None:
        if on_progress:
            await on_progress(result)

    async def execute(name: str, arguments: dict[str, Any]) -> None:
        if name not in ALLOWED_TOOLS:
            raise InvalidAssessment("Requested tool is outside the diagnostic allowlist")
        started = time.perf_counter()
        step = {
            "id": f"STEP-{len(result['steps']) + 1:03d}",
            "action": ACTION_LABELS[name],
            "tool": name,
            "status": "running",
            "evidence_ids": [],
            "timestamp": utc_now(),
            "duration_ms": 0.0,
        }
        result["steps"].append(step)
        await publish()
        try:
            returned = await asyncio.wait_for(
                tools.call(name, {**arguments, "incident_id": incident_id, "limit": 50}), timeout=10
            )
            for raw in returned[:50]:
                item = sanitize(as_dict(raw))
                step["evidence_ids"].append(item["id"])
                if item["id"] not in seen and len(result["evidence"]) < 250:
                    result["evidence"].append(item)
                    seen.add(item["id"])
            step["status"] = "complete"
        except (TimeoutError, ValueError, RuntimeError):
            step["status"] = "failed"
            LOGGER.warning("diagnostic_tool_failed", extra={"tool": name, "incident_id": incident_id})
        step["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
        await publish()

    await execute("get_incident", {})
    plan, plan_usage = await provider.plan(incident_context)
    usages.append(plan_usage)
    for request in plan.requests:
        arguments: dict[str, Any] = {}
        if request.service:
            arguments["service"] = request.service[:80]
        if request.q:
            arguments["q"] = request.q[:240]
        if request.name in ("search_runbooks", "find_similar_incidents") and not request.q:
            domain, _, _ = diagnose(result["evidence"])
            arguments["q"] = (
                domain if domain != ABSTAIN_DOMAIN else as_dict(incident).get("summary", "")[:240]
            )
        await execute(request.name, arguments)
    started = time.perf_counter()
    assessment, assessment_usage = await provider.assess(incident_context, result["evidence"])
    usages.append(assessment_usage)
    assessment = validate_assessment(assessment, result["evidence"])
    if any(step["status"] == "failed" for step in result["steps"]):
        assessment.requires_human_review = True
        assessment.confidence = min(assessment.confidence, 0.6)
        assessment.limitations.append(
            "One or more diagnostic tools failed; additional human investigation is required."
        )
    result["assessment"] = assessment.model_dump(mode="json")
    result["usage"] = merge_usage(usages)
    result["steps"].append(
        {
            "id": f"STEP-{len(result['steps']) + 1:03d}",
            "action": "Generated and validated evidence-backed assessment",
            "tool": "assessment_validation",
            "status": "complete",
            "evidence_ids": assessment.supporting_evidence_ids,
            "timestamp": utc_now(),
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    )
    result["status"] = "complete"
    await publish()
    return result


def artifact_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()


def write_replay_artifact(result: dict[str, Any], directory: Path = REPLAY_DIR) -> Path:
    identifier = result["incident_id"]
    if not re.fullmatch(r"INC-(?:DEMO|EVAL)-\d{3}", identifier):
        raise ValueError("Unsupported artifact incident ID")
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "provenance": {
            "pipeline": "creditops.investigator.collect_investigation",
            "provider": result["provider"],
            "model_called": result["provider"] != "deterministic",
            "telemetry_window": "complete synthetic scenario snapshot",
        },
        "investigation": result,
    }
    envelope = {"sha256": artifact_digest(payload), "payload": payload}
    path = directory / f"{identifier}.json"
    path.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")
    return path


def read_replay_artifact(incident_id: str, directory: Path = REPLAY_DIR) -> dict[str, Any]:
    if not re.fullmatch(r"INC-(?:DEMO|EVAL)-\d{3}", incident_id):
        raise ProviderUnavailable("No replay artifact for this incident")
    path = directory / f"{incident_id}.json"
    if not path.exists():
        raise ProviderUnavailable(
            "Replay artifact missing. Run the evaluation/artifact generator before serving this demo."
        )
    if path.stat().st_size > 2_000_000:
        raise InvalidAssessment("Replay artifact exceeded size budget")
    envelope = json.loads(path.read_text(encoding="utf-8"))
    payload = envelope["payload"]
    if envelope["sha256"] != artifact_digest(payload) or payload["schema_version"] != 1:
        raise InvalidAssessment("Replay artifact integrity check failed")
    result = payload["investigation"]
    if result["incident_id"] != incident_id or result["status"] != "complete":
        raise InvalidAssessment("Replay artifact incident or state mismatch")
    validated = validate_assessment(Assessment.model_validate(result["assessment"]), result["evidence"])
    result["assessment"] = validated.model_dump(mode="json")
    return payload


async def create_investigation(store: Any, session_id: str, incident_id: str, mode: str) -> dict[str, Any]:
    if mode not in ("REPLAY", "LIVE_AI"):
        raise ValueError("Investigation mode must be REPLAY or LIVE_AI")
    if await store.get_incident(session_id, incident_id) is None:
        raise ValueError("Run an incident in this session before investigating")
    row = {
        "id": str(uuid4()),
        "incident_id": incident_id,
        "mode": mode,
        "status": "running",
        "provider": "deterministic" if mode == "REPLAY" else Settings().ai_provider,
        "created_at": utc_now(),
        "steps": [],
        "evidence": [],
        "assessment": None,
        "error": None,
        "usage": {},
    }
    await store.save_investigation(session_id, row)
    return row


async def run_investigation(store: Any, session_id: str, inv_id: str) -> None:
    row = await store.get_investigation(session_id, inv_id)
    if row is None:
        return

    async def persist(update: dict[str, Any]) -> None:
        row.update({key: value for key, value in update.items() if key not in ("id", "mode", "created_at")})
        await store.save_investigation(session_id, row)

    async def work() -> None:
        if row["mode"] == "REPLAY":
            payload = read_replay_artifact(row["incident_id"], Settings().replay_dir)
            artifact = payload["investigation"]
            row["provider"] = payload["provenance"]["provider"]
            row["usage"] = artifact["usage"]
            for step in artifact["steps"]:
                row["steps"].append(step)
                ids = set(step["evidence_ids"])
                current = {item["id"] for item in row["evidence"]}
                row["evidence"].extend(
                    item for item in artifact["evidence"] if item["id"] in ids and item["id"] not in current
                )
                await store.save_investigation(session_id, row)
                await asyncio.sleep(0.18)
            row["evidence"] = artifact["evidence"]
            row["assessment"] = artifact["assessment"]
            row["assessment"]["limitations"] = [
                *row["assessment"]["limitations"],
                "Replay uses a persisted complete scenario snapshot. Step timestamps are artifact generation times; this is not a live model call.",
            ]
            row["status"] = "complete"
            await store.save_investigation(session_id, row)
        else:
            provider = create_provider(Settings().ai_provider)
            try:
                await collect_investigation(store, session_id, row["incident_id"], provider, persist)
            finally:
                client = getattr(provider, "client", None)
                if client is not None:
                    await client.close()

    try:
        await asyncio.wait_for(work(), timeout=Settings().investigation_timeout_seconds)
    except asyncio.CancelledError:
        row["status"] = "failed"
        row["error"] = "Investigation interrupted by server shutdown. Please retry."
        await store.save_investigation(session_id, row)
        raise
    except Exception as error:
        row["status"] = "failed"
        row["error"] = (
            sanitize(str(error))
            if isinstance(error, (ProviderUnavailable, InvalidAssessment, ValueError))
            else f"Investigation could not complete ({type(error).__name__}). Review server configuration and retry."
        )
        await store.save_investigation(session_id, row)
        LOGGER.warning(
            "investigation_failed",
            extra={"incident_id": row["incident_id"], "error_type": type(error).__name__},
        )


async def stream_events(store: Any, session_id: str, inv_id: str) -> AsyncIterator[str]:
    sent: dict[str, str] = {}
    deadline = time.monotonic() + Settings().investigation_timeout_seconds + 10
    while time.monotonic() < deadline:
        row = await store.get_investigation(session_id, inv_id)
        if row is None:
            yield 'event: error\ndata: {"message":"Investigation not found in this session"}\n\n'
            return
        for step in row["steps"]:
            state = json.dumps(step, sort_keys=True)
            if sent.get(step["id"]) != state:
                sent[step["id"]] = state
                yield f"event: step\ndata: {json.dumps(step)}\n\n"
        if row["status"] == "complete":
            yield f"event: complete\ndata: {json.dumps(row)}\n\n"
            return
        if row["status"] == "failed":
            yield f"event: error\ndata: {json.dumps({'message': row['error']})}\n\n"
            return
        yield ": heartbeat\n\n"
        await asyncio.sleep(0.25)
    yield 'event: error\ndata: {"message":"Investigation stream timed out; retrieve the saved result or retry"}\n\n'
