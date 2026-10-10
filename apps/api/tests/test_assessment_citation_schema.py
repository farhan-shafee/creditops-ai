"""Assessment citation contracts serialized by official SDKs, using offline HTTP only."""

import copy
import json

import httpx
import pytest
from creditops.models import Assessment
from creditops.providers import ASSESSMENT_INSTRUCTION, AnthropicProvider, OpenAIProvider, ProviderUnavailable
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaError
from pydantic import ValidationError

MISSING_RUNBOOK = "No returned runbook IDs available in the provided evidence."
MISSING_HISTORY = "No returned historical incident IDs available in the provided evidence."


def proposal():
    """A complete public shape, independent of the evidence-conditioned builder."""
    return Assessment(
        incident_summary="Returned observations require review.",
        probable_failure_domain="insufficient evidence",
        confidence=0.2,
        supporting_evidence_ids=[],
        alternative_hypotheses=[],
        recommended_next_steps=["Review the returned observations."],
        relevant_runbooks=[],
        similar_incidents=[],
        requires_human_review=True,
        limitations=["Runbook and history evidence was not retrieved."],
        rca={
            "executive_summary": "Human review required.",
            "impact": "Business impact is unverified.",
            "timeline": [],
            "observed_evidence": [],
            "probable_root_cause": "Unresolved.",
            "contributing_factors": [],
            "immediate_next_steps": [],
            "follow_up_work": [],
        },
    ).model_dump(mode="json")


def evidence(identifier="LOG-RETURNED", kind="log", **data):
    return {
        "id": identifier,
        "kind": kind,
        "service": "synthetic-service",
        "timestamp": "2026-10-09T14:00:00Z",
        "summary": "Synthetic returned observation.",
        "data": data,
    }


async def serialized_assessment(
    monkeypatch, kind, output, rows, *, legacy_static=False, envelope_patch=None, expected_exception=ValidationError
):
    """Capture the request after installed SDK serialization; transport cannot infer."""
    upper = kind.upper()
    for name, value in {
        f"{upper}_API_KEY": "offline-citation-test-key",
        f"{upper}_MODEL": "explicit-offline-model",
        f"{upper}_INPUT_USD_PER_MILLION": "0.75",
        f"{upper}_OUTPUT_USD_PER_MILLION": "4.50",
    }.items():
        monkeypatch.setenv(name, value)
    captured = []
    if kind == "openai":
        from openai import AsyncOpenAI

        def respond(request):
            captured.append(json.loads(request.content))
            payload = {
                "id": "resp_offline_citation",
                "object": "response",
                "created_at": 1,
                "status": "completed",
                "model": "returned-offline-model",
                "output": [
                    {
                        "id": "msg_offline_citation",
                        "type": "message",
                        "status": "completed",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": json.dumps(output), "annotations": []}],
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140},
            }
            payload.update(copy.deepcopy(envelope_patch or {}))
            return httpx.Response(
                200,
                headers={"x-request-id": "req_offline_citation"},
                json=payload,
            )

        provider = OpenAIProvider()
        await provider.client.close()
        provider.client = AsyncOpenAI(
            api_key="offline-citation-test-key",
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        )
    else:
        import httpx2
        from anthropic import AsyncAnthropic

        def respond(request):
            captured.append(json.loads(request.content))
            payload = {
                "id": "msg_offline_citation", "type": "message", "role": "assistant",
                "model": "returned-offline-model",
                "content": [{"type": "text", "text": json.dumps(output)}],
                "stop_reason": "end_turn", "stop_sequence": None,
                "usage": {"input_tokens": 100, "output_tokens": 40},
            }
            payload.update(copy.deepcopy(envelope_patch or {}))
            return httpx2.Response(
                200,
                headers={"request-id": "req_offline_citation"},
                json=payload,
            )

        provider = AnthropicProvider()
        await provider.client.close()
        provider.client = AsyncAnthropic(
            api_key="offline-citation-test-key",
            max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )
    provider.enable_budget(2)
    parsed, error = None, None
    try:
        try:
            if legacy_static:
                parsed, _ = await provider._parse(
                    Assessment, ASSESSMENT_INSTRUCTION, {"incident": {}, "evidence": rows}
                )
            else:
                parsed, _ = await provider.assess({}, rows)
        except expected_exception as caught:
            error = caught
        assert len(captured) == 1
        schema = (
            captured[0]["text"]["format"]["schema"]
            if kind == "openai"
            else captured[0]["output_config"]["format"]["schema"]
        )
        return schema, parsed, error, copy.deepcopy(provider.execution_receipts), captured[0]
    finally:
        await provider.client.close()


@pytest.mark.parametrize("kind", ["openai", "anthropic"])
async def test_exact_historical_absence_prose_fails_actual_assessment_sdk_schema(monkeypatch, kind):
    output = {**proposal(), "relevant_runbooks": [MISSING_RUNBOOK], "similar_incidents": [MISSING_HISTORY]}
    rows = [evidence()]
    old_schema, old_parsed, _, _, _ = await serialized_assessment(
        monkeypatch, kind, output, rows, legacy_static=True
    )
    # Historical public serialization remains readable and the original static
    # SDK contract demonstrates the mismatch; no historical receipt is edited.
    Draft202012Validator(old_schema).validate(output)
    assert old_parsed.relevant_runbooks == [MISSING_RUNBOOK]
    assert old_parsed.similar_incidents == [MISSING_HISTORY]

    schema, parsed, error, _, _ = await serialized_assessment(monkeypatch, kind, output, rows)
    with pytest.raises(SchemaError):
        Draft202012Validator(schema).validate(output)
    assert parsed is None
    assert isinstance(error, ValidationError)


def with_reference(output, field, identifiers):
    output = copy.deepcopy(output)
    if field in {"supporting_evidence_ids", "relevant_runbooks", "similar_incidents"}:
        output[field] = identifiers
    elif field == "alternative_hypotheses":
        output[field] = [{"domain": "Unknown", "reason": "Unresolved.", "evidence_ids": identifiers}]
    elif field == "possible_triggers":
        output[field] = [
            {
                "statement": "Candidate requires review.",
                "evidence_ids": identifiers,
                "status": "candidate",
                "reason": "Initiating cause is not established.",
            }
        ]
    elif field == "observations":
        output[field] = [{"statement": "Recorded observation.", "evidence_ids": identifiers}]
    elif field == "confirmed_cause":
        output[field] = {"statement": "Offline structural fixture only.", "evidence_ids": identifiers}
    else:
        raise AssertionError(f"Unknown test reference field: {field}")
    return output


REFERENCE_FIELDS = (
    "supporting_evidence_ids",
    "relevant_runbooks",
    "similar_incidents",
    "alternative_hypotheses",
    "observations",
    "possible_triggers",
    "confirmed_cause",
)


@pytest.mark.parametrize("kind", ["openai", "anthropic"])
async def test_absent_reference_kinds_allow_only_empty_arrays_on_the_sdk_wire(monkeypatch, kind):
    output = proposal()
    schema, parsed, error, _, _ = await serialized_assessment(monkeypatch, kind, output, [evidence()])
    validator = Draft202012Validator(schema)
    validator.validate(output)
    assert parsed is not None and error is None
    for field in ("relevant_runbooks", "similar_incidents"):
        for bad in [MISSING_RUNBOOK, MISSING_HISTORY, "none", "N/A", "LOG-RETURNED", None, 123, {}]:
            with pytest.raises(SchemaError):
                validator.validate({**output, field: [bad]})
        with pytest.raises(SchemaError):
            validator.validate({**output, field: None})

    # With no top-level evidence, all seven collections are empty-only, including
    # citations inside optional nested objects. No invalid empty enum is emitted.
    empty_schema, parsed, error, _, _ = await serialized_assessment(monkeypatch, kind, output, [])
    empty_validator = Draft202012Validator(empty_schema)
    assert parsed is not None and error is None
    for field in REFERENCE_FIELDS:
        empty_validator.validate(with_reference(output, field, []))
        with pytest.raises(SchemaError):
            empty_validator.validate(with_reference(output, field, ["LOG-RETURNED"]))
    for node in schema_nodes(empty_schema):
        if "enum" in node:
            assert node["enum"]
    if kind == "openai":
        assert any(node.get("maxItems") == 0 for node in schema_nodes(empty_schema))
    else:
        # Installed Anthropic SDK strips maxItems; its documented const support
        # expresses the same empty-only array in the actual public create body.
        assert any(
            node.get("type") == "array" and node.get("const") == [] for node in schema_nodes(empty_schema)
        )


@pytest.mark.parametrize("kind", ["openai", "anthropic"])
async def test_only_top_level_returned_ids_and_correct_reference_kinds_are_eligible(monkeypatch, kind):
    from creditops.assessment_schema import assessment_type

    rows = [
        evidence("LOG-RETURNED", mentioned="RUNBOOK-NESTED", timeline=[{"evidence_ids": ["LOG-NESTED"]}]),
        evidence("RUNBOOK-RETURNED", "runbook"),
        evidence("INC-HIST-RETURNED", "history"),
        evidence("INC-HIST-OTHER", "historical_incident"),
    ]
    output = proposal()
    schema, parsed, error, _, _ = await serialized_assessment(monkeypatch, kind, output, rows)
    assert parsed is not None and error is None
    validator = Draft202012Validator(schema)
    local_type = assessment_type(rows)
    eligible = {
        "relevant_runbooks": ["RUNBOOK-RETURNED"],
        "similar_incidents": ["INC-HIST-RETURNED", "INC-HIST-OTHER"],
    }
    all_returned = ["LOG-RETURNED", "RUNBOOK-RETURNED", "INC-HIST-RETURNED", "INC-HIST-OTHER"]
    for field in REFERENCE_FIELDS:
        for identifier in eligible.get(field, all_returned):
            valid = with_reference(output, field, [identifier])
            validator.validate(valid)
            assert isinstance(local_type.model_validate(valid), Assessment)
        validator.validate(with_reference(output, field, []))
        for identifier in ["LOG-UNRETURNED", "RUNBOOK-NESTED", "LOG-NESTED", "An explanatory sentence"]:
            invalid = with_reference(output, field, [identifier])
            with pytest.raises(SchemaError):
                validator.validate(invalid)
            with pytest.raises(ValidationError):
                local_type.model_validate(invalid)
    for field, wrong in [
        ("relevant_runbooks", "LOG-RETURNED"),
        ("relevant_runbooks", "INC-HIST-RETURNED"),
        ("similar_incidents", "LOG-RETURNED"),
        ("similar_incidents", "RUNBOOK-RETURNED"),
    ]:
        invalid = with_reference(output, field, [wrong])
        with pytest.raises(SchemaError):
            validator.validate(invalid)
        with pytest.raises(ValidationError):
            local_type.model_validate(invalid)


def schema_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from schema_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from schema_nodes(child)


def assert_supported_schema_bounds(schema, *, kind="openai"):
    """Check the actual serialized schema against documented standard-model limits."""
    assert schema["type"] == "object" and "anyOf" not in schema
    property_count = enum_count = string_length = 0
    for node in schema_nodes(schema):
        assert not {"oneOf", "allOf", "not", "if", "then", "else", "discriminator"} & node.keys()
        if "const" in node:
            assert kind == "anthropic" and node.get("type") == "array" and node["const"] == []
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
        property_count += len(node.get("properties", {}))
        string_length += sum(len(key) for key in node.get("properties", {}))
        string_length += sum(len(key) for key in node.get("$defs", {}))
        choices = node.get("enum", [])
        enum_count += len(choices)
        string_length += sum(len(value) for value in choices if isinstance(value, str))
        assert choices or "enum" not in node
        if len(choices) > 250:
            assert sum(len(value) for value in choices if isinstance(value, str)) <= 15_000
    assert property_count <= 5_000
    assert enum_count <= 1_000
    assert string_length <= 120_000

    def depth(node, object_depth=0):
        if isinstance(node, dict):
            if "$ref" in node:
                referenced = schema
                for key in node["$ref"].removeprefix("#/").split("/"):
                    referenced = referenced[key]
                return depth(referenced, object_depth)
            object_depth += node.get("type") == "object"
            assert object_depth <= 10
            for key, child in node.items():
                if key != "$defs":
                    depth(child, object_depth)
        elif isinstance(node, list):
            for child in node:
                depth(child, object_depth)

    depth(schema)


@pytest.mark.parametrize("kind", ["openai", "anthropic"])
@pytest.mark.parametrize("packet_size", [0, 4, 100])
async def test_actual_sdk_assessment_schema_is_closed_and_bounded_at_supported_packet_sizes(
    monkeypatch, kind, packet_size
):
    rows = [
        evidence(
            f"RETURNED-{index:03d}-" + "x" * 83,
            ("log", "runbook", "history", "historical_incident")[index % 4],
        )
        for index in range(packet_size)
    ]
    assert all(len(item["id"]) == 96 for item in rows)
    schema, parsed, error, _, _ = await serialized_assessment(monkeypatch, kind, proposal(), rows)
    assert parsed is not None and error is None
    Draft202012Validator.check_schema(schema)
    assert_supported_schema_bounds(schema, kind=kind)
    for node in schema_nodes(schema):
        if "enum" in node and all(isinstance(value, str) for value in node["enum"]):
            # Shared citation definitions keep maximum packets below aggregate
            # enum limits, rather than copying the full enum for every field.
            assert len(node["enum"]) <= 100


async def test_maximum_unicode_ids_remain_supported_and_preserve_actual_wire_reservation(monkeypatch):
    # Evidence bounds count characters, while reservation accounting measures
    # escaped JSON bytes. Neither a smaller ASCII-only bound nor hidden enum
    # truncation is a correct substitute for the supported packet maximum.
    rows = [evidence(f"RETURNED-{index:03d}-" + "界" * 83) for index in range(100)]
    schema, parsed, error, receipts, _ = await serialized_assessment(monkeypatch, "openai", proposal(), rows)
    assert parsed is not None and error is None
    assert_supported_schema_bounds(schema)
    validator = Draft202012Validator(schema)
    for identifier in [rows[0]["id"], rows[-1]["id"]]:
        validator.validate(with_reference(proposal(), "supporting_evidence_ids", [identifier]))
    assert isinstance(receipts[0]["input_tokens_ceiling"], int)
    assert receipts[0]["input_tokens_ceiling"] > len(json.dumps(schema).encode("utf-8"))


@pytest.mark.parametrize("kind", ["openai", "anthropic"])
async def test_sdk_schema_is_deterministic_and_does_not_leak_between_investigations(monkeypatch, kind):
    from creditops.assessment_schema import assessment_type

    public_before = copy.deepcopy(Assessment.model_json_schema())
    a = [evidence("LOG-SESSION-A"), evidence("RUNBOOK-SESSION-A", "runbook")]
    b = [evidence("LOG-SESSION-B"), evidence("INC-HIST-SESSION-B", "history")]
    a_before = copy.deepcopy(a)
    schema_a, _, _, _, _ = await serialized_assessment(monkeypatch, kind, proposal(), a)
    saved_a = copy.deepcopy(schema_a)
    schema_b, _, _, _, _ = await serialized_assessment(monkeypatch, kind, proposal(), b)
    schema_reordered, _, _, _, _ = await serialized_assessment(
        monkeypatch, kind, proposal(), list(reversed(a))
    )
    schema_duplicates, _, _, _, _ = await serialized_assessment(monkeypatch, kind, proposal(), [*a, a[0]])
    assert schema_a == saved_a == schema_reordered == schema_duplicates
    assert a == a_before
    assert Assessment.model_json_schema() == public_before
    for schema, own, other in [
        (schema_a, "LOG-SESSION-A", "LOG-SESSION-B"),
        (schema_b, "LOG-SESSION-B", "LOG-SESSION-A"),
    ]:
        validator = Draft202012Validator(schema)
        validator.validate(with_reference(proposal(), "supporting_evidence_ids", [own]))
        with pytest.raises(SchemaError):
            validator.validate(with_reference(proposal(), "supporting_evidence_ids", [other]))
    with pytest.raises(ValidationError):
        assessment_type(a).model_validate(
            with_reference(proposal(), "supporting_evidence_ids", ["LOG-SESSION-B"])
        )


@pytest.mark.parametrize("kind", ["openai", "anthropic"])
async def test_invalid_offline_citation_preserves_parse_failure_metadata_and_reservation(monkeypatch, kind):
    output = {**proposal(), "relevant_runbooks": [MISSING_RUNBOOK]}
    original = copy.deepcopy(output)
    _, parsed, error, receipts, _ = await serialized_assessment(monkeypatch, kind, output, [evidence()])
    assert parsed is None and isinstance(error, ValidationError)
    assert output == original
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["status"] == "parse_error"
    assert receipt["rejection_stage"] == "assessment_structured_output"
    assert receipt["structured_output"] is None
    assert receipt["rejected_assessment_proposal"] == output
    assert receipt["request_started"] is True
    assert receipt["response_id"] in {"resp_offline_citation", "msg_offline_citation"}
    assert receipt["request_id"] == "req_offline_citation"
    assert receipt["requested_model"] == "explicit-offline-model"
    assert receipt["returned_model"] == "returned-offline-model"
    assert receipt["usage"]["total_tokens"] == 140
    assert receipt["usage"]["estimated_cost_usd"] is not None
    assert float(receipt["reserved_cost_usd"]) > receipt["usage"]["estimated_cost_usd"]


@pytest.mark.parametrize("kind", ["openai", "anthropic"])
async def test_malformed_public_assessment_does_not_become_a_repaired_proposal(monkeypatch, kind):
    output = {
        **proposal(),
        "observations": [{"statement": "Malformed fixture", "evidence_ids": "LOG-RETURNED"}],
    }
    _, parsed, error, receipts, _ = await serialized_assessment(monkeypatch, kind, output, [evidence()])
    assert parsed is None and isinstance(error, ValidationError)
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["status"] == "parse_error"
    assert receipt["rejection_stage"] == "assessment_structured_output"
    assert receipt["structured_output"] is None
    assert receipt.get("rejected_assessment_proposal") is None
    assert receipt["request_id"] == "req_offline_citation"
    assert receipt["usage"]["total_tokens"] == 140


@pytest.mark.parametrize("payload", [
    {"output": None}, {"output": "not a list"}, {"output": [None]},
    {"output": [{"content": None}]}, {"output": [{"content": "not a list"}]},
    {"output": [{"content": [None]}]}, {"content": None}, {"content": "not a list"},
    {"content": [None]}, {},
])
def test_malformed_envelope_cannot_interrupt_recording_assessment_schema_rejection(payload):
    from creditops.providers import _record_assessment_schema_rejection

    with pytest.raises(ValidationError) as caught:
        Assessment.model_validate({})
    receipt = {}
    _record_assessment_schema_rejection(receipt, payload, caught.value)
    assert receipt["rejection_stage"] == "assessment_structured_output"
    assert receipt["rejected_fields"]
    assert receipt.get("rejected_assessment_proposal") is None


@pytest.mark.parametrize("kind", ["openai", "anthropic"])
@pytest.mark.parametrize("bad_list", [None, "not a list", [None]])
async def test_actual_sdk_malformed_envelope_retains_finished_partial_receipt(monkeypatch, kind, bad_list):
    field = "output" if kind == "openai" else "content"
    schema, parsed, error, receipts, _ = await serialized_assessment(
        monkeypatch, kind, proposal(), [evidence()],
        envelope_patch={field: bad_list},
        expected_exception=(ValidationError, TypeError, AttributeError, ProviderUnavailable),
    )
    assert schema["type"] == "object"
    assert parsed is None and error is not None
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["status"] in {"parse_error", "incomplete"}
    assert receipt["request_started"] is True and receipt["response_received"] is True
    assert receipt["started_at"] <= receipt["ended_at"]
    assert isinstance(receipt["duration_ms"], (int, float)) and receipt["duration_ms"] >= 0
    assert receipt["request_id"] == "req_offline_citation"
    assert receipt["response_id"] in {"resp_offline_citation", "msg_offline_citation"}
    assert receipt["returned_model"] == "returned-offline-model"
    assert receipt["usage"]["total_tokens"] == 140
    assert float(receipt["reserved_cost_usd"]) > receipt["usage"]["estimated_cost_usd"]
    assert receipt["structured_output"] is None
    assert receipt.get("rejected_assessment_proposal") is None


@pytest.mark.parametrize("kind", ["openai", "anthropic"])
async def test_schema_citation_eligibility_matches_exact_sanitized_packet(monkeypatch, kind):
    # Secret-bearing strings are sanitized before both the message and the
    # evidence-conditioned schema; the unsanitized source never becomes an enum.
    raw_identifier = "Bearer synthetic-secret-value"
    rows = [evidence(raw_identifier)]
    before = copy.deepcopy(rows)
    schema, _, _, _, request = await serialized_assessment(monkeypatch, kind, proposal(), rows)
    message = request["input"][1]["content"] if kind == "openai" else request["messages"][0]["content"]
    packet = json.loads(message.split("\n", 1)[1])
    returned = packet["evidence"][0]["id"]
    assert returned != raw_identifier
    validator = Draft202012Validator(schema)
    validator.validate(with_reference(proposal(), "supporting_evidence_ids", [returned]))
    with pytest.raises(SchemaError):
        validator.validate(with_reference(proposal(), "supporting_evidence_ids", [raw_identifier]))
    assert "synthetic-secret-value" not in json.dumps(request)
    assert rows == before


def test_reference_eligibility_does_not_guarantee_narrative_truth():
    from creditops.assessment_schema import assessment_type
    from creditops.validation import validate_assessment_with_outcome

    rows = [evidence("LOG-RETURNED")]
    output = with_reference(proposal(), "supporting_evidence_ids", ["LOG-RETURNED"])
    output["incident_summary"] = "All unqueried systems stayed healthy and executed orders made a profit."
    parsed = assessment_type(rows).model_validate(output)
    # The schema constrains identifiers, not free-text factuality. The existing
    # domain gate still observes the original proposal and may normalize prose.
    assert parsed.incident_summary == output["incident_summary"]
    final, original, outcome = validate_assessment_with_outcome(parsed, rows)
    assert original["incident_summary"] == output["incident_summary"]
    assert final.incident_summary != original["incident_summary"]
    assert outcome["original_claims_independently_verified"] is False
    assert outcome["changed_fields"]
