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

from pydantic import ValidationError

from .diagnostic_clients import (
    DiagnosticClient,
    DiagnosticClientError,
    DiagnosticConnectionError,
    DirectDiagnosticClient,
    MCPDiagnosticClient,
    safe_arguments,
)
from .models import Assessment
from .providers import (
    ABSTAIN_DOMAIN,
    AdaptiveDecision,
    AssessmentProvider,
    DeterministicProvider,
    ProviderUnavailable,
    as_dict,
    create_provider,
    diagnose,
)
from .security import sanitize
from .settings import Settings
from .validation import InvalidAssessment, validate_assessment

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


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def merge_usage(records: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ("input_tokens", "output_tokens", "total_tokens", "estimated_cost_usd")
    return {
        key: sum(record[key] for record in records if record.get(key) is not None)
        if any(record.get(key) is not None for record in records)
        else None
        for key in keys
    }


async def collect_adaptive_investigation(
    store: Any,
    session_id: str,
    incident_id: str,
    provider: AssessmentProvider,
    on_progress: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    *,
    diagnostic_client: DiagnosticClient | None = None,
    limits: Settings | None = None,
) -> dict[str, Any]:
    """Bounded observe/choose loop, with real MCP as the application default.

    Direct diagnostics require an explicit adapter. Provider plan-only support is
    deliberately insufficient: this path must observe actual results between turns.
    """
    configuration = limits or Settings()
    if not callable(getattr(provider, "next_action", None)):
        raise ProviderUnavailable("Configured provider does not support evidence-adaptive diagnostics")
    cutoff = await store.freeze_snapshot(session_id, incident_id)
    incident = await store.get_incident(session_id, incident_id, as_of=cutoff)
    if incident is None:
        raise ValueError("Incident not found in this demo session")
    raw = as_dict(incident)
    # No scenario/title/fixture labels, narrative future impact, or playback timeline.
    context = sanitize(
        {
            key: raw[key]
            for key in ("id", "summary", "severity", "started_at", "affected_services")
            if key in raw
        }
    )
    client = diagnostic_client or MCPDiagnosticClient(session_id, incident_id, cutoff)
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
        "provenance": {
            "workflow": "adaptive",
            "transport": client.transport,
            "provider": provider.name,
            "model_called": False,
            "snapshot_cutoff": cutoff,
            "snapshot_kind": "frozen_current",
            "recorded": False,
        },
    }
    seen: set[str] = set()
    requested: set[str] = set()
    observations: list[dict[str, Any]] = []
    usages: list[dict[str, Any]] = []
    no_progress = 0
    provider_turns = 0
    stop_reason: str | None = None

    async def publish() -> None:
        result["usage"] = merge_usage(usages)
        if on_progress:
            await on_progress(result)

    async def execute(name: str, arguments: dict[str, Any]) -> None:
        nonlocal no_progress
        arguments = safe_arguments(name, arguments)
        key = json.dumps([name, arguments], sort_keys=True)
        if key in requested:
            raise DiagnosticClientError("Duplicate diagnostic request stopped safely")
        requested.add(key)
        before = len(seen)
        started = time.perf_counter()
        step = {
            "id": f"STEP-{len(result['steps']) + 1:03d}",
            "action": ACTION_LABELS[name],
            "tool": name,
            "status": "running",
            "evidence_ids": [],
            "timestamp": utc_now(),
            "duration_ms": 0.0,
            "safe_arguments": arguments,
            "transport": client.transport,
            "provider": provider.name,
            "provider_turn": provider_turns,
            "recorded": False,
            "error": None,
        }
        result["steps"].append(step)
        await publish()
        try:
            async with asyncio.timeout(configuration.diagnostic_timeout_seconds):
                returned = await client.call(name, arguments)
            for item in returned:
                item = sanitize(as_dict(item))
                if item["id"] not in seen:
                    candidate = [*result["evidence"], item]
                    if len(candidate) > 250 or len(json.dumps(candidate, ensure_ascii=True).encode()) > 90000:
                        raise DiagnosticClientError("Bounded evidence/context capacity reached")
                    result["evidence"].append(item)
                    seen.add(item["id"])
                step["evidence_ids"].append(item["id"])
            step["status"] = "complete"
        except DiagnosticConnectionError:
            step["status"] = "failed"
            step["error"] = "MCP connection failed; no direct fallback"
            raise
        except asyncio.CancelledError:
            step["status"] = "failed"
            step["error"] = "Diagnostic cancelled; no completed result was returned"
            raise
        except (DiagnosticClientError, TimeoutError, ValueError, RuntimeError):
            step["status"] = "failed"
            step["error"] = "Diagnostic unavailable or invalid; no healthy observation was returned"
        finally:
            step["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
            observations.append(
                {key: step[key] for key in ("tool", "safe_arguments", "status", "evidence_ids", "error")}
            )
            no_progress = no_progress + 1 if len(seen) == before else 0
            await publish()

    try:
        async with asyncio.timeout(configuration.investigation_timeout_seconds), client:
            result["provenance"].update(client.provenance)
            await execute("get_incident", {})
            no_progress = 0  # Initial metadata is context, not a diagnostic attempt.
            while provider_turns < configuration.max_provider_turns - 1:
                if no_progress >= configuration.max_no_progress_calls:
                    stop_reason = (
                        "Repeated unproductive diagnostics reached the no-progress limit; abstained safely."
                    )
                    break
                provider_turns += 1
                async with asyncio.timeout(configuration.provider_timeout_seconds):
                    decision, usage = await provider.next_action(
                        context,
                        client.schemas,
                        observations,
                        [item for item in result["evidence"] if item["kind"] != "incident"],
                    )
                usages.append(usage)
                result["provenance"]["model_called"] = provider.name in ("openai", "anthropic")
                try:
                    decision = AdaptiveDecision.model_validate(as_dict(decision))
                except ValidationError as error:
                    raise ValueError("Provider returned an invalid bounded diagnostic action") from error
                if decision.action == "assess":
                    break
                if len(requested) >= configuration.max_diagnostic_calls:
                    stop_reason = "Finite diagnostic call budget exhausted; abstained safely."
                    break
                request = decision.request
                arguments = {
                    key: value
                    for key, value in {"service": request.service, "q": request.q}.items()
                    if value is not None
                }
                key = json.dumps([request.name, arguments], sort_keys=True)
                if key in requested:
                    stop_reason = "Duplicate diagnostic request detected; abstained safely."
                    break
                await execute(request.name, arguments)
            else:
                stop_reason = "Finite provider turn budget exhausted; abstained safely."
            started = time.perf_counter()
            if stop_reason:
                assessment, _ = await DeterministicProvider().assess(
                    context, [item for item in result["evidence"] if item["kind"] != "incident"]
                )
                assessment.probable_failure_domain = ABSTAIN_DOMAIN
                assessment.limitations.append(stop_reason)
                result["provenance"]["stop_reason"] = stop_reason
            else:
                provider_turns += 1
                async with asyncio.timeout(configuration.provider_timeout_seconds):
                    assessment, usage = await provider.assess(
                        context, [item for item in result["evidence"] if item["kind"] != "incident"]
                    )
                usages.append(usage)
                result["provenance"]["model_called"] = provider.name in ("openai", "anthropic")
            assessment = validate_assessment(assessment, result["evidence"])
            if any(step["status"] == "failed" for step in result["steps"]):
                assessment.requires_human_review = True
                assessment.confidence = min(assessment.confidence, 0.6)
                assessment.limitations.append(
                    "One or more diagnostic tools failed; their state is unknown, not healthy."
                )
            assessment.limitations.append(
                f"Evidence-adaptive {provider.name} investigation through {client.transport}; frozen synthetic cutoff {cutoff}. No operational action was executed."
            )
            result["assessment"] = assessment.model_dump(mode="json")
            result["provenance"]["provider_turns"] = provider_turns
            result["provenance"]["tool_calls"] = len(requested)
            result["steps"].append(
                {
                    "id": f"STEP-{len(result['steps']) + 1:03d}",
                    "action": "Validated advisory assessment",
                    "tool": "assessment_validation",
                    "status": "complete",
                    "evidence_ids": assessment.supporting_evidence_ids,
                    "timestamp": utc_now(),
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "safe_arguments": {},
                    "transport": "local_validation",
                    "provider": provider.name,
                    "provider_turn": provider_turns,
                    "recorded": False,
                    "error": None,
                }
            )
            result["status"] = "complete"
            await publish()
            return result
    except BaseException:
        result["status"] = "failed"
        result["error"] = (
            "Adaptive investigation interrupted, unavailable, or invalid; no successful MCP execution is claimed."
        )
        await publish()
        raise


async def collect_investigation(
    store: Any,
    session_id: str,
    incident_id: str,
    provider: AssessmentProvider,
    on_progress: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    cutoff = await store.freeze_snapshot(session_id, incident_id)
    incident = await store.get_incident(session_id, incident_id, as_of=cutoff)
    if incident is None:
        raise ValueError("Incident not found in this demo session")
    # Generator tags are UI simulation controls, never diagnostic/model context.
    incident_context = sanitize(
        {
            key: value
            for key, value in as_dict(incident).items()
            if key in ("id", "summary", "severity", "started_at", "affected_services")
        }
    )
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
        "provenance": {
            "workflow": "initial_plan",
            "transport": "direct",
            "provider": provider.name,
            "model_called": provider.name in ("openai", "anthropic"),
            "snapshot_cutoff": cutoff,
            "snapshot_kind": "frozen_current",
            "recorded": False,
        },
    }
    tools = DirectDiagnosticClient(store, session_id, incident_id, cutoff)
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
            "safe_arguments": arguments,
            "transport": "direct",
            "provider": provider.name,
            "recorded": False,
        }
        result["steps"].append(step)
        await publish()
        try:
            returned = await asyncio.wait_for(tools.call(name, arguments), timeout=10)
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
    assessment, assessment_usage = await provider.assess(
        incident_context, [item for item in result["evidence"] if item["kind"] != "incident"]
    )
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
        "schema_version": 2,
        "generated_at": utc_now(),
        "provenance": {
            "pipeline": "creditops.investigator.collect_investigation",
            "provider": result["provider"],
            "model_called": result["provider"] != "deterministic",
            "telemetry_window": "complete synthetic scenario snapshot",
            "transport": result.get("provenance", {}).get("transport", "unknown"),
            "snapshot_cutoff": result.get("provenance", {}).get("snapshot_cutoff"),
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
    if envelope["sha256"] != artifact_digest(payload) or payload["schema_version"] not in (1, 2):
        raise InvalidAssessment("Replay artifact integrity check failed")
    result = payload["investigation"]
    if result["incident_id"] != incident_id or result["status"] != "complete":
        raise InvalidAssessment("Replay artifact incident or state mismatch")
    validated = validate_assessment(Assessment.model_validate(result["assessment"]), result["evidence"])
    result["assessment"] = validated.model_dump(mode="json")
    return payload


async def create_investigation(store: Any, session_id: str, incident_id: str, mode: str) -> dict[str, Any]:
    if mode not in ("REPLAY", "MCP_DEMO", "LIVE_AI"):
        raise ValueError("Investigation mode must be REPLAY, MCP_DEMO or LIVE_AI")
    if await store.get_incident(session_id, incident_id) is None:
        raise ValueError("Run an incident in this session before investigating")
    row = {
        "id": str(uuid4()),
        "incident_id": incident_id,
        "mode": mode,
        "status": "running",
        "provider": "deterministic" if mode in ("REPLAY", "MCP_DEMO") else Settings().ai_provider,
        "created_at": utc_now(),
        "steps": [],
        "evidence": [],
        "assessment": None,
        "error": None,
        "usage": {},
        "provenance": {},
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
            original_transport = payload["provenance"].get(
                "transport", artifact.get("provenance", {}).get("transport", "unknown")
            )
            row["provenance"] = {
                "workflow": "recorded_replay",
                "transport": "recorded_replay",
                "original_transport": original_transport,
                "provider": row["provider"],
                "model_called": False,
                "generating_model_called": payload["provenance"].get("model_called", False),
                "snapshot_kind": "complete_scenario",
                "snapshot_cutoff": payload["provenance"].get("snapshot_cutoff")
                or max((item["timestamp"] for item in artifact["evidence"]), default=None),
                "recorded": True,
                "artifact_schema_version": payload["schema_version"],
                "artifact_generated_at": payload["generated_at"],
            }
            for step in artifact["steps"]:
                row["steps"].append(
                    {**step, "transport": "recorded_replay", "provider": row["provider"], "recorded": True}
                )
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
            provider = (
                DeterministicProvider()
                if row["mode"] == "MCP_DEMO"
                else create_provider(Settings().ai_provider)
            )
            try:
                if row["mode"] == "LIVE_AI":
                    provider.enable_budget(Settings().live_max_spend_usd)
                await collect_adaptive_investigation(store, session_id, row["incident_id"], provider, persist)
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
