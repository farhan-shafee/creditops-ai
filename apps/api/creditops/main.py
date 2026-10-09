"""FastAPI boundary for a synthetic operations platform. Diagnostic tools are read-only."""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, generate_latest
from pydantic import Field
from starlette.types import ASGIApp, Receive, Scope, Send

from .models import (
    BusinessImpact,
    Evidence,
    Incident,
    Instrument,
    Investigation,
    InvestigationRequest,
    ToolArguments,
)
from .security import RateLimiter, authorize_admin, sanitize
from .settings import Settings, get_settings
from .store import Store
from .telemetry import SyntheticTelemetryAdapter
from .tools import DiagnosticTools, canonical_time


class JSONLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            "logger": record.name,
        }
        for field in (
            "tool",
            "incident_id",
            "investigation_id",
            "error_type",
            "method",
            "path",
            "status",
            "duration_ms",
        ):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(sanitize(payload))


def configure_logging() -> None:
    logger = logging.getLogger("creditops")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not any(isinstance(handler.formatter, JSONLogFormatter) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JSONLogFormatter())
        logger.addHandler(handler)


class DiagnosticQuery(ToolArguments):
    """Parse HTTP query strings before entering the strictly typed tool boundary."""

    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=5000)


class RequestSizeLimit:
    def __init__(self, app: ASGIApp, limit: int):
        self.app, self.limit = app, limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            await JSONResponse({"detail": "Invalid content length"}, status_code=400)(scope, receive, send)
            return
        if length < 0 or length > self.limit or len(scope.get("query_string", b"")) > 8192:
            await JSONResponse({"detail": "Request exceeded size limit"}, status_code=413)(
                scope, receive, send
            )
            return
        chunks, size = [], 0
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            size += len(event.get("body", b""))
            if size > self.limit:
                await JSONResponse({"detail": "Request exceeded size limit"}, status_code=413)(
                    scope, receive, send
                )
                return
            chunks.append(event.get("body", b""))
            if not event.get("more_body", False):
                break
        body = b"".join(chunks)
        sent = False

        async def bounded_receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)


def demo_session(x_demo_session: Annotated[str | None, Header()] = None) -> str:
    if x_demo_session is None:
        return "00000000-0000-4000-8000-000000000000"
    try:
        return str(UUID(x_demo_session))
    except (ValueError, TypeError, AttributeError) as error:
        raise HTTPException(400, "X-Demo-Session must be a UUID") from error


Session = Annotated[str, Depends(demo_session)]
Short = Annotated[str | None, Query(max_length=96)]
TimeFilter = Annotated[str | None, Query(max_length=40)]
SearchFilter = Annotated[str | None, Query(max_length=240)]


def create_app(
    store: Store | None = None, manage_store: bool = True, settings: Settings | None = None
) -> FastAPI:
    configure_logging()
    configuration = settings or get_settings()
    database = store or Store(configuration.database_url)
    tasks: dict[tuple[str, str], tuple[str, asyncio.Task]] = {}
    registry = CollectorRegistry()
    http_requests = Counter(
        "creditops_http_requests_total", "HTTP requests", ["method", "path", "status"], registry=registry
    )
    investigation_runs = Counter(
        "creditops_investigations_total", "Investigation results", ["status", "mode"], registry=registry
    )
    latency = Gauge(
        "creditops_service_latency_ms", "Synthetic service latency p95", ["service"], registry=registry
    )
    kafka_lag = Gauge("creditops_kafka_consumer_lag", "Synthetic consumer lag", ["group"], registry=registry)
    fix_connected = Gauge(
        "creditops_fix_connected", "Synthetic FIX connectivity", ["session"], registry=registry
    )
    db_pool = Gauge(
        "creditops_db_pool_utilization", "Synthetic DB pool utilization", ["service"], registry=registry
    )
    investigation_limiter = RateLimiter(
        configuration.max_investigations_per_window, configuration.rate_limit_window_seconds
    )
    ip_limiter = RateLimiter(
        configuration.max_investigations_per_window * 3, configuration.rate_limit_window_seconds
    )
    simulation_limiter = RateLimiter(60, 60)
    adapter = SyntheticTelemetryAdapter(configuration.telemetry_mode, configuration.kafka_bootstrap_servers)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if manage_store:
            await database.initialize()
        await adapter.start()
        app.state.store = database
        for service in (await database.topology("00000000-0000-4000-8000-000000000000"))["services"]:
            latency.labels(service["id"]).set(85)
        kafka_lag.labels("pricing-credit-demo").set(3)
        fix_connected.labels("FIX-DEMO-SESSION-A").set(1)
        db_pool.labels("quote-service").set(0.35)
        yield
        running = [task for _, task in tasks.values()]
        for task in running:
            task.cancel()
        if running:
            await asyncio.gather(*running, return_exceptions=True)
        await adapter.close()
        if manage_store:
            await database.close()

    app = FastAPI(title="CreditOps AI — Synthetic Read-only Diagnostics", version="1.0.0", lifespan=lifespan)
    app.state.store = database
    app.add_middleware(RequestSizeLimit, limit=configuration.max_request_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configuration.cors_origins.split(","),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Demo-Session", "Authorization"],
    )

    @app.middleware("http")
    async def observe_http(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")
        http_requests.labels(request.method, path, str(response.status_code)).inc()
        logging.getLogger("creditops.http").info(
            "http_request",
            extra={
                "method": request.method,
                "path": path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def bad_request(request: Request, error: ValueError):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.get("/health")
    async def health():
        try:
            database_ok = await asyncio.wait_for(database.ping(), timeout=3)
        except Exception:
            database_ok = False
        return JSONResponse(
            {
                "status": "healthy" if database_ok else "degraded",
                "database": "connected" if database_ok else "unavailable",
                "telemetry_mode": adapter.health()["mode"],
                "kafka": adapter.health(),
                "environment": "synthetic",
                "diagnostic_capabilities": "read-only",
            },
            status_code=200 if database_ok else 503,
        )

    @app.get("/metrics", include_in_schema=False)
    async def prometheus():
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    @app.get("/api/overview")
    async def overview(session_id: Session):
        value = await database.overview(session_id)
        value["telemetry_mode"] = adapter.health()["mode"]
        value["telemetry_transport"] = adapter.health()
        for series in await database.metrics(session_id):
            if series.metric == "request_latency_p95_ms" and series.points:
                latency.labels(series.service).set(series.points[-1].value)
        kafka_lag.labels("pricing-credit-demo").set(value["kafka"]["consumer_lag"])
        fix_connected.labels("FIX-DEMO-SESSION-A").set(int(value["fix"]["connected"]))
        db_pool.labels("quote-service").set(value["database"]["pool_utilization"])
        return value

    @app.get("/api/scenarios")
    async def scenarios():
        return await database.scenarios()

    @app.post("/api/demo/scenarios/{scenario}/run", response_model=Incident)
    async def run_scenario(scenario: str, session_id: Session, request: Request):
        ip = request.client.host if request.client else "unknown"
        if not simulation_limiter.allow(ip):
            raise HTTPException(429, "Simulation budget exceeded; retry in one minute")
        row = await database.run_scenario(session_id, scenario)
        await adapter.publish_incident(row.id)
        return row

    @app.post("/api/demo/scenarios/{scenario}/reset")
    async def reset_scenario(scenario: str, session_id: Session):
        match = next((row for row in await database.scenarios() if row["id"] == scenario), None)
        if match is None:
            raise HTTPException(404, "Scenario not found")
        running = [
            task
            for (owner, _), (incident, task) in list(tasks.items())
            if owner == session_id and incident == match["incident_id"]
        ]
        for task in running:
            task.cancel()
        if running:
            await asyncio.gather(*running, return_exceptions=True)
        await database.reset_scenario(session_id, scenario)
        return {"status": "reset"}

    @app.get("/api/incidents", response_model=list[Incident])
    async def incidents(session_id: Session):
        return await database.list_incidents(session_id)

    @app.get("/api/incidents/{id}", response_model=Incident)
    async def incident(id: str, session_id: Session, as_of: TimeFilter = None):
        row = await database.get_incident(session_id, id, as_of=canonical_time(as_of))
        if row is None:
            raise HTTPException(404, "Incident not found in this session")
        return row

    @app.get("/api/instruments", response_model=list[Instrument])
    async def instruments():
        return await database.instruments()

    @app.get("/api/incidents/{id}/business-impact", response_model=BusinessImpact)
    async def business_impact(id: str, session_id: Session, as_of: TimeFilter = None):
        value = await database.business_impact(session_id, id, as_of=canonical_time(as_of))
        if value is None:
            raise HTTPException(404, "Incident not found in this session")
        return value

    @app.get("/api/logs/search")
    async def logs(
        session_id: Session,
        service: Short = None,
        severity: Short = None,
        trace_id: Short = None,
        q: SearchFilter = None,
        start: TimeFilter = None,
        end: TimeFilter = None,
        incident_id: Short = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 25,
        offset: Annotated[int, Query(ge=0, le=5000)] = 0,
    ):
        if severity and severity not in {"DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"}:
            raise HTTPException(422, "Invalid severity")
        lower, upper = canonical_time(start), canonical_time(end)
        if lower and upper and lower > upper:
            raise HTTPException(422, "start must precede end")
        filters = {
            "kind": ("log", "business_event"),
            "service": service,
            "severity": severity,
            "trace_id": trace_id,
            "q": q,
            "start": lower,
            "end": upper,
            "incident_id": incident_id,
        }
        items = await database.evidence(session_id, limit=limit, offset=offset, **filters)
        total = await database.evidence_count(session_id, **filters)
        return {
            "items": items,
            "total": total,
            "next_offset": offset + len(items) if offset + len(items) < total else None,
        }

    @app.get("/api/metrics/query")
    async def query_metrics(
        session_id: Session,
        service: Short = None,
        metric: Short = None,
        start: TimeFilter = None,
        end: TimeFilter = None,
        incident_id: Short = None,
        aggregation: Annotated[str, Query(pattern="^(raw|avg|min|max)$")] = "raw",
    ):
        lower, upper = canonical_time(start), canonical_time(end)
        if lower and upper and lower > upper:
            raise HTTPException(422, "start must precede end")
        return await database.metrics(
            session_id,
            service=service,
            metric=metric,
            start=lower,
            end=upper,
            incident_id=incident_id,
            aggregation=aggregation,
        )

    @app.get("/api/services/topology")
    async def topology(session_id: Session):
        return await database.topology(session_id)

    @app.get("/api/telemetry/{kind}", response_model=list[Evidence])
    async def telemetry(kind: str, session_id: Session, incident_id: Short = None):
        kinds = {"kafka": "kafka", "fix": "fix", "database": "database", "deployments": "deployment"}
        if kind not in kinds:
            raise HTTPException(404, "Telemetry kind not found")
        return await database.evidence(session_id, incident_id=incident_id, kind=kinds[kind])

    @app.get("/api/evidence/{id}", response_model=Evidence)
    async def evidence(id: str, session_id: Session):
        row = await database.get_evidence(session_id, id)
        if row is None:
            raise HTTPException(404, "Evidence not found in this session")
        return row

    @app.get("/api/runbooks", response_model=list[Evidence])
    async def runbooks(session_id: Session, q: SearchFilter = None):
        return await database.retrieve(session_id, "runbook", q, limit=20)

    @app.get("/api/history", response_model=list[Evidence])
    async def history(session_id: Session, q: SearchFilter = None):
        return await database.retrieve(session_id, "history", q, limit=20)

    @app.get("/api/diagnostics/{name}", response_model=list[Evidence])
    async def diagnostics(name: str, session_id: Session, arguments: Annotated[DiagnosticQuery, Query()]):
        return await DiagnosticTools(database, session_id).call(name, arguments.model_dump(exclude_none=True))

    @app.get("/api/evaluations/latest")
    async def latest_evaluation():
        path = configuration.project_root / "artifacts" / "eval" / "latest.json"
        if not path.is_file():
            return {"status": "not_generated"}
        if path.stat().st_size > 2_000_000:
            raise HTTPException(503, "Evaluation artifact exceeds size budget")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as error:
            raise HTTPException(503, "Evaluation artifact unavailable") from error

    async def worker(session_id: str, id: str):
        from .investigator import run_investigation

        try:
            await run_investigation(database, session_id, id)
            row = await database.get_investigation(session_id, id)
            if row:
                investigation_runs.labels(row["status"], row["mode"]).inc()
        finally:
            tasks.pop((session_id, id), None)

    @app.post("/api/investigations", response_model=Investigation)
    async def create_investigation(
        body: InvestigationRequest,
        session_id: Session,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
    ):
        from .investigator import create_investigation as create

        if body.mode == "LIVE_AI":
            key = configuration.admin_api_key.get_secret_value() if configuration.admin_api_key else None
            if not authorize_admin(authorization, key):
                raise HTTPException(403, "LIVE_AI requires a server-side admin key")
        if await database.get_incident(session_id, body.incident_id) is None:
            raise HTTPException(404, "Run this incident in your demo session first")
        ip = request.client.host if request.client else "unknown"
        if not ip_limiter.allow(ip) or not investigation_limiter.allow(session_id):
            raise HTTPException(429, "Investigation budget exceeded; wait for the current window to reset")
        row = await create(database, session_id, body.incident_id, body.mode)
        task = asyncio.create_task(worker(session_id, row["id"]))
        tasks[(session_id, row["id"])] = (body.incident_id, task)
        return row

    @app.get("/api/investigations/{id}", response_model=Investigation)
    async def investigation(id: str, session_id: Session):
        row = await database.get_investigation(session_id, id)
        if row is None:
            raise HTTPException(404, "Investigation not found in this session")
        return row

    @app.get("/api/investigations/{id}/events")
    async def investigation_events(id: str, session_id: Session):
        from .investigator import stream_events

        if await database.get_investigation(session_id, id) is None:
            raise HTTPException(404, "Investigation not found in this session")
        return StreamingResponse(
            stream_events(database, session_id, id),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    return app


app = create_app()
