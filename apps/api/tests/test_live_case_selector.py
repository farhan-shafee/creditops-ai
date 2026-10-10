"""Offline CLI selection: reject ambiguity before any execution side effect."""

import json

import pytest
from test_live_runner import runner


def selector_arguments(*selection):
    return [
        "--provider", "openai", "--model", "gpt-5.4-mini-2026-03-17",
        "--max-tool-calls", "12", "--max-provider-turns", "12",
        "--max-spend-usd", "2", "--timeout-seconds", "300",
        "--provider-timeout-seconds", "90", "--diagnostic-timeout-seconds", "15",
        "--total-timeout-seconds", "330", "--input-price-ceiling", "0.75",
        "--output-price-ceiling", "4.50", *selection,
    ]


@pytest.mark.parametrize("case_id", ["INC-DEMO-001", "INC-DEMO-002", "INC-DEMO-003"])
async def test_explicit_case_dry_run_binds_only_selected_id_without_execution(
    case_id, monkeypatch, tmp_path, capsys
):
    def forbidden(*args, **kwargs):
        raise AssertionError("Dry-run crossed the execution boundary")

    monkeypatch.setattr(runner, "create_provider", forbidden)
    monkeypatch.setattr(runner, "Store", forbidden)
    monkeypatch.setattr(runner, "ExperimentLedger", forbidden)
    monkeypatch.setattr(runner, "source_commit", lambda: "offline-source")
    output = tmp_path / "must-not-be-created"
    args = runner.parse_args(selector_arguments("--case-id", case_id, "--output-directory", str(output)))
    receipt = await runner.run(args)
    assert receipt["configuration"]["case_ids"] == [case_id]
    assert receipt["configuration"]["stop_on_tool_error"] is True
    assert receipt["execution"] == "NOT RUN" and receipt["results"] == []
    assert json.loads(capsys.readouterr().out)["configuration"]["case_ids"] == [case_id]
    assert not output.exists()


@pytest.mark.parametrize(
    "selection",
    [
        ("--case-id", "INC-DEMO-004"),
        ("--case-id", "INC-DEMO-002", "--case-count", "1"),
        ("--case-id", "INC-DEMO-002", "--stage", "remaining"),
        ("--case-id", "INC-DEMO-003", "--continue-reviewed"),
        ("--case-id", "INC-DEMO-002", "--stage", "remaining", "--continue-reviewed"),
        (),
    ],
)
def test_invalid_or_ambiguous_selection_fails_before_execution(selection, monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid selection crossed the execution boundary")

    monkeypatch.setattr(runner, "Store", forbidden)
    monkeypatch.setattr(runner, "create_provider", forbidden)
    monkeypatch.setattr(runner, "ExperimentLedger", forbidden)
    with pytest.raises(SystemExit) as rejected:
        runner.parse_args(selector_arguments(*selection, "--output-directory", str(tmp_path)))
    assert rejected.value.code == 2
    assert list(tmp_path.iterdir()) == []


async def test_legacy_prefix_plan_and_review_requirements_remain_unchanged(tmp_path):
    args = runner.parse_args(selector_arguments("--case-count", "3", "--output-directory", str(tmp_path)))
    receipt = await runner.run(args)
    assert receipt["configuration"]["case_ids"] == ["INC-DEMO-001", "INC-DEMO-002", "INC-DEMO-003"]
    with pytest.raises(SystemExit):
        runner.parse_args(selector_arguments("--case-count", "3", "--stage", "remaining"))
    with pytest.raises(SystemExit):
        runner.parse_args(selector_arguments("--case-count", "1", "--stage", "remaining", "--continue-reviewed"))
    reviewed = runner.parse_args(selector_arguments("--case-count", "3", "--stage", "remaining", "--continue-reviewed"))
    assert reviewed.stage == "remaining" and reviewed.case_count == 3
    assert list(tmp_path.iterdir()) == []
