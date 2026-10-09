"""Regression checks for quote observation time and quote/order identity."""

import pytest
from creditops.business import observation_time, reduce_request
from creditops.business_seed import make_business_seed
from creditops.models import SyntheticRFQ
from creditops.seed import timestamp


def request_events(case):
    fixture = make_business_seed()
    row = next(row for row in fixture["rfqs"] if row["incident_id"] == f"INC-DEMO-{case:03}")
    rfq = SyntheticRFQ.model_validate(row["payload"])
    events = [
        {
            "id": item["id"],
            "timestamp": item["timestamp"],
            "event_type": item["data"]["event_type"],
            "data": dict(item["data"]),
        }
        for item in fixture["events"]
        if item["data"]["rfq_id"] == rfq.id
    ]
    return rfq, events


@pytest.mark.parametrize("case,status,age", [(1, "EXPIRED", 120000), (2, "ACCEPTED", 132000)])
def test_quote_age_uses_snapshot_cutoff_without_changing_observed_state(case, status, age):
    rfq, events = request_events(case)
    result = reduce_request(rfq, events, observation_time(timestamp(144)))
    assert result["quote"].freshness_ms == age
    assert result["quote"].status == status
    if case == 2:
        assert result["quote"].accepted_at == observation_time(timestamp(24))
        assert result["order"].status == "UNKNOWN"


@pytest.mark.parametrize("quote_id", ["QUOTE-OTHER", None])
def test_order_submission_requires_the_accepted_quote_identity(quote_id):
    rfq, events = request_events(2)
    submission = next(item for item in events if item["event_type"] == "ORDER_SUBMITTED")
    if quote_id is None:
        del submission["data"]["quote_id"]
    else:
        submission["data"]["quote_id"] = quote_id
    with pytest.raises(ValueError, match="quote identity"):
        reduce_request(rfq, events, observation_time(timestamp(144)))
