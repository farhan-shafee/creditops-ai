"""Request-local citation types; the public/historical Assessment stays unchanged."""

from typing import Annotated, Any, Literal, TypeAliasType

from pydantic import Field, WithJsonSchema, create_model

from .models import AlternativeHypothesis, Assessment, Evidence, EvidenceClaim, TriggerHypothesis


def assessment_type(evidence: list[dict[str, Any]]) -> type[Assessment]:
    """Constrain references to the exact already-sanitized assessment packet.

    Only top-level returned rows confer eligibility. Callers supply the bounded
    serialized packet, never a database lookup or IDs mentioned inside its rows.
    Fresh types avoid session/global-schema mutation; sorted sets are deterministic.
    """
    if len(evidence) > 100:
        raise ValueError("Assessment evidence exceeds the existing model packet limit")
    rows = [Evidence.model_validate(row) for row in evidence]
    kinds: dict[str, str] = {}
    for row in rows:
        if row.id in kinds and kinds[row.id] != row.kind:
            raise ValueError("Ambiguous evidence identifier kinds in assessment packet")
        kinds[row.id] = row.kind
    general = tuple(sorted(kinds))
    runbooks = tuple(identifier for identifier in general if kinds[identifier] == "runbook")
    history = tuple(identifier for identifier in general if kinds[identifier] in {"history", "historical_incident"})
    aliases: dict[tuple[str, ...], Any] = {}

    def references(identifiers: tuple[str, ...], name: str, description: str):
        if not identifiers:
            # Supported maxItems: 0, never an empty enum or a placeholder item.
            return Annotated[list[str], Field(max_length=0, description=description)]
        if identifiers not in aliases:
            item = Annotated[
                Literal[identifiers],
                WithJsonSchema({"type": "string", "enum": list(identifiers)}),
            ]
            aliases[identifiers] = TypeAliasType(name, item)
        return Annotated[list[aliases[identifiers]], Field(description=description)]

    ids = references(general, "ReturnedEvidenceID", "Actual top-level returned evidence IDs only; [] is allowed. Eligibility does not establish claim support.")
    runbook_ids = references(runbooks, "ReturnedRunbookID", "Returned runbook IDs only. With none retrieved use []; explain absence in limitations/unknowns, not here.")
    history_ids = references(history, "ReturnedHistoryID", "Returned history/historical_incident IDs only. With none retrieved use []; not retrieved does not mean nonexistent.")
    hypothesis = create_model("ReturnedAlternativeHypothesis", __base__=AlternativeHypothesis, evidence_ids=(ids, ...))
    claim = create_model("ReturnedEvidenceClaim", __base__=EvidenceClaim, evidence_ids=(ids, ...))
    trigger = create_model(
        "ReturnedTriggerHypothesis", __base__=TriggerHypothesis, evidence_ids=(ids, ...),
        status=(Annotated[Literal["candidate"], WithJsonSchema({"type": "string", "enum": ["candidate"]})], "candidate"),
    )
    return create_model(
        "Assessment",
        __base__=Assessment,
        supporting_evidence_ids=(ids, ...),
        relevant_runbooks=(runbook_ids, ...),
        similar_incidents=(history_ids, ...),
        alternative_hypotheses=(list[hypothesis], ...),
        observations=(list[claim], Field(default_factory=list)),
        possible_triggers=(list[trigger], Field(default_factory=list)),
        confirmed_cause=(claim | None, None),
        score_kind=(Annotated[Literal["uncalibrated_support"], WithJsonSchema({"type": "string", "enum": ["uncalibrated_support"]})], "uncalibrated_support"),
    )


def anthropic_assessment_schema(model: type[Assessment]) -> dict[str, Any]:
    """Documented raw-schema route: the SDK parser drops maxItems and const.

    Anthropic documents const, but not maxItems: 0. Use const: [] for those
    collections, retain local max_length=0 validation, and require every field.
    Numeric bounds stay local, as with the ordinary SDK transformation. Defaults
    are removed intentionally so all properties remain required on the wire.
    """
    schema = model.model_json_schema()  # Fresh dict; never change global types.

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object":
                node["required"] = list(node.get("properties", {}))
            if node.get("maxItems") == 0:
                node.pop("maxItems")
                node["const"] = []
            bounds = {key: node.pop(key) for key in ("minimum", "maximum") if key in node}
            if bounds:
                node["description"] = f"{node.get('description', '')} Numeric bounds checked locally: {bounds}.".strip()
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(schema)
    return schema
