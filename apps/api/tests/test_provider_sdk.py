"""Exercise installed official SDK serialization/parsing with an offline HTTP transport."""

import json

import httpx
import pytest
from creditops.providers import AnthropicProvider, DiagnosticPlan, OpenAIProvider, usage_record
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaError

PLAN = {"requests": [{"name": "query_metrics", "service": None, "metric": None, "start": None, "end": None}]}


async def test_openai_responses_structured_output_and_server_configuration(monkeypatch):
    from openai import AsyncOpenAI

    monkeypatch.setenv("OPENAI_API_KEY", "demo-offline-key")
    monkeypatch.setenv("OPENAI_MODEL", "demo-configured-model")
    monkeypatch.setenv("OPENAI_INPUT_USD_PER_MILLION", "1")
    monkeypatch.setenv("OPENAI_OUTPUT_USD_PER_MILLION", "1")
    captured = []

    def respond(request):
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "resp_demo",
                "object": "response",
                "created_at": 1,
                "status": "completed",
                "model": "demo-configured-model",
                "output": [
                    {
                        "id": "msg_demo",
                        "type": "message",
                        "status": "completed",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": json.dumps(PLAN), "annotations": []}],
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140},
            },
        )

    provider = OpenAIProvider()
    provider.enable_budget(1)
    await provider.client.close()
    provider.client = AsyncOpenAI(
        api_key="demo-offline-key",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    try:
        parsed, usage = await provider._parse(
            DiagnosticPlan, "Read-only query plan", {"log": "Bearer hidden-demo-value"}
        )
        assert parsed.requests[0].name == "query_metrics"
        assert usage["total_tokens"] == 140
        assert captured[0]["model"] == "demo-configured-model"
        assert captured[0]["store"] is False
        assert captured[0]["text"]["format"]["type"] == "json_schema"
        assert "hidden-demo-value" not in json.dumps(captured)
    finally:
        await provider.client.close()


async def test_anthropic_messages_structured_output_with_current_sdk(monkeypatch):
    import httpx2
    from anthropic import AsyncAnthropic

    monkeypatch.setenv("ANTHROPIC_API_KEY", "demo-offline-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "demo-configured-model")
    monkeypatch.setenv("ANTHROPIC_INPUT_USD_PER_MILLION", "1")
    monkeypatch.setenv("ANTHROPIC_OUTPUT_USD_PER_MILLION", "1")
    captured = []

    def respond(request):
        captured.append(json.loads(request.content))
        return httpx2.Response(
            200,
            json={
                "id": "msg_demo",
                "type": "message",
                "role": "assistant",
                "model": "demo-configured-model",
                "content": [{"type": "text", "text": json.dumps(PLAN)}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 100, "output_tokens": 40},
            },
        )

    provider = AnthropicProvider()
    provider.enable_budget(1)
    await provider.client.close()
    provider.client = AsyncAnthropic(
        api_key="demo-offline-key",
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
    )
    try:
        parsed, usage = await provider._parse(
            DiagnosticPlan, "Read-only query plan", {"log": "password=hidden-demo-value"}
        )
        assert parsed.requests[0].name == "query_metrics"
        assert usage["total_tokens"] == 140
        assert captured[0]["model"] == "demo-configured-model"
        assert captured[0]["output_config"]["format"]["type"] == "json_schema"
        assert "hidden-demo-value" not in json.dumps(captured)
    finally:
        await provider.client.close()


def test_cost_is_only_estimated_when_explicit_prices_exist(monkeypatch):
    monkeypatch.delenv("OPENAI_INPUT_USD_PER_MILLION", raising=False)
    monkeypatch.delenv("OPENAI_OUTPUT_USD_PER_MILLION", raising=False)
    assert usage_record("openai", 100, 40)["estimated_cost_usd"] is None
    monkeypatch.setenv("OPENAI_INPUT_USD_PER_MILLION", "1")
    monkeypatch.setenv("OPENAI_OUTPUT_USD_PER_MILLION", "2")
    assert usage_record("openai", 100, 40)["estimated_cost_usd"] == 0.00018


@pytest.mark.parametrize("kind", ["openai", "anthropic"])
async def test_offline_adaptive_sdk_receives_actual_prior_result(kind, monkeypatch):
    from creditops.providers import AdaptiveDecision

    captured = []
    action = {"action": "tool", "request": {"name": "inspect_database_health", "service": None}}
    for key, value in {
        f"{kind.upper()}_API_KEY": "demo-offline-key",
        f"{kind.upper()}_MODEL": "explicit-offline-model",
        f"{kind.upper()}_INPUT_USD_PER_MILLION": "1",
        f"{kind.upper()}_OUTPUT_USD_PER_MILLION": "1",
    }.items():
        monkeypatch.setenv(key, value)
    if kind == "openai":
        from openai import AsyncOpenAI

        def respond(request):
            captured.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "id": "resp_offline",
                    "object": "response",
                    "created_at": 1,
                    "status": "completed",
                    "model": "explicit-offline-model",
                    "output": [
                        {
                            "id": "msg_offline",
                            "type": "message",
                            "status": "completed",
                            "role": "assistant",
                            "content": [
                                {"type": "output_text", "text": json.dumps(action), "annotations": []}
                            ],
                        }
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140},
                },
            )

        provider = OpenAIProvider()
        await provider.client.close()
        provider.client = AsyncOpenAI(
            api_key="demo-offline-key",
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        )
    else:
        import httpx2
        from anthropic import AsyncAnthropic

        def respond(request):
            captured.append(json.loads(request.content))
            return httpx2.Response(
                200,
                json={
                    "id": "msg_offline",
                    "type": "message",
                    "role": "assistant",
                    "model": "explicit-offline-model",
                    "content": [{"type": "text", "text": json.dumps(action)}],
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {"input_tokens": 100, "output_tokens": 40},
                },
            )

        provider = AnthropicProvider()
        await provider.client.close()
        provider.client = AsyncAnthropic(
            api_key="demo-offline-key",
            max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )
    provider.enable_budget(1)
    try:
        decision, usage = await provider.next_action(
            {"summary": "latency"},
            [{"name": "inspect_database_health"}],
            [{"tool": "query_metrics", "status": "complete", "evidence_ids": ["METRIC-POOL"]}],
            [{"id": "METRIC-POOL", "data": {"pool_utilization": 99}}],
        )
        assert isinstance(decision, AdaptiveDecision)
        assert decision.request.name == "inspect_database_health"
        assert usage["total_tokens"] == 140
        assert "METRIC-POOL" in json.dumps(captured)
        assert "pool_utilization" in json.dumps(captured)
        # Both official SDKs receive the narrowed request schema, not merely an
        # altered textual catalog; prior metric evidence stays in their context.
        schema = (
            captured[0]["text"]["format"]["schema"]
            if kind == "openai"
            else captured[0]["output_config"]["format"]["schema"]
        )
        validator = Draft202012Validator(schema)
        validator.validate(action)
        with pytest.raises(SchemaError):
            validator.validate({"action": "tool", "request": {"name": "get_service_topology"}})
        assert "get_service_topology" not in json.dumps(schema)
        provider.enable_budget(0.000001)
        with pytest.raises(RuntimeError, match="before request"):
            await provider.next_action({}, [], [], [])
        assert len(captured) == 1
    finally:
        await provider.client.close()
