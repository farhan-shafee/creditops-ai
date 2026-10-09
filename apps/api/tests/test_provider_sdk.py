"""Exercise installed official SDK serialization/parsing with an offline HTTP transport."""

import json

import httpx
from creditops.providers import AnthropicProvider, DiagnosticPlan, OpenAIProvider, usage_record

PLAN = {"requests": [{"name": "query_metrics", "service": None, "q": None}]}


async def test_openai_responses_structured_output_and_server_configuration(monkeypatch):
    from openai import AsyncOpenAI

    monkeypatch.setenv("OPENAI_API_KEY", "demo-offline-key")
    monkeypatch.setenv("OPENAI_MODEL", "demo-configured-model")
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
