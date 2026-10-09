"""Offline tests of the existing paid runner's authorization and durable boundaries."""

import importlib.util
import json
from decimal import Decimal
from uuid import uuid4

import pytest
from creditops.settings import PROJECT_ROOT, Settings

spec = importlib.util.spec_from_file_location("verify_live", PROJECT_ROOT / "scripts/verify_live.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def arguments(*extra):
    return runner.parse_args(
        [
            "--provider",
            "openai",
            "--model",
            "gpt-5.4-mini-2026-03-17",
            "--case-count",
            "3",
            "--max-tool-calls",
            "12",
            "--max-provider-turns",
            "12",
            "--max-spend-usd",
            "5",
            "--timeout-seconds",
            "300",
            "--input-price-ceiling",
            "0.75",
            "--output-price-ceiling",
            "4.50",
            *extra,
        ]
    )


async def test_dry_run_never_creates_provider_store_or_ledger(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("Dry-run crossed the execution boundary")

    monkeypatch.setattr(runner, "create_provider", forbidden)
    monkeypatch.setattr(runner, "Store", forbidden)
    receipt = await runner.run(arguments("--output-directory", str(tmp_path)))
    assert receipt["execution"] == "NOT RUN"
    assert receipt["results"] == []
    assert list(tmp_path.iterdir()) == []


async def test_dry_run_always_advertises_strict_diagnostic_stopping(monkeypatch, tmp_path):
    """This runner owns the policy; an environment value cannot disable it."""
    monkeypatch.setenv("STOP_ON_TOOL_ERROR", "false")
    receipt = await runner.run(arguments("--output-directory", str(tmp_path)))
    assert receipt["configuration"]["stop_on_tool_error"] is True
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://u:p@remote.example/creditops",
        "postgresql+asyncpg://u:p@127.0.0.1:15432/unrelated",
        "sqlite+aiosqlite:///./unrelated.db",
    ],
)
def test_unrelated_database_is_rejected_before_it_can_be_initialized(url):
    with pytest.raises(ValueError, match="local CreditOps"):
        runner.validate_local_resources(Settings(database_url=url))


def test_remote_api_and_paid_extra_features_are_rejected():
    with pytest.raises(ValueError):
        runner.validate_local_resources(Settings(mcp_api_url="https://remote.example"))
    with pytest.raises(ValueError):
        runner.validate_local_resources(Settings(embeddings_enabled=True))


def test_reservations_survive_continuation_and_first_case_cannot_repeat(tmp_path):
    config = {"maximum_spend_usd": "5", "case_ids": runner.CASE_IDS}
    path = tmp_path / "experiment.json"
    ledger = runner.ExperimentLedger(path, config, "first", False)
    ledger.reserve(Decimal("0.12"))
    ledger.data["attempts"] = [{"incident_id": "INC-DEMO-001", "status": "complete"}]
    ledger.data["state"] = "AWAITING_FIRST_CASE_REVIEW"
    ledger.save()
    with pytest.raises(FileExistsError):
        runner.ExperimentLedger(path, config, "first", False)
    with pytest.raises(ValueError):
        runner.ExperimentLedger(path, config, "remaining", False)
    continued = runner.ExperimentLedger(path, config, "remaining", True)
    assert continued.reserved == Decimal("0.12")
    continued.reserve(Decimal("0.24"))
    assert runner.ExperimentLedger(path, config, "remaining", True).reserved == Decimal("0.24")
    with pytest.raises(ValueError):
        continued.reserve(Decimal("0.10"))
    with pytest.raises(ValueError):
        continued.reserve(Decimal("5.01"))


def test_changed_limits_or_interrupted_first_case_prevent_continuation(tmp_path):
    path = tmp_path / "experiment.json"
    config = {"maximum_spend_usd": "5", "case_ids": runner.CASE_IDS}
    ledger = runner.ExperimentLedger(path, config, "first", False)
    ledger.reserve(Decimal("0.12"))
    ledger.data["attempts"] = [{"incident_id": "INC-DEMO-001", "status": "running"}]
    ledger.save()
    with pytest.raises(ValueError):
        runner.ExperimentLedger(path, config, "remaining", True)
    ledger.data["state"] = "AWAITING_FIRST_CASE_REVIEW"
    ledger.data["attempts"][0]["status"] = "complete"
    ledger.save()
    with pytest.raises(ValueError):
        runner.ExperimentLedger(path, {**config, "maximum_spend_usd": "10"}, "remaining", True)


def test_live_limits_reject_nan_prices_and_require_experiment_identity():
    with pytest.raises(SystemExit):
        arguments("--execute-paid")
    with pytest.raises(SystemExit):
        arguments("--input-price-ceiling", "nan")


@pytest.mark.parametrize("write_failure", [False, True])
@pytest.mark.parametrize("reported_cost", [None, 0.00018])
async def test_interrupted_attempt_retains_usage_cost_and_closes_resources(
    monkeypatch, tmp_path, write_failure, reported_cost
):
    """Only the network/orchestrator is substituted; durable runner code is real."""
    monkeypatch.setenv(
        "DATABASE_URL", f"sqlite+aiosqlite:///{(PROJECT_ROOT / 'artifacts/creditops.db').as_posix()}"
    )
    monkeypatch.setenv("MCP_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "false")
    closed = []

    class OfflineClient:
        async def close(self):
            closed.append("provider")

    class OfflineProvider:
        client = OfflineClient()
        execution_receipts = [{"status": "offline_fixture", "usage": {"estimated_cost_usd": reported_cost}}]

        def enable_budget(self, *args, **kwargs):
            pass

    class OfflineStore:
        def __init__(self, *args):
            pass

        async def activate_case(self, *args):
            pass

        async def close(self):
            closed.append("store")

    async def identity(*args):
        return {"verified": True, "offline_test": True}

    async def interrupted(*args, **kwargs):
        raise TimeoutError("offline interruption")

    monkeypatch.setattr(runner, "source_commit", lambda: "offline-test-source")
    monkeypatch.setattr(runner.subprocess, "check_output", lambda *args, **kwargs: "")
    monkeypatch.setattr(runner, "create_provider", lambda *args: OfflineProvider())
    monkeypatch.setattr(runner, "Store", OfflineStore)
    monkeypatch.setattr(runner, "verify_api_identity", identity)
    monkeypatch.setattr(runner, "collect_adaptive_investigation", interrupted)
    original_write = runner.write_json

    def fail_final_write(path, payload):
        if write_failure and "ended_at" in payload:
            raise OSError("offline disk failure")
        original_write(path, payload)

    monkeypatch.setattr(runner, "write_json", fail_final_write)
    with pytest.raises(OSError if write_failure else TimeoutError):
        await runner.run(
            arguments("--execute-paid", "--experiment-id", str(uuid4()), "--output-directory", str(tmp_path))
        )
    assert closed == ["provider", "store"]
    assert not list(tmp_path.glob("*.lock"))
    ledger = json.loads(next(tmp_path.glob("experiment-*.json")).read_text())
    assert ledger["state"] == "STOPPED"
    assert ledger["attempts"][0]["status"] == "interrupted_or_failed"
    if not write_failure:
        receipt = json.loads(next(tmp_path.glob("run-*.json")).read_text())
        assert receipt["execution"] == "STOPPED"
        assert receipt["estimated_cost_usd"] == reported_cost
        assert receipt["known_cost_subtotal_usd"] == reported_cost
        assert receipt["results"][0]["status"] == "interrupted_or_failed"
