"""Receipt regressions use the installed SDK against an offline HTTP transport."""

import asyncio
import json
from decimal import Decimal

import httpx
import pytest
from creditops.providers import OpenAIProvider, ProviderUnavailable, usage_record
from creditops.security import sanitize
from openai import APITimeoutError, InternalServerError
from pydantic import ValidationError

PLAN = {
    "requests": [{"name": "query_metrics", "service": None, "metric": None, "start": None, "end": None}]
}


def response_payload(*, usage=None, text=None, status="completed"):
    return {
        "id": "resp_receipt_offline",
        "object": "response",
        "created_at": 1,
        "status": status,
        "model": "returned-offline-snapshot",
        "service_tier": "default",
        "output": [
            {
                "id": "msg_receipt_offline",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text or json.dumps(PLAN), "annotations": []}],
            }
        ],
        "usage": usage,
    }


async def offline_provider(monkeypatch, respond):
    monkeypatch.setenv("OPENAI_API_KEY", "demo-offline-key")
    monkeypatch.setenv("OPENAI_MODEL", "requested-offline-model")
    monkeypatch.setenv("OPENAI_INPUT_USD_PER_MILLION", "0.75")
    monkeypatch.setenv("OPENAI_OUTPUT_USD_PER_MILLION", "4.50")
    provider = OpenAIProvider()
    original = provider.client
    provider.client = original.with_options(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    await original.close()
    return provider


def test_missing_usage_remains_unknown_despite_configured_prices(monkeypatch):
    monkeypatch.setenv("OPENAI_INPUT_USD_PER_MILLION", "0.75")
    monkeypatch.setenv("OPENAI_OUTPUT_USD_PER_MILLION", "4.50")
    usage = usage_record("openai", None, None)
    assert usage["total_tokens"] is None
    assert usage["estimated_cost_usd"] is None
    assert usage["usage_status"] == "unknown"


async def test_sdk_receipt_records_public_metadata_and_reserves_before_request(monkeypatch):
    events = []

    def respond(request):
        events.append(("request", json.loads(request.content)))
        return httpx.Response(
            200,
            headers={"x-request-id": "req_offline_receipt", "authorization": "never-store-this-header"},
            json=response_payload(
                usage={
                    "input_tokens": 100,
                    "output_tokens": 40,
                    "total_tokens": 140,
                    "input_tokens_details": {"cached_tokens": 20, "cache_write_tokens": 30},
                    "output_tokens_details": {"reasoning_tokens": 10},
                }
            ),
        )

    provider = await offline_provider(monkeypatch, respond)
    provider.enable_budget(1, reservation_callback=lambda total: events.append(("reserved", total)))
    try:
        parsed, usage = await provider.plan({"summary": "synthetic latency"})
        receipt = provider.execution_receipts[0]
        assert parsed.requests[0].name == "query_metrics"
        assert [event[0] for event in events] == ["reserved", "request"]
        assert events[1][1]["service_tier"] == "default"
        assert receipt["requested_model"] == "requested-offline-model"
        assert receipt["returned_model"] == "returned-offline-snapshot"
        assert receipt["response_id"] == "resp_receipt_offline"
        assert receipt["request_id"] == "req_offline_receipt"
        assert receipt["provider_created_at"] == 1
        assert receipt["status"] == "success"
        assert receipt["request_started"] is True
        assert receipt["started_at"] <= receipt["ended_at"]
        assert receipt["duration_ms"] >= 0
        assert receipt["usage"]["input_tokens_details"] == {"cached_tokens": 20, "cache_write_tokens": 30}
        assert receipt["usage"]["output_tokens_details"] == {"reasoning_tokens": 10}
        assert receipt["usage"]["reported_total_tokens"] == 140
        assert usage["estimated_cost_usd"] == 0.000255
        assert Decimal(receipt["reserved_cost_usd"]) > Decimal("0.0225")
        persisted = sanitize(receipt)
        assert isinstance(persisted["input_tokens_ceiling"], int)
        assert not isinstance(persisted["input_tokens_ceiling"], bool)
        assert persisted["input_tokens_ceiling"] > 0
        assert "input_token_ceiling" not in receipt
        assert "never-store-this-header" not in json.dumps(receipt)
    finally:
        await provider.client.close()


async def test_parse_failure_retains_usage_and_response_identity(monkeypatch):
    def respond(request):
        return httpx.Response(
            200,
            headers={"x-request-id": "req_bad_json"},
            json=response_payload(
                usage={"input_tokens": 100, "output_tokens": 40, "total_tokens": 140},
                text='{"requests": "password=do-not-persist"}',
            ),
        )

    provider = await offline_provider(monkeypatch, respond)
    provider.enable_budget(1)
    try:
        with pytest.raises(ValidationError):
            await provider.plan({})
        receipt = provider.execution_receipts[0]
        assert receipt["status"] == "parse_error"
        assert receipt["response_id"] == "resp_receipt_offline"
        assert receipt["request_id"] == "req_bad_json"
        assert receipt["usage"]["total_tokens"] == 140
        assert receipt["usage"]["estimated_cost_usd"] == 0.000255
        assert "do-not-persist" not in json.dumps(receipt)
        assert receipt["structured_output"] is None
    finally:
        await provider.client.close()


async def test_success_without_usage_is_inspectable_but_cost_unknown(monkeypatch):
    provider = await offline_provider(
        monkeypatch, lambda request: httpx.Response(200, json=response_payload())
    )
    provider.enable_budget(1)
    try:
        _, usage = await provider.plan({})
        receipt = provider.execution_receipts[0]
        assert receipt["status"] == "success"
        assert receipt["usage"]["usage_status"] == "unknown"
        assert usage["input_tokens"] is None
        assert usage["output_tokens"] is None
        assert usage["estimated_cost_usd"] is None
        assert receipt["charge_status"] == "unknown"
    finally:
        await provider.client.close()


async def test_provider_failed_response_is_not_misclassified_as_incomplete(monkeypatch):
    payload = response_payload(status="failed")
    payload["output"] = []
    payload["error"] = {
        "code": "server_error",
        "type": "server_error",
        "message": "do-not-persist-provider-text",
    }
    provider = await offline_provider(monkeypatch, lambda request: httpx.Response(200, json=payload))
    provider.enable_budget(1)
    try:
        with pytest.raises(ProviderUnavailable):
            await provider.plan({})
        receipt = provider.execution_receipts[0]
        assert receipt["status"] == "provider_error"
        assert receipt["provider_error_code"] == "server_error"
        assert receipt["provider_error_type"] == "server_error"
        assert receipt["charge_status"] == "unknown"
        assert "do-not-persist-provider-text" not in json.dumps(receipt)
    finally:
        await provider.client.close()


async def test_reported_token_total_is_retained_separately_from_derived_total(monkeypatch):
    payload = response_payload(
        usage={
            "input_tokens": 100,
            "output_tokens": 40,
            "total_tokens": 141,
            "input_tokens_details": {"cached_tokens": 20},
        }
    )
    provider = await offline_provider(monkeypatch, lambda request: httpx.Response(200, json=payload))
    provider.enable_budget(1)
    try:
        _, usage = await provider.plan({})
        assert usage["total_tokens"] == 140
        assert usage["reported_total_tokens"] == 141
        assert usage["input_tokens_details"]["cache_write_tokens"] is None
    finally:
        await provider.client.close()


@pytest.mark.parametrize("kind", ["refusal", "incomplete"])
async def test_unsuccessful_output_is_categorized_without_success_cost(monkeypatch, kind):
    payload = response_payload(status="incomplete" if kind == "incomplete" else "completed")
    if kind == "refusal":
        payload["output"][0]["content"] = [{"type": "refusal", "refusal": "offline refusal"}]
    else:
        payload["incomplete_details"] = {"reason": "max_output_tokens"}
    provider = await offline_provider(monkeypatch, lambda request: httpx.Response(200, json=payload))
    provider.enable_budget(1)
    try:
        with pytest.raises(ProviderUnavailable):
            await provider.plan({})
        receipt = provider.execution_receipts[0]
        assert receipt["status"] == kind
        assert receipt["usage"]["estimated_cost_usd"] is None
        assert receipt["usage"]["usage_status"] == "unknown"
        assert Decimal(receipt["reserved_cost_usd"]) > 0
    finally:
        await provider.client.close()


@pytest.mark.parametrize("failure", ["timeout", "cancelled", "http_error"])
async def test_interrupted_request_retains_unknown_charge_and_never_retries(monkeypatch, failure):
    requests = []

    def respond(request):
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("offline timeout", request=request)
        if failure == "cancelled":
            raise asyncio.CancelledError()
        return httpx.Response(
            503, headers={"x-request-id": "req_503"}, json={"error": {"message": "offline"}}
        )

    provider = await offline_provider(monkeypatch, respond)
    provider.enable_budget(1)
    try:
        expected_error = {
            "timeout": APITimeoutError,
            "cancelled": asyncio.CancelledError,
            "http_error": InternalServerError,
        }
        with pytest.raises(expected_error[failure]):
            await provider.plan({})
        receipt = provider.execution_receipts[0]
        assert receipt["status"] == failure
        assert receipt["request_started"] is True
        assert receipt["usage"]["estimated_cost_usd"] is None
        assert receipt["usage"]["total_tokens"] is None
        assert receipt["charge_status"] == "unknown"
        assert Decimal(receipt["reserved_cost_usd"]) > 0
        assert len(requests) == 1
    finally:
        await provider.client.close()


async def test_durable_reservation_failure_prevents_network_request(monkeypatch):
    requests = []
    provider = await offline_provider(monkeypatch, lambda request: requests.append(request))

    def cannot_persist(total):
        raise OSError("offline write failure")

    provider.enable_budget(1, reservation_callback=cannot_persist)
    try:
        with pytest.raises(OSError):
            await provider.plan({})
        assert requests == []
        receipt = provider.execution_receipts[0]
        assert receipt["request_started"] is False
        assert receipt["status"] == "reservation_error"
    finally:
        await provider.client.close()


async def test_reenabling_budget_cannot_refund_or_raise_an_existing_cap(monkeypatch):
    provider = await offline_provider(
        monkeypatch, lambda request: httpx.Response(200, json=response_payload())
    )
    provider.enable_budget(1, reserved_spend=Decimal("0.30"))
    try:
        await provider.plan({})
        used = provider._reserved_spend
        provider.enable_budget(1)
        assert provider._reserved_spend == used
        with pytest.raises(ProviderUnavailable):
            provider.enable_budget(2)
    finally:
        await provider.client.close()


async def test_infinite_spend_cap_is_rejected_before_any_request(monkeypatch):
    provider = await offline_provider(
        monkeypatch, lambda request: httpx.Response(200, json=response_payload())
    )
    try:
        with pytest.raises(ProviderUnavailable):
            provider.enable_budget(float("inf"))
        assert provider.execution_receipts == []
    finally:
        await provider.client.close()


def test_conflicting_openai_endpoint_is_rejected_before_creating_client(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "demo-offline-key")
    monkeypatch.setenv("OPENAI_MODEL", "requested-offline-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    with pytest.raises(ProviderUnavailable, match="endpoint"):
        OpenAIProvider()
