"""Dry-run or explicitly execute the existing bounded MCP investigator.

--execute-paid requires owner authorization. Review the first case before continuation.
"""

import argparse
import asyncio
import copy
import json
import math
import os
import subprocess
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from creditops.investigator import collect_adaptive_investigation
from creditops.providers import create_provider
from creditops.security import sanitize
from creditops.settings import PROJECT_ROOT, Settings, get_settings
from creditops.store import Store
from sqlalchemy.engine import make_url

CASE_IDS = ["INC-DEMO-001", "INC-DEMO-002", "INC-DEMO-003"]


def now():
    return datetime.now(UTC).isoformat()


def write_json(path, payload):
    """Replace this active receipt/ledger only; earlier runs have distinct paths."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(sanitize(payload), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


class ExperimentLedger:
    def __init__(self, path, configuration, stage, reviewed):
        self.path = path
        configuration = json.loads(json.dumps(configuration))
        if stage == "first":
            self.data = {
                "configuration": configuration,
                "reserved_spend_usd": "0",
                "elapsed_seconds": 0,
                "state": "PREPARING",
                "attempts": [],
            }
            with path.open("x", encoding="utf-8") as handle:
                json.dump(self.data, handle)
        else:
            self.data = json.loads(path.read_text(encoding="utf-8"))
            attempts = self.data["attempts"]
            if (
                not reviewed
                or self.data["configuration"] != configuration
                or self.data["state"] != "AWAITING_FIRST_CASE_REVIEW"
                or len(attempts) != 1
                or attempts[0]["incident_id"] != CASE_IDS[0]
                or attempts[0]["status"] != "complete"
            ):
                raise ValueError("Continuation requires a completed reviewed first case and unchanged limits")

    @property
    def reserved(self):
        return Decimal(self.data["reserved_spend_usd"])

    def save(self):
        write_json(self.path, self.data)

    def reserve(self, total):
        if (
            not total.is_finite()
            or total < self.reserved
            or total > Decimal(str(self.data["configuration"]["maximum_spend_usd"]))
        ):
            raise ValueError("Reservation cannot decrease or exceed the shared maximum")
        self.data["reserved_spend_usd"] = str(total)
        self.save()  # Durable BEFORE any provider request.


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("openai", "anthropic"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--case-count", type=int, choices=range(1, 4), required=True)
    parser.add_argument("--max-tool-calls", type=int, choices=range(2, 17), required=True)
    parser.add_argument("--max-provider-turns", type=int, choices=range(2, 17), required=True)
    parser.add_argument("--max-spend-usd", type=float, required=True)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("--provider-timeout-seconds", type=float, default=90)
    parser.add_argument("--diagnostic-timeout-seconds", type=float, default=15)
    parser.add_argument("--total-timeout-seconds", type=float, default=900)
    parser.add_argument("--input-price-ceiling", type=float, required=True)
    parser.add_argument("--output-price-ceiling", type=float, required=True)
    parser.add_argument("--experiment-id", type=UUID)
    parser.add_argument("--stage", choices=("first", "remaining"), default="first")
    parser.add_argument("--continue-reviewed", action="store_true")
    boundary = parser.add_mutually_exclusive_group()
    boundary.add_argument("--execute-paid", action="store_true")
    boundary.add_argument("--preflight", action="store_true", help="Local identity check; no model calls")
    parser.add_argument("--output-directory", type=Path, default=PROJECT_ROOT / "artifacts/live-verification")
    args = parser.parse_args(argv)
    ranges = [
        (args.max_spend_usd, 0, 10),
        (args.timeout_seconds, 0, 300),
        (args.provider_timeout_seconds, 0, 120),
        (args.diagnostic_timeout_seconds, 0, 30),
        (args.total_timeout_seconds, 0, 900),
        (args.input_price_ceiling, 0, 1000),
        (args.output_price_ceiling, 0, 1000),
    ]
    if (
        not args.model.strip()
        or len(args.model) > 120
        or any(not math.isfinite(v) or not lo < v <= hi for v, lo, hi in ranges)
        or args.timeout_seconds < 1
        or args.provider_timeout_seconds > args.timeout_seconds
        or args.total_timeout_seconds < args.timeout_seconds
        or (args.execute_paid and args.experiment_id is None)
        or (args.stage == "remaining" and (args.case_count < 2 or not args.continue_reviewed))
    ):
        parser.error(
            "Finite positive limits, paid experiment identity and explicit continuation review are required"
        )
    if args.provider == "openai" and args.model in ("gpt-5.4-mini", "gpt-5.4-mini-2026-03-17"):
        if args.input_price_ceiling < 0.75 or args.output_price_ceiling < 4.50:
            parser.error("The candidate's standard documented rates exceed these ceilings")
    return args


def validate_local_resources(configuration):
    """Reject before Store construction, connection, initialization or query."""
    url = make_url(configuration.database_url)
    if url.drivername.startswith("sqlite"):
        allowed = Path(url.database or "").resolve() == (PROJECT_ROOT / "artifacts/creditops.db").resolve()
        identity = "repository artifacts/creditops.db"
    else:
        allowed = (
            url.drivername in ("postgresql", "postgresql+asyncpg")
            and url.host in ("127.0.0.1", "localhost")
            and url.port == 15432
            and url.database == "creditops"
        )
        identity = "local Compose creditops database on port 15432"
    api = urlsplit(configuration.mcp_api_url)
    if not allowed:
        raise ValueError("Only the local CreditOps demo database is allowed")
    if (
        api.scheme != "http"
        or api.hostname not in ("127.0.0.1", "localhost")
        or api.port not in (8000, 18000)
        or api.username
        or api.password
        or api.path not in ("", "/")
        or api.query
        or api.fragment
        or configuration.embeddings_enabled
    ):
        raise ValueError("Only the local synthetic API without paid extra features is allowed")
    return {"database": identity, "api": configuration.mcp_api_url, "embeddings_enabled": False}


async def verify_api_identity(store, configuration, session_id):
    """Fresh session row proves shared persistence; no seed, migration or reset."""
    identifier = str(uuid4())
    marker = {
        "id": identifier,
        "incident_id": CASE_IDS[0],
        "mode": "LIVE_AI",
        "status": "preflight",
        "provider": "none",
        "created_at": now(),
        "steps": [],
        "evidence": [],
        "assessment": None,
        "error": None,
        "usage": {},
        "provenance": {"identity_check": identifier, "model_called": False},
    }
    await store.save_investigation(session_id, marker)
    async with httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False) as client:
        health = await client.get(configuration.mcp_api_url.rstrip("/") + "/health")
        health.raise_for_status()
        health_data = health.json()
        if (
            health_data.get("environment") != "synthetic"
            or health_data.get("diagnostic_capabilities") != "read-only"
            or health_data.get("embeddings_enabled") is not False
        ):
            raise ValueError(
                "Local API must confirm synthetic read-only diagnostics with embeddings disabled"
            )
        response = await client.get(
            configuration.mcp_api_url.rstrip("/") + f"/api/investigations/{identifier}",
            headers={"X-Demo-Session": session_id},
        )
        response.raise_for_status()
        if response.json().get("provenance", {}).get("identity_check") != identifier:
            raise ValueError("API and runner database identity was not established")
    return {"verified": True, "session_id": session_id, "record_id": identifier, "checked_at": now()}


def source_commit():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True).strip()


async def run(args):
    plan = {
        "provider": args.provider,
        "model": args.model,
        "case_ids": CASE_IDS[: args.case_count],
        "max_tool_calls_per_case": args.max_tool_calls,
        "max_provider_turns_per_case": args.max_provider_turns,
        "maximum_spend_usd": str(args.max_spend_usd),
        "timeout_seconds_per_case": args.timeout_seconds,
        "provider_timeout_seconds": args.provider_timeout_seconds,
        "diagnostic_timeout_seconds": args.diagnostic_timeout_seconds,
        "total_active_timeout_seconds": args.total_timeout_seconds,
        "input_usd_per_million": args.input_price_ceiling,
        "output_usd_per_million": args.output_price_ceiling,
        "max_output_tokens_per_call": 5000,
        "snapshot_policy": "completed synthetic fixture; frozen once per case",
        "transport": "mcp_stdio",
        "source_commit": source_commit(),
        "retries": 0,
        "stop_on_tool_error": True,
    }
    receipt = {"execution": "NOT RUN", "quality": "UNVERIFIED", "configuration": plan, "results": []}
    if not args.execute_paid and not args.preflight:
        print(json.dumps(receipt, indent=2))
        return receipt
    for key, value in {
        f"{args.provider.upper()}_MODEL": args.model,
        f"{args.provider.upper()}_INPUT_USD_PER_MILLION": args.input_price_ceiling,
        f"{args.provider.upper()}_OUTPUT_USD_PER_MILLION": args.output_price_ceiling,
        "PROVIDER_TIMEOUT_SECONDS": args.provider_timeout_seconds,
        "DIAGNOSTIC_TIMEOUT_SECONDS": args.diagnostic_timeout_seconds,
    }.items():
        os.environ[key] = str(value)
    get_settings.cache_clear()
    configuration = Settings(
        max_diagnostic_calls=args.max_tool_calls,
        max_provider_turns=args.max_provider_turns,
        investigation_timeout_seconds=args.timeout_seconds,
    )
    plan["local_resources"] = validate_local_resources(configuration)
    if args.preflight:
        store = Store(configuration.database_url)
        try:
            async with asyncio.timeout(15):
                receipt["local_identity"] = await verify_api_identity(store, configuration, str(uuid4()))
            receipt["execution"] = "LOCAL_PREFLIGHT_ONLY_NO_MODEL_CALLS"
        finally:
            await store.close()
        print(json.dumps(receipt, indent=2))
        return receipt
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=PROJECT_ROOT, text=True).strip():
        raise ValueError("Paid execution requires a clean reviewed source checkout")
    root = args.output_directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    experiment = str(args.experiment_id)
    lock_path = root / f"{experiment}.lock"
    with lock_path.open("x", encoding="utf-8") as lock:
        lock.write(str(os.getpid()))
    provider = store = ledger = None
    started = time.monotonic()
    path = root / f"run-{uuid4()}.json"
    receipt.update(
        run_id=path.stem,
        experiment_id=experiment,
        started_at=now(),
        stage=args.stage,
        estimated_cost_usd=None,
        reserved_spend_usd=None,
        cost_scope="current invocation; reserved spend covers the shared experiment",
    )
    try:
        path.touch(exist_ok=False)
        write_json(path, receipt)
        ledger = ExperimentLedger(
            root / f"experiment-{experiment}.json", plan, args.stage, args.continue_reviewed
        )
        ledger.data["state"] = "RUNNING"
        ledger.save()
        store = Store(configuration.database_url)
        session_id = str(uuid4())
        async with asyncio.timeout(min(15, args.total_timeout_seconds - ledger.data["elapsed_seconds"])):
            receipt["local_identity"] = await verify_api_identity(store, configuration, session_id)
        provider = create_provider(args.provider)

        def reserve(total):
            ledger.reserve(total)
            receipt["reserved_spend_usd"] = str(total)
            write_json(path, receipt)

        provider.enable_budget(
            args.max_spend_usd, reserved_spend=ledger.reserved, reservation_callback=reserve
        )
        cases = CASE_IDS[:1] if args.stage == "first" else CASE_IDS[1 : args.case_count]
        for incident_id in cases:
            remaining = (
                args.total_timeout_seconds - ledger.data["elapsed_seconds"] - (time.monotonic() - started)
            )
            if remaining <= 0:
                raise TimeoutError("Shared experiment deadline exhausted")
            attempt = {"incident_id": incident_id, "status": "running", "run_id": receipt["run_id"]}
            ledger.data["attempts"].append(attempt)
            ledger.save()
            receipt["results"].append({"incident_id": incident_id, "status": "running"})
            write_json(path, receipt)

            async def progress(result):
                saved = copy.deepcopy(result)
                saved["mode"] = "LIVE_AI"
                saved["provenance"].update(
                    session_id=session_id,
                    experiment_id=experiment,
                    run_id=receipt["run_id"],
                    source_commit=plan["source_commit"],
                )
                receipt["results"][-1] = saved
                write_json(path, receipt)
                await store.save_investigation(session_id, saved)

            async with asyncio.timeout(min(args.timeout_seconds, remaining)):
                await store.activate_case(session_id, incident_id)
                result = await collect_adaptive_investigation(
                    store,
                    session_id,
                    incident_id,
                    provider,
                    on_progress=progress,
                    limits=configuration,
                    stop_on_tool_error=True,
                )
                await progress(result)
            if (
                not result.get("provider_proposal")
                or not result.get("provider_calls")
                or any(step["status"] == "failed" for step in result["steps"])
                or result.get("validation_outcome", {}).get("status") == "rejected"
                or result.get("provenance", {}).get("stop_reason")
            ):
                raise ValueError("Case lacks valid inspectable execution; stop for offline review")
            attempt["status"] = "complete"
            ledger.save()
        receipt["execution"] = (
            "AWAITING_FIRST_CASE_REVIEW"
            if args.stage == "first" and args.case_count > 1
            else "COMPLETED_APPROVED_CASES"
        )
        ledger.data["state"] = receipt["execution"]
        receipt["quality"] = "REQUIRES_SEPARATE_PROPOSAL_AND_SYSTEM_REVIEW"
    except BaseException as error:
        receipt["execution"] = "STOPPED"
        receipt["error_category"] = type(error).__name__
        if ledger:
            ledger.data["state"] = "STOPPED"
            if ledger.data["attempts"] and ledger.data["attempts"][-1]["status"] == "running":
                ledger.data["attempts"][-1]["status"] = "interrupted_or_failed"
        if receipt["results"] and receipt["results"][-1]["status"] == "running":
            receipt["results"][-1]["status"] = "interrupted_or_failed"
        raise
    finally:
        receipt["ended_at"] = now()
        receipt["duration_seconds"] = round(time.monotonic() - started, 3)
        receipt["provider_calls"] = copy.deepcopy(getattr(provider, "execution_receipts", []))
        costs = [call.get("usage", {}).get("estimated_cost_usd") for call in receipt["provider_calls"]]
        receipt["known_cost_subtotal_usd"] = (
            sum(c for c in costs if c is not None) if any(c is not None for c in costs) else None
        )
        receipt["estimated_cost_usd"] = sum(costs) if costs and all(c is not None for c in costs) else None
        try:
            try:
                if ledger:
                    receipt["reserved_spend_usd"] = str(ledger.reserved)
                    ledger.data["elapsed_seconds"] += receipt["duration_seconds"]
                    ledger.save()
            finally:
                write_json(path, receipt)
                write_json(root / "latest.json", {"run_id": receipt["run_id"], "receipt": path.name})
        finally:
            try:
                if provider:
                    await provider.client.close()
            finally:
                try:
                    if store:
                        await store.close()
                finally:
                    lock_path.unlink()
    print(json.dumps({k: v for k, v in receipt.items() if k not in ("results", "provider_calls")}, indent=2))
    return receipt


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
