"""Session-scoped synthetic simulation and bounded evidence retrieval."""

import asyncio
import json
import math
import re
import time
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import DateTime, String, and_, case, cast, delete, event, func, or_, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .db import (
    Base,
    DatabaseHealthRow,
    DemoRunRow,
    DependencyRow,
    DeploymentRow,
    EvidenceRow,
    FixSessionRow,
    HistoricalIncidentRow,
    IncidentEventRow,
    IncidentRow,
    InvestigationRow,
    InvestigationStepRow,
    KafkaGroupRow,
    KafkaTopicRow,
    LogRow,
    MetricRow,
    RunbookRow,
    ServiceRow,
)
from .models import Evidence, Incident, MetricPoint, MetricSeries, Service
from .security import sanitize
from .seed import make_seed
from .settings import PROJECT_ROOT, get_settings


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://"):
        url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if url.startswith("postgresql+asyncpg://"):
        parsed = urlsplit(url)
        query = [
            ("ssl" if key == "sslmode" else key, value)
            for key, value in parse_qsl(parsed.query)
            if key != "channel_binding"
        ]
        url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
    return url


class Store:
    def __init__(self, database_url: str | None = None, clock: Callable[[], float] | None = None):
        self.database_url = normalize_database_url(database_url or get_settings().database_url)
        if self.database_url.startswith("sqlite"):
            (PROJECT_ROOT / "artifacts").mkdir(parents=True, exist_ok=True)
            path = self.database_url.partition("///")[2].split("?")[0]
            if path and path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
        connection_options = (
            {"ssl": "require"}
            if self.database_url.startswith("postgresql") and get_settings().database_require_ssl
            else {}
        )
        self.engine = create_async_engine(
            self.database_url, pool_pre_ping=True, connect_args=connection_options
        )
        if self.database_url.startswith("sqlite"):

            @event.listens_for(self.engine.sync_engine, "connect")
            def enforce_foreign_keys(connection, _):
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.clock = clock or time.monotonic
        self._starts: dict[tuple[str, str], float] = {}
        self._lock = asyncio.Lock()

    async def initialize(self, seed: bool = True) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        if not seed:
            return
        async with self._lock, self.sessions.begin() as session:
            fixture = make_seed()
            existing_incidents = {row.id: row for row in await session.scalars(select(IncidentRow))}
            existing_evidence = {row.id: row for row in await session.scalars(select(EvidenceRow))}
            first_seed = not existing_incidents
            if first_seed:
                for service in fixture["services"]:
                    session.add(
                        ServiceRow(id=service["id"], name=service["name"], description=service["description"])
                    )
            await session.flush()
            if first_seed:
                for dependency in fixture["dependencies"]:
                    session.add(DependencyRow(**dependency))
                for topic in fixture["topics"]:
                    session.add(
                        KafkaTopicRow(
                            name=topic,
                            partitions=6 if topic == "pricing.updates" else 3,
                            description=f"Fictional {topic} event stream",
                        )
                    )
            pending_events = []
            for incident in fixture["incidents"]:
                payload = {k: v for k, v in incident.items() if k != "interactive"}
                if incident["id"] in existing_incidents:
                    existing_incidents[incident["id"]].payload = payload
                else:
                    session.add(
                        IncidentRow(
                            id=incident["id"],
                            scenario=incident["scenario"],
                            severity=incident["severity"],
                            started_at=incident["started_at"],
                            interactive=incident["interactive"],
                            payload=payload,
                        )
                    )
                    for i, event in enumerate(incident["timeline"]):
                        pending_events.append(
                            IncidentEventRow(
                                id=f"{incident['id']}-EVENT-{i}",
                                incident_id=incident["id"],
                                timestamp=event["timestamp"],
                                reveal_seconds=event["reveal_seconds"],
                                payload=event,
                            )
                        )
            await session.flush()
            session.add_all(pending_events)
            for record in fixture["evidence"]:
                if record["id"] in existing_evidence:
                    row = existing_evidence[record["id"]]
                    if row.data != record["data"]:
                        row.data = record["data"]
                else:
                    session.add(EvidenceRow(**record))
            await session.flush()
            for record in fixture["evidence"]:
                if record["id"] in existing_evidence:
                    continue
                id, kind, data = record["id"], record["kind"], record["data"]
                if kind == "log":
                    session.add(
                        LogRow(
                            evidence_id=id,
                            severity=data["severity"],
                            trace_id=data.get("trace_id"),
                            message=data["message"],
                        )
                    )
                elif kind == "metric":
                    session.add(
                        MetricRow(
                            evidence_id=id, metric=data["metric"], value=data["value"], unit=data["unit"]
                        )
                    )
                elif kind == "kafka":
                    session.add(
                        KafkaGroupRow(
                            evidence_id=id,
                            topic=data["topic"],
                            consumer_group=data["consumer_group"],
                            consumer_lag=data["consumer_lag"],
                        )
                    )
                elif kind == "fix":
                    session.add(
                        FixSessionRow(
                            evidence_id=id,
                            **{
                                key: data[key]
                                for key in [
                                    "session_id",
                                    "connected",
                                    "sender_seq_num",
                                    "target_seq_num",
                                    "reconnect_count",
                                    "sequence_gaps",
                                ]
                            },
                        )
                    )
                elif kind == "database":
                    session.add(
                        DatabaseHealthRow(
                            evidence_id=id,
                            **{key: data[key] for key in ["pool_utilization", "query_latency_ms", "wait_ms"]},
                        )
                    )
                elif kind == "deployment":
                    session.add(
                        DeploymentRow(
                            evidence_id=id,
                            version=data["version"],
                            deployed_at=data["deployed_at"],
                            change=data["change"],
                        )
                    )
                elif kind == "runbook":
                    session.add(
                        RunbookRow(
                            evidence_id=id,
                            title=data["title"],
                            content=data["content"],
                            search_text=data["tags"],
                        )
                    )
                elif kind == "history":
                    session.add(
                        HistoricalIncidentRow(
                            evidence_id=id,
                            title=data["title"],
                            symptoms=data["symptoms"],
                            resolution=data["resolution"],
                        )
                    )

    async def close(self) -> None:
        await self.engine.dispose()

    async def ping(self) -> bool:
        async with self.sessions() as session:
            return (await session.scalar(text("SELECT 1"))) == 1

    def _elapsed(self, run: DemoRunRow) -> float:
        if run.fixed_elapsed is not None:
            return run.fixed_elapsed
        key = (run.session_id, run.incident_id)
        if key not in self._starts:
            # Recover a monotonic reference after process restart from the persisted wall timestamp.
            self._starts[key] = self.clock() - max(0, min(time.time() - run.started_wall, 3600))
        return max(0, min(self.clock() - self._starts[key], 3600))

    async def run_scenario(self, session_id: str, scenario_id: str) -> Incident:
        async with self._lock, self.sessions.begin() as session:
            incident = await session.scalar(
                select(IncidentRow).where(
                    IncidentRow.scenario == scenario_id, IncidentRow.interactive.is_(True)
                )
            )
            if incident is None:
                raise ValueError("Unknown interactive scenario")
            key = (session_id, incident.id)
            existing = await session.get(DemoRunRow, key)
            if existing is None:
                session.add(
                    DemoRunRow(
                        session_id=session_id,
                        incident_id=incident.id,
                        started_wall=time.time(),
                        fixed_elapsed=None,
                    )
                )
                self._starts[key] = self.clock()
        result = await self.get_incident(session_id, incident.id)
        if result is None:
            raise ValueError("Scenario was reset before startup completed; retry the run")
        return result

    async def activate_case(self, session_id: str, incident_id: str) -> Incident:
        """Evaluation-only local API: expose a completed immutable fixture without HTTP mutation tooling."""
        async with self._lock, self.sessions.begin() as session:
            if await session.get(IncidentRow, incident_id) is None:
                raise ValueError("Unknown case")
            run = await session.get(DemoRunRow, (session_id, incident_id))
            if run is None:
                session.add(
                    DemoRunRow(
                        session_id=session_id,
                        incident_id=incident_id,
                        started_wall=time.time(),
                        fixed_elapsed=300,
                    )
                )
            else:
                run.fixed_elapsed = 300
        result = await self.get_incident(session_id, incident_id)
        if result is None:
            raise ValueError("Evaluation case was reset before activation completed")
        return result

    async def reset_scenario(self, session_id: str, scenario_id: str) -> None:
        async with self._lock, self.sessions.begin() as session:
            incident = await session.scalar(
                select(IncidentRow).where(
                    IncidentRow.scenario == scenario_id, IncidentRow.interactive.is_(True)
                )
            )
            if incident is None:
                raise ValueError("Unknown interactive scenario")
            await session.execute(
                delete(DemoRunRow).where(
                    DemoRunRow.session_id == session_id, DemoRunRow.incident_id == incident.id
                )
            )
            investigations = await session.scalars(
                select(InvestigationRow.id).where(
                    InvestigationRow.session_id == session_id, InvestigationRow.incident_id == incident.id
                )
            )
            ids = list(investigations)
            if ids:
                await session.execute(
                    delete(InvestigationStepRow).where(
                        InvestigationStepRow.session_id == session_id,
                        InvestigationStepRow.investigation_id.in_(ids),
                    )
                )
                await session.execute(
                    delete(InvestigationRow).where(
                        InvestigationRow.session_id == session_id, InvestigationRow.id.in_(ids)
                    )
                )
            self._starts.pop((session_id, incident.id), None)

    async def get_incident(self, session_id: str, id: str) -> Incident | None:
        async with self.sessions() as session:
            run = await session.get(DemoRunRow, (session_id, id))
            incident = await session.get(IncidentRow, id)
            if run is None or incident is None:
                return None
            elapsed = self._elapsed(run)
            payload = dict(incident.payload)
            payload["timeline"] = [
                {k: v for k, v in event.items() if k != "reveal_seconds"}
                for event in payload["timeline"]
                if event["reveal_seconds"] <= elapsed
            ]
            payload["simulated_elapsed_seconds"] = int(elapsed * 12)
            return Incident.model_validate(payload)

    async def list_incidents(self, session_id: str) -> list[Incident]:
        async with self.sessions() as session:
            ids = list(
                await session.scalars(
                    select(DemoRunRow.incident_id).where(DemoRunRow.session_id == session_id)
                )
            )
        return [incident for id in ids if (incident := await self.get_incident(session_id, id)) is not None]

    async def case_catalog(self) -> list[dict]:
        async with self.sessions() as session:
            rows = (await session.scalars(select(IncidentRow).order_by(IncidentRow.id))).all()
            return [
                {
                    "id": row.id,
                    "scenario": row.scenario,
                    "title": row.payload["title"],
                    "interactive": row.interactive,
                }
                for row in rows
            ]

    async def scenarios(self) -> list[dict]:
        return [
            {
                "id": case["scenario"],
                "title": case["title"],
                "description": "Progressively replay persisted synthetic operational signals.",
                "incident_id": case["id"],
            }
            for case in await self.case_catalog()
            if case["interactive"]
        ]

    async def _evidence_query(
        self,
        session_id: str,
        incident_id: str | None = None,
        kind: str | None = None,
        service: str | None = None,
        q: str | None = None,
        severity: str | None = None,
        trace_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        metric: str | None = None,
    ):
        async with self.sessions() as session:
            runs = (
                await session.scalars(select(DemoRunRow).where(DemoRunRow.session_id == session_id))
            ).all()
        clauses = [
            and_(EvidenceRow.incident_id == run.incident_id, EvidenceRow.reveal_seconds <= self._elapsed(run))
            for run in runs
            if incident_id is None or run.incident_id == incident_id
        ]
        if incident_id is None:
            clauses.append(EvidenceRow.incident_id.is_(None))
        query = select(EvidenceRow).where(
            or_(*clauses) if clauses else EvidenceRow.id == "__no_visible_evidence__"
        )
        for column, value in [(EvidenceRow.kind, kind), (EvidenceRow.service, service)]:
            if value is not None:
                query = query.where(column == value)
        if q:
            needle = q.lower()
            query = query.where(
                or_(
                    func.lower(EvidenceRow.summary).contains(needle, autoescape=True),
                    func.lower(cast(EvidenceRow.data, String)).contains(needle, autoescape=True),
                )
            )
        if severity is not None or trace_id is not None:
            query = query.join(LogRow, LogRow.evidence_id == EvidenceRow.id)
            if severity is not None:
                query = query.where(LogRow.severity == severity)
            if trace_id is not None:
                query = query.where(LogRow.trace_id == trace_id)
        if metric:
            query = query.join(MetricRow, MetricRow.evidence_id == EvidenceRow.id).where(
                MetricRow.metric == metric
            )
        if start:
            query = (
                query.where(func.julianday(EvidenceRow.timestamp) >= func.julianday(start))
                if self.engine.dialect.name == "sqlite"
                else query.where(
                    cast(EvidenceRow.timestamp, DateTime(timezone=True))
                    >= datetime.fromisoformat(start.replace("Z", "+00:00"))
                )
            )
        if end:
            query = (
                query.where(func.julianday(EvidenceRow.timestamp) <= func.julianday(end))
                if self.engine.dialect.name == "sqlite"
                else query.where(
                    cast(EvidenceRow.timestamp, DateTime(timezone=True))
                    <= datetime.fromisoformat(end.replace("Z", "+00:00"))
                )
            )
        return query

    @staticmethod
    def _public(row: EvidenceRow) -> Evidence:
        return Evidence(
            id=row.id,
            kind=row.kind,
            service=row.service,
            timestamp=row.timestamp,
            summary=sanitize(row.summary),
            data=sanitize(row.data),
        )

    async def evidence(
        self,
        session_id: str,
        incident_id: str | None = None,
        kind: str | None = None,
        service: str | None = None,
        q: str | None = None,
        severity: str | None = None,
        trace_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 50,
        offset: int = 0,
        metric: str | None = None,
    ) -> list[Evidence]:
        if not 1 <= limit <= 50 or not 0 <= offset <= 5000:
            raise ValueError("Evidence result bounds exceeded")
        query = await self._evidence_query(
            session_id, incident_id, kind, service, q, severity, trace_id, start, end, metric
        )
        async with self.sessions() as session:
            ordering = (
                (
                    case((EvidenceRow.id.contains("-SERIES-"), 1), else_=0),
                    EvidenceRow.timestamp.desc(),
                    EvidenceRow.id,
                )
                if kind == "metric"
                else (EvidenceRow.timestamp, EvidenceRow.id)
            )
            rows = (await session.scalars(query.order_by(*ordering).limit(limit).offset(offset))).all()
            return [self._public(row) for row in rows]

    async def evidence_count(self, session_id: str, **filters) -> int:
        query = await self._evidence_query(session_id, **filters)
        async with self.sessions() as session:
            return int(await session.scalar(select(func.count()).select_from(query.subquery())) or 0)

    async def get_evidence(self, session_id: str, id: str) -> Evidence | None:
        query = await self._evidence_query(session_id)
        async with self.sessions() as session:
            row = await session.scalar(query.where(EvidenceRow.id == id))
            return self._public(row) if row else None

    async def metrics(self, session_id: str, aggregation: str = "raw", **filters) -> list[MetricSeries]:
        if aggregation not in {"raw", "avg", "min", "max"}:
            raise ValueError("Unsupported aggregation")
        query = await self._evidence_query(session_id, kind="metric", **filters)
        async with self.sessions() as session:
            rows = (
                await session.scalars(query.order_by(EvidenceRow.timestamp, EvidenceRow.id).limit(1000))
            ).all()
            records = [self._public(row) for row in rows]
        grouped: dict[tuple[str, str, str], list[Evidence]] = {}
        for record in records:
            key = (record.service, record.data["metric"], record.data["unit"])
            grouped.setdefault(key, []).append(record)
        result = []
        for (service, metric, unit), rows in grouped.items():
            points = [
                MetricPoint(timestamp=row.timestamp, value=float(row.data["value"]), evidence_id=row.id)
                for row in rows
            ]
            if aggregation != "raw" and points:
                values = [point.value for point in points]
                # Aggregate points preserve the most recent contributing evidence ID.
                value = (
                    sum(values) / len(values)
                    if aggregation == "avg"
                    else (max(values) if aggregation == "max" else min(values))
                )
                points = [
                    MetricPoint(
                        timestamp=points[-1].timestamp, value=value, evidence_id=points[-1].evidence_id
                    )
                ]
            result.append(MetricSeries(service=service, metric=metric, unit=unit, points=points))
        return result

    async def topology(self, session_id: str) -> dict:
        active = await self.list_incidents(session_id)
        statuses = {service: "degraded" for incident in active for service in incident.affected_services}
        async with self.sessions() as session:
            services = (await session.scalars(select(ServiceRow).order_by(ServiceRow.id))).all()
            dependencies = (await session.scalars(select(DependencyRow))).all()
            return {
                "services": [
                    Service(
                        id=row.id,
                        name=row.name,
                        description=row.description,
                        status=statuses.get(row.id, "healthy"),
                    ).model_dump()
                    for row in services
                ],
                "dependencies": [{"source": row.source, "target": row.target} for row in dependencies],
            }

    async def retrieve(
        self, session_id: str, kind: str, q: str | None, service: str | None = None, limit: int = 10
    ) -> list[Evidence]:
        """BM25-style lexical retrieval with explicit symptom/service match explanations."""
        candidates = await self.evidence(session_id, kind=kind, limit=50)
        terms = re.findall(r"[a-z0-9_-]+", (q or "").lower())[:30]
        documents = [
            re.findall(r"[a-z0-9_-]+", (row.summary + " " + json.dumps(row.data)).lower())
            for row in candidates
        ]
        n = len(documents)
        average_length = sum(map(len, documents)) / max(n, 1)
        scored = []
        for row, document in zip(candidates, documents, strict=True):
            frequencies = Counter(document)
            matching = [term for term in terms if term in frequencies]
            score = 0.0
            for term in matching:
                df = sum(term in doc for doc in documents)
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                tf = frequencies[term]
                score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(document) / max(average_length, 1)))
            service_match = service is not None and row.service == service
            score += 2.0 if service_match else 0
            if not terms or score > 0:
                data = dict(row.data)
                data["retrieval"] = {
                    "method": "lexical_bm25",
                    "score": round(score, 4),
                    "matching_terms": sorted(set(matching)),
                    "overlapping_services": [service] if service_match else [],
                    "explanation": f"Matched {', '.join(sorted(set(matching))) or 'catalog entry'}"
                    + (f"; shared service {service}" if service_match else ""),
                }
                scored.append((score, row.model_copy(update={"data": data})))
        lexical = [row for _, row in sorted(scored, key=lambda pair: (-pair[0], pair[1].id))]
        if q and get_settings().embeddings_enabled:
            from .embeddings import query_references

            vectors = await query_references(self, kind, q, limit)
            if vectors:
                positions = {row.id: i + 1 for i, row in enumerate(lexical)}
                similarity = {id: score for id, score in vectors}
                vector_positions = {id: i + 1 for i, (id, _) in enumerate(vectors)}
                candidates_by_id = {row.id: row for row in candidates}
                scores = {
                    id: (1 / (60 + positions[id]) if id in positions else 0)
                    + (1 / (60 + vector_positions[id]) if id in vector_positions else 0)
                    for id in positions.keys() | vector_positions.keys()
                    if id in candidates_by_id
                }
                fused = []
                for id in sorted(scores, key=lambda identifier: (-scores[identifier], identifier))[:limit]:
                    row = candidates_by_id[id]
                    data = dict(row.data)
                    data["retrieval"] = {
                        "method": "hybrid_bm25_pgvector",
                        "score": round(scores[id], 6),
                        "vector_similarity": similarity.get(id),
                        "matching_terms": sorted(
                            set(terms) & set(re.findall(r"[a-z0-9_-]+", json.dumps(data).lower()))
                        ),
                        "overlapping_services": [service] if service and service == row.service else [],
                        "explanation": "Rank fusion of lexical symptom matches and configured embedding similarity",
                    }
                    fused.append(row.model_copy(update={"data": data}))
                return fused
        return lexical[:limit]

    async def save_investigation(self, session_id: str, payload: dict) -> dict:
        async with self._lock, self.sessions.begin() as session:
            key = (session_id, payload["id"])
            row = await session.get(InvestigationRow, key)
            values = {
                "incident_id": payload["incident_id"],
                "mode": payload["mode"],
                "status": payload["status"],
                "created_at": payload["created_at"],
                "payload": sanitize(payload),
            }
            if row is None:
                session.add(InvestigationRow(session_id=session_id, id=payload["id"], **values))
            else:
                for name, value in values.items():
                    setattr(row, name, value)
            await session.flush()
            await session.execute(
                delete(InvestigationStepRow).where(
                    InvestigationStepRow.session_id == session_id,
                    InvestigationStepRow.investigation_id == payload["id"],
                )
            )
            for i, step in enumerate(payload.get("steps", [])):
                session.add(
                    InvestigationStepRow(
                        session_id=session_id,
                        investigation_id=payload["id"],
                        id=step["id"],
                        position=i,
                        tool=step["tool"],
                        payload=sanitize(step),
                    )
                )
        return payload

    async def get_investigation(self, session_id: str, id: str) -> dict | None:
        async with self.sessions() as session:
            row = await session.get(InvestigationRow, (session_id, id))
            return dict(row.payload) if row else None

    async def investigation_count(self, session_id: str) -> int:
        async with self.sessions() as session:
            return int(
                await session.scalar(
                    select(func.count())
                    .select_from(InvestigationRow)
                    .where(InvestigationRow.session_id == session_id)
                )
                or 0
            )

    async def overview(self, session_id: str) -> dict:
        topology = await self.topology(session_id)
        kafka = await self.evidence(session_id, kind="kafka")
        fix = await self.evidence(session_id, kind="fix")
        database = await self.evidence(session_id, kind="database")
        kafka_lag = max([row.data["consumer_lag"] for row in kafka], default=3)
        disconnected = any(not row.data["connected"] for row in fix)
        pool = max([row.data["pool_utilization"] for row in database], default=0.35)
        return {
            "services": topology["services"],
            "active_incidents": [i.model_dump() for i in await self.list_incidents(session_id)],
            "kafka": {
                "status": "degraded" if kafka_lag > 1000 else "healthy",
                "consumer_lag": kafka_lag,
                "topic_count": 6,
            },
            "fix": {
                "status": "degraded" if disconnected else "healthy",
                "connected": not disconnected,
                "session_count": 2,
                "reconnect_count": max([row.data["reconnect_count"] for row in fix], default=0),
            },
            "database": {
                "status": "critical" if pool > 0.9 else "healthy",
                "pool_utilization": pool,
                "query_latency_ms": max([row.data["query_latency_ms"] for row in database], default=12),
            },
            "investigation_count": await self.investigation_count(session_id),
            "clock": {"label": "Synthetic clock · 12 seconds per real second", "scale": 12},
            "telemetry_mode": get_settings().telemetry_mode,
        }


async def seed_database() -> None:
    store = Store()
    await store.initialize()
    print(
        json.dumps(
            {
                "status": "seeded",
                "incident_count": len(await store.case_catalog()),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
    )
    await store.close()


if __name__ == "__main__":
    asyncio.run(seed_database())
