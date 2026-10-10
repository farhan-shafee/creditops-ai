"""Official SDK request serialization with an offline HTTP transport only."""

import json
from datetime import datetime

import httpx
import pytest
from creditops.diagnostic_clients import DiagnosticClientError, DirectDiagnosticClient, safe_arguments
from creditops.providers import AdaptiveDecision, OpenAIProvider
from creditops.tool_contracts import MODEL_ARGUMENTS, MODEL_TOOLS, REQUEST_ADAPTER, DiagnosticRequest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as SchemaError
from pydantic import ValidationError

TIME_FORMAT_CHECKER = FormatChecker()


@TIME_FORMAT_CHECKER.checks("date-time", raises=ValueError)
def valid_datetime(value):
    # jsonschema's optional RFC3339 checker is not installed by the application.
    # Validate the declared format offline using the same timestamp calendar
    # primitive as the execution boundary, in addition to the schema pattern.
    return (
        not isinstance(value, str) or datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    )


BAD_METRIC_ACTION = {
    "action": "tool",
    "request": {
        "name": "query_metrics",
        "service": "quote-service",
        "q": "cpu utilization latency request duration saturation backlog around incident start",
    },
}


async def serialized_schema(monkeypatch, output, *, catalog=None, captured_sink=None):
    """Capture what installed official OpenAI SDK sends, never use a real transport."""
    from openai import AsyncOpenAI

    monkeypatch.setenv("OPENAI_API_KEY", "offline-contract-test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.4-mini-2026-03-17")
    monkeypatch.setenv("OPENAI_INPUT_USD_PER_MILLION", "0.75")
    monkeypatch.setenv("OPENAI_OUTPUT_USD_PER_MILLION", "4.50")
    captured = []

    def respond(request):
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "resp_offline_contract",
                "object": "response",
                "created_at": 1,
                "status": "completed",
                "model": "gpt-5.4-mini-2026-03-17",
                "output": [
                    {
                        "id": "msg_offline_contract",
                        "type": "message",
                        "status": "completed",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(output),
                                "annotations": [],
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140},
            },
        )

    provider = OpenAIProvider()
    await provider.client.close()
    provider.client = AsyncOpenAI(
        api_key="offline-contract-test-key",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    provider.enable_budget(1)
    parsed = None
    try:
        try:
            if catalog is None:
                parsed, _ = await provider._parse(AdaptiveDecision, "Offline schema contract", {})
            else:
                parsed, _ = await provider.next_action({}, catalog, [], [])
        except ValidationError:
            pass
        assert len(captured) == 1
        if captured_sink is not None:
            captured_sink.extend(captured)
        return captured[0]["text"]["format"]["schema"], parsed
    finally:
        await provider.client.close()


async def test_reported_cross_tool_argument_fails_actual_sdk_schema_and_runtime(monkeypatch):
    with pytest.raises(DiagnosticClientError):
        safe_arguments("query_metrics", {"service": "quote-service", "q": BAD_METRIC_ACTION["request"]["q"]})
    schema, parsed = await serialized_schema(monkeypatch, BAD_METRIC_ACTION)
    # Before repair this required red regression showed that the generic SDK
    # schema accepted the bad action while the executable guard rejected it.
    with pytest.raises(SchemaError):
        Draft202012Validator(schema).validate(BAD_METRIC_ACTION)
    assert parsed is None


def request_for(name):
    samples = {
        "service": "quote-service",
        "q": "timeout",
        "severity": "ERROR",
        "trace_id": "trace-1",
        "metric": "request_latency_ms",
        "start": "2026-10-09T14:00:00Z",
        "end": "2026-10-09T15:00:00+00:00",
    }
    return {"name": name, **{field: samples[field] for field in MODEL_ARGUMENTS[name].model_fields}}


@pytest.mark.parametrize("name", sorted(MODEL_TOOLS))
async def test_every_model_tool_actual_sdk_schema_local_types_and_guard(monkeypatch, name):
    request = request_for(name)
    action = {"action": "tool", "request": request}
    schema, parsed = await serialized_schema(monkeypatch, action)
    validator = Draft202012Validator(schema, format_checker=TIME_FORMAT_CHECKER)
    validator.validate(action)
    assert parsed.request.name == name
    arguments = {key: value for key, value in request.items() if key != "name"}
    assert safe_arguments(name, arguments) == arguments
    assert REQUEST_ADAPTER.validate_python(request).model_dump() == request

    # Fields present only on other tools, arbitrary fields and authority remain
    # closed both in the actual outgoing provider schema and runtime guard.
    cross_field = "q" if "q" not in arguments else "metric"
    for field, value in [
        (cross_field, "unexpected"),
        ("unknown", 1),
        ("session_id", "other"),
        ("incident_id", "INC-DEMO-002"),
        ("as_of", "2099-01-01T00:00:00Z"),
        ("snapshot", "2099-01-01T00:00:00Z"),
        ("limit", 50),
        ("offset", 0),
    ]:
        bad = {**request, field: value}
        with pytest.raises(SchemaError):
            validator.validate({"action": "tool", "request": bad})
        with pytest.raises(ValidationError):
            REQUEST_ADAPTER.validate_python(bad)
        with pytest.raises(DiagnosticClientError):
            safe_arguments(name, {key: value for key, value in bad.items() if key != "name"})

    # Local omitted/null defaults explicitly become no filter. SDK strict output
    # requires these supported nullable fields to be present with null instead.
    omitted = DiagnosticRequest(name=name)
    null_request = omitted.model_dump()
    validator.validate({"action": "tool", "request": null_request})
    assert safe_arguments(name, omitted.model_dump(exclude={"name"})) == {}

    for field in arguments:
        invalid = [True, 123, {}]
        if field in {"service", "metric", "trace_id"}:
            invalid += ["", "x" * 81, "two words", "../escape"]
        elif field == "q":
            invalid += ["x" * 241]
        elif field in {"start", "end"}:
            invalid += ["2026-10-09T15:00:00", "2026-02-30T15:00:00Z", "bad time"]
        elif field == "severity":
            invalid += ["error", "UNKNOWN"]
        for value in invalid:
            bad = {**request, field: value}
            with pytest.raises(SchemaError):
                validator.validate({"action": "tool", "request": bad})
            with pytest.raises(ValidationError):
                REQUEST_ADAPTER.validate_python(bad)
            with pytest.raises(DiagnosticClientError):
                safe_arguments(name, {key: value for key, value in bad.items() if key != "name"})


@pytest.mark.parametrize("q", [None, "free text"])
async def test_complete_metrics_object_forbids_q_even_when_null(monkeypatch, q):
    valid = {"action": "tool", "request": request_for("query_metrics")}
    schema, _ = await serialized_schema(monkeypatch, valid)
    bad = {"action": "tool", "request": {**valid["request"], "q": q}}
    with pytest.raises(SchemaError):
        Draft202012Validator(schema).validate(bad)
    with pytest.raises(ValidationError):
        AdaptiveDecision.model_validate(bad)
    with pytest.raises(DiagnosticClientError):
        safe_arguments(
            "query_metrics", {**{k: v for k, v in valid["request"].items() if k != "name"}, "q": q}
        )


def assert_supported_closed_schema(schema):
    """Inspect actual wire schemas against the documented provider subset."""
    assert schema["type"] == "object"
    assert "anyOf" not in schema

    def check(node):
        if isinstance(node, dict):
            assert not {"const", "oneOf", "allOf", "not", "if", "then", "else", "discriminator"} & node.keys()
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    check(schema)


async def test_actual_sdk_schema_uses_supported_closed_nested_union(monkeypatch):
    schema, _ = await serialized_schema(monkeypatch, {"action": "assess", "request": None})
    assert schema["type"] == "object"
    assert "anyOf" not in schema
    assert "anyOf" in schema["properties"]["request"]

    assert_supported_closed_schema(schema)
    # Cross-field semantic checks remain local; Python validators are not
    # represented as unsupported JSON Schema conditionals.
    for bad in [
        {"action": "tool", "request": None},
        {"action": "assess", "request": request_for("get_service_topology")},
    ]:
        with pytest.raises(ValidationError):
            AdaptiveDecision.model_validate(bad)


def test_app_owned_context_and_time_order_remain_guarded():
    assert safe_arguments("get_incident", {}) == {}
    for arguments in [{"incident_id": "INC-DEMO-002"}, {"limit": 1}, {"service": "quote-service"}]:
        with pytest.raises(DiagnosticClientError):
            safe_arguments("get_incident", arguments)
    bad = {"name": "query_metrics", "start": "2026-10-09T15:01:00Z", "end": "2026-10-09T15:00:00Z"}
    with pytest.raises(ValidationError):
        REQUEST_ADAPTER.validate_python(bad)
    with pytest.raises(DiagnosticClientError):
        safe_arguments("query_metrics", {key: value for key, value in bad.items() if key != "name"})


async def test_actual_provider_request_includes_owned_catalog_and_no_match_semantics(monkeypatch):
    catalog = DirectDiagnosticClient(
        None, "00000000-0000-0000-0000-000000000001", "INC-SYNTHETIC", "2026-10-09T15:00:00Z"
    ).schemas
    captured = []
    await serialized_schema(
        monkeypatch, {"action": "assess", "request": None}, catalog=catalog, captured_sink=captured
    )
    payload = json.loads(captured[0]["input"][1]["content"].split("\n", 1)[1])
    visible = {item["name"]: item for item in payload["available_tools"]}
    assert set(visible) == MODEL_TOOLS
    logs = visible["search_logs"]["description"]
    for expected in [
        "literal substring",
        "summary",
        "serialized data",
        "no Boolean OR/AND",
        "not healthy telemetry",
    ]:
        assert expected in logs
    metrics = visible["query_metrics"]
    assert "exact identifiers" in metrics["description"]
    assert "metric" in metrics["input_schema"]["properties"]
    assert not {"q", "aggregation"} & metrics["input_schema"]["properties"].keys()
    assert "No matches and tool failures are unknown" in captured[0]["input"][0]["content"]


async def test_topology_omitted_catalog_rejects_topology_in_actual_sdk_schema_and_parsing(monkeypatch):
    # The first successful frozen-snapshot topology result is retained by the
    # investigator. Its next catalog deliberately removes the redundant action.
    catalog = [
        item
        for item in DirectDiagnosticClient(
            None, "00000000-0000-0000-0000-000000000001", "INC-SYNTHETIC", "2026-10-09T15:00:00Z"
        ).schemas
        if item["name"] != "get_service_topology"
    ]
    repeated = {"action": "tool", "request": {"name": "get_service_topology"}}
    captured = []
    schema, parsed = await serialized_schema(
        monkeypatch, repeated, catalog=catalog, captured_sink=captured
    )
    assert_supported_closed_schema(schema)
    validator = Draft202012Validator(schema, format_checker=TIME_FORMAT_CHECKER)
    with pytest.raises(SchemaError):
        validator.validate(repeated)
    assert parsed is None
    assert "get_service_topology" not in json.dumps(schema)
    payload = json.loads(captured[0]["input"][1]["content"].split("\n", 1)[1])
    visible = {item["name"] for item in payload["available_tools"]}
    assert visible == {
        "search_logs", "query_metrics", "get_recent_deployments", "find_similar_incidents",
        "search_runbooks", "inspect_kafka_lag", "inspect_fix_session", "inspect_database_health",
    }
    for name in sorted(visible):
        validator.validate({"action": "tool", "request": request_for(name)})
    # Distinct narrow/broader filter requests remain representable: availability
    # is tool-specific, not an irreversible once-per-tool ban.
    for query in ["timeout", ""]:
        request = {**request_for("search_logs"), "q": query}
        validator.validate({"action": "tool", "request": request})
    for service in ["quote-service", "pricing-service", None]:
        request = {**request_for("query_metrics"), "service": service}
        validator.validate({"action": "tool", "request": request})


async def test_initial_catalog_retains_topology_in_actual_sdk_schema(monkeypatch):
    catalog = DirectDiagnosticClient(
        None, "00000000-0000-0000-0000-000000000001", "INC-SYNTHETIC", "2026-10-09T15:00:00Z"
    ).schemas
    action = {"action": "tool", "request": {"name": "get_service_topology"}}
    schema, parsed = await serialized_schema(monkeypatch, action, catalog=catalog)
    assert_supported_closed_schema(schema)
    Draft202012Validator(schema).validate(action)
    assert parsed.request.name == "get_service_topology"


async def test_empty_catalog_is_assessment_only_in_actual_sdk_schema(monkeypatch):
    schema, parsed = await serialized_schema(
        monkeypatch, {"action": "assess", "request": None}, catalog=[]
    )
    assert parsed.action == "assess"
    assert_supported_closed_schema(schema)
    validator = Draft202012Validator(schema)
    validator.validate({"action": "assess", "request": None})
    with pytest.raises(SchemaError):
        validator.validate({"action": "tool", "request": request_for("query_metrics")})
    with pytest.raises(SchemaError):
        validator.validate({"action": "tool", "request": None})


@pytest.mark.parametrize("output", [
    {"action": "tool", "request": None},
    {"action": "assess", "request": {"name": "inspect_database_health", "service": None}},
])
async def test_restricted_actual_sdk_schema_preserves_local_action_coherence(monkeypatch, output):
    schema, parsed = await serialized_schema(
        monkeypatch, output, catalog=[{"name": "inspect_database_health"}]
    )
    assert_supported_closed_schema(schema)
    assert parsed is None
