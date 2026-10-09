"""Run offline developer-authored robustness fixtures; never contacts a provider."""

from pathlib import Path

from creditops.robustness import evaluate_robustness

if __name__ == "__main__":
    report = evaluate_robustness(Path(__file__).resolve().parents[1] / "artifacts/robustness")
    print(
        f"{report['passed']}/{report['case_count']} passed; {report['failed']} failed; {report['abstentions']} abstentions; {report['invalid_reference_count']} invalid references; {report['failed_substantive_checks']} failed substantive checks. Live provider NOT RUN."
    )
    raise SystemExit(1 if report["failed"] else 0)
