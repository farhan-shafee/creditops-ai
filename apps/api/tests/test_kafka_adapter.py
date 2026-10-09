"""Adapters must fall back without a broker and accept only synthetic envelopes."""

import pytest


async def test_persisted_adapter_requires_no_broker():
    try:
        from creditops.telemetry import SyntheticTelemetryAdapter
    except ImportError:
        pytest.fail("Synthetic telemetry adapter is missing")
    adapter = SyntheticTelemetryAdapter(mode="persisted", bootstrap_servers="127.0.0.1:1")
    await adapter.start()
    assert adapter.health()["mode"] == "persisted"
    assert adapter.health()["broker_connected"] is False
    await adapter.close()


async def test_synthetic_adapter_rejects_external_or_malformed_envelopes():
    try:
        from creditops.telemetry import validate_envelope
    except ImportError:
        pytest.fail("Synthetic stream envelope validator is missing")
    with pytest.raises(ValueError):
        validate_envelope({"environment": "production", "evidence_id": "REAL-001", "data": {}})
    with pytest.raises(ValueError):
        validate_envelope({"environment": "synthetic", "evidence_id": "LOG-001", "data": "bad"})
    row = validate_envelope(
        {"environment": "synthetic", "evidence_id": "LOG-001-001", "data": {"message": "sample"}}
    )
    assert row["evidence_id"] == "LOG-001-001"


def test_synthetic_envelope_accepts_actual_rich_metric_identifiers():
    from creditops.telemetry import validate_envelope

    id = "METRIC-001-SERIES-QUOTE-SERVICE-REQUEST_LATENCY_P95_MS-5"
    row = validate_envelope(
        {
            "environment": "synthetic",
            "evidence_id": id,
            "data": {"metric": "request_latency_p95_ms", "value": 1450},
        }
    )
    assert row["evidence_id"] == id
