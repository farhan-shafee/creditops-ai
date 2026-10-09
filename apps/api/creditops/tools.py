"""Read-only diagnostic allowlist shared by HTTP, MCP and the investigator."""

from datetime import UTC, datetime

from pydantic import ValidationError

from .models import Evidence, ToolArguments
from .store import Store

ALLOWED_TOOLS = frozenset(
    {
        "get_incident",
        "search_logs",
        "query_metrics",
        "get_service_topology",
        "get_recent_deployments",
        "find_similar_incidents",
        "search_runbooks",
        "inspect_kafka_lag",
        "inspect_fix_session",
        "inspect_database_health",
    }
)


def canonical_time(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Timestamp must include a timezone")
        return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError) as error:
        raise ValueError("Filters require ISO-8601 timestamps with a timezone") from error


class DiagnosticTools:
    def __init__(self, store: Store, session_id: str, as_of: str | None = None):
        self.store = store
        self.session_id = session_id
        self.as_of = canonical_time(as_of)

    async def call(self, name: str, arguments: dict) -> list[Evidence]:
        if name not in ALLOWED_TOOLS:
            raise ValueError("Tool is outside the read-only diagnostic allowlist")
        try:
            args = ToolArguments.model_validate(arguments)
        except ValidationError as error:
            raise ValueError("Invalid bounded diagnostic arguments") from error
        start, end = canonical_time(args.start), canonical_time(args.end)
        requested_cutoff = canonical_time(args.as_of)
        if self.as_of and requested_cutoff and requested_cutoff != self.as_of:
            raise ValueError("Tool cannot override its fixed snapshot cutoff")
        as_of = self.as_of or requested_cutoff
        if start and end and start > end:
            raise ValueError("start must precede end")
        if name == "get_incident":
            if not args.incident_id:
                raise ValueError("incident_id is required")
            incident = await self.store.get_incident(self.session_id, args.incident_id, as_of=as_of)
            if incident is None:
                return []
            record = await self.store.get_evidence(self.session_id, args.incident_id, as_of=as_of)
            if record is None:
                return []
            impact = await self.store.business_impact(self.session_id, args.incident_id, as_of=as_of)
            # Narrative fixture labels are UI context, never diagnostic observations.
            data = {
                "incident_id": incident.id,
                "severity": incident.severity,
                "started_at": incident.started_at,
                "affected_services": incident.affected_services,
                "symptoms": "Observed operational degradation; determine the condition from timestamped evidence.",
                "as_of": impact.as_of if impact else as_of,
                "timeline": [event.model_dump() for event in incident.timeline],
            }
            metadata = record.model_copy(
                update={"summary": "Current incident observation context", "data": data}
            )
            events = (
                await self.store.evidence(
                    self.session_id,
                    incident_id=args.incident_id,
                    kind="business_event",
                    as_of=as_of,
                    limit=max(1, args.limit - 1),
                )
                if args.limit > 1
                else []
            )
            return [metadata, *events]
        if name == "get_service_topology":
            record = await self.store.get_evidence(self.session_id, "TOPOLOGY-001", as_of=as_of)
            return [record] if record else []
        if name in {"find_similar_incidents", "search_runbooks"}:
            return await self.store.retrieve(
                self.session_id,
                "history" if name == "find_similar_incidents" else "runbook",
                args.q,
                args.service,
                args.limit,
                as_of=as_of,
                incident_id=args.incident_id,
            )
        kinds = {
            "search_logs": ("log", "business_event"),
            "query_metrics": "metric",
            "get_recent_deployments": "deployment",
            "inspect_kafka_lag": "kafka",
            "inspect_fix_session": "fix",
            "inspect_database_health": "database",
        }
        filters = {
            "incident_id": args.incident_id,
            "kind": kinds[name],
            "service": args.service,
            "q": args.q,
            "start": start,
            "end": end,
            "limit": args.limit,
            "offset": args.offset,
            "as_of": as_of,
        }
        if name == "search_logs":
            filters.update(severity=args.severity, trace_id=args.trace_id)
        if name == "query_metrics":
            filters.update(metric=args.metric)
        return await self.store.evidence(self.session_id, **filters)
