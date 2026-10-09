from creditops.evaluation import score_case


def test_evaluation_counts_invalid_citations_and_recall_separately():
    case = {
        "ground_truth_failure_domain": "domain",
        "required_evidence_ids": ["A", "B"],
        "requires_human_review": False,
    }
    assessment = {
        "probable_failure_domain": "domain",
        "supporting_evidence_ids": ["A", "INVENTED"],
        "alternative_hypotheses": [],
        "relevant_runbooks": [],
        "similar_incidents": [],
        "requires_human_review": False,
    }
    score = score_case(case, assessment, {"A", "B"}, latency_ms=25, tool_errors=1, tool_calls=10)
    assert score["top1_correct"]
    assert score["top3_correct"]
    assert score["required_evidence_recall"] == 0.5
    assert score["invalid_evidence_citations"] == 1
    assert score["hallucinated_evidence_count"] == 1
    assert score["tool_error_rate"] == 0.1


def test_abstention_requires_both_abstain_and_escalation():
    case = {
        "ground_truth_failure_domain": "insufficient evidence",
        "required_evidence_ids": [],
        "requires_human_review": True,
    }
    assessment = {
        "probable_failure_domain": "insufficient evidence",
        "supporting_evidence_ids": [],
        "alternative_hypotheses": [],
        "relevant_runbooks": [],
        "similar_incidents": [],
        "requires_human_review": True,
    }
    assert score_case(case, assessment, set())["correct_abstention"]
    assessment["requires_human_review"] = False
    assert not score_case(case, assessment, set())["correct_abstention"]
