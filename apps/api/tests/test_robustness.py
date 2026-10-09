from creditops.robustness import evaluate_robustness


def test_predeclared_synthetic_robustness_expectations():
    result = evaluate_robustness()
    assert result["case_count"] == 13
    assert result["failed"] == 0, [row for row in result["results"] if not row["passed"]]
    assert result["abstentions"] == 4
    assert result["invalid_reference_count"] == 0
    assert result["failed_substantive_checks"] == 0
    assert result["live_provider_execution"] == "NOT RUN"
