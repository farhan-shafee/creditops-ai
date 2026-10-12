"""Real-socket regression for ordinary recorded SSE polling cancellation."""

import asyncio
import contextvars
import copy
import json
import logging
import os
import socket
import weakref
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import aiosqlite
import httpx
import pytest
import uvicorn
from creditops import investigator
from creditops.db import InvestigationRow
from creditops.main import create_app
from creditops.settings import Settings
from creditops.sse_reads import PollingStore
from creditops.store import Store
from sqlalchemy import event

ROLE = contextvars.ContextVar("owned_sse_role", default=False)


@asynccontextmanager
async def server_for(app):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    sock.setblocking(False)
    port = sock.getsockname()[1]
    ready = asyncio.Event()

    class ReadyServer(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets)
            ready.set()

    server = ReadyServer(
        uvicorn.Config(
            app, host="127.0.0.1", port=port, lifespan="on", log_config=None, timeout_graceful_shutdown=3
        )
    )
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        await asyncio.wait_for(ready.wait(), 3)
        yield server, port
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(task, 5)
        finally:
            sock.close()


class RequestRole:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        token = ROLE.set(scope["type"] == "http" and scope.get("path", "").endswith("/events"))
        try:
            return await self.app(scope, receive, send)
        finally:
            ROLE.reset(token)


@pytest.mark.parametrize(
    "backend",
    [
        "sqlite",
        pytest.param(
            "postgres",
            marks=pytest.mark.skipif(
                not os.getenv("CREDITOPS_TEST_DATABASE_URL"),
                reason="Disposable local PostgreSQL URL not configured",
            ),
        ),
    ],
)
async def test_recorded_stream_pre_ping_disconnect_joins_owned_cleanup(
    tmp_path, monkeypatch, caplog, backend
):
    database = Store(
        os.environ["CREDITOPS_TEST_DATABASE_URL"]
        if backend == "postgres"
        else f"sqlite+aiosqlite:///{(tmp_path / 'owned.db').as_posix()}"
    )
    await database.initialize()
    counts = {"checkout": 0, "checkin": 0, "invalidation": 0, "engine_error": 0}
    labels = weakref.WeakKeyDictionary()
    threads = {}
    drivers_seen = []
    unusable = set()
    reused_unusable = []
    active = set()

    def driver_name(driver):
        if driver not in labels:
            drivers_seen.append(driver)
            labels[driver] = f"D{len(drivers_seen)}"
        name = labels[driver]
        if backend == "sqlite":
            threads[name] = driver._thread
        return name

    @event.listens_for(database.engine.sync_engine, "connect")
    def connected(connection, _):
        driver_name(connection.driver_connection)

    @event.listens_for(database.engine.sync_engine, "checkout")
    def checkout(connection, record, _):
        counts["checkout"] += 1
        active.add(id(record))
        name = driver_name(connection.driver_connection)
        if name in unusable:
            reused_unusable.append(name)

    @event.listens_for(database.engine.sync_engine, "checkin")
    def checkin(_, record):
        counts["checkin"] += 1
        active.discard(id(record))

    @event.listens_for(database.engine.sync_engine, "invalidate")
    def invalidate(connection, _, error):
        counts["invalidation"] += 1
        if connection is not None:
            unusable.add(driver_name(connection.driver_connection))

    @event.listens_for(database.engine.sync_engine, "handle_error")
    def engine_error(_):
        counts["engine_error"] += 1

    ready, release, complete = asyncio.Event(), asyncio.Event(), asyncio.Event()
    native_query_completed = False
    read_ordinal = 0
    live_reads = set()
    child_cancel = []
    elapsed = None
    captured_source = {}
    original_read = investigator.read_replay_artifact

    def capture_source(*args, **kwargs):
        value = original_read(*args, **kwargs)
        captured_source.clear()
        captured_source.update(copy.deepcopy(value))
        return value

    monkeypatch.setattr(investigator, "read_replay_artifact", capture_source)
    original_save = database.save_investigation

    async def observe_save(*args, **kwargs):
        value = await original_save(*args, **kwargs)
        if value["status"] == "complete":
            complete.set()
        return value

    monkeypatch.setattr(database, "save_investigation", observe_save)
    original_execute = aiosqlite.Cursor.execute

    async def schedule_after_real_query(cursor, statement, parameters=None):
        nonlocal native_query_completed
        value = await original_execute(cursor, statement, parameters)
        if ROLE.get() and read_ordinal >= 2 and statement == "SELECT 1" and not ready.is_set():
            native_query_completed = True
            ready.set()
            await release.wait()  # Test-only async scheduling; native work has already returned.
        return value

    if backend == "sqlite":
        monkeypatch.setattr(aiosqlite.Cursor, "execute", schedule_after_real_query)
    else:
        original_ping = database.engine.sync_engine.dialect.do_ping

        def schedule_after_real_ping(connection):
            nonlocal native_query_completed
            value = original_ping(connection)
            if ROLE.get() and read_ordinal >= 2 and not ready.is_set():
                assert value
                native_query_completed = True
                ready.set()

                async def hold_after_ping(_driver):
                    await release.wait()

                connection.run_async(hold_after_ping)
            return value

        monkeypatch.setattr(database.engine.sync_engine.dialect, "do_ping", schedule_after_real_ping)

    class ObservedRead(database.sessions.class_):
        async def get(self, entity, ident, **kwargs):
            nonlocal read_ordinal
            if not ROLE.get() or entity is not InvestigationRow:
                return await super().get(entity, ident, **kwargs)
            read_ordinal += 1
            task = asyncio.current_task()
            live_reads.add(id(task))
            try:
                return await super().get(entity, ident, **kwargs)
            except asyncio.CancelledError as error:
                child_cancel.append(
                    {"scope_reason": "cancel scope" in str(error), "cancellation_calls": task.cancelling()}
                )
                raise
            finally:
                live_reads.discard(id(task))

    database.sessions.class_ = ObservedRead

    outer_cancel = []
    propagated_cancel = []
    original_shield = asyncio.shield

    def observe_owned_shield(child):
        protected = original_shield(child)
        if not isinstance(child, asyncio.Task) or child.get_name() != "creditops.sse.poll":
            return protected

        async def observe():
            try:
                return await protected
            except asyncio.CancelledError as error:
                outer_cancel.append((id(error), "cancel scope" in str(error)))
                raise

        return observe()

    monkeypatch.setattr(asyncio, "shield", observe_owned_shield)
    original_poll = PollingStore.get_investigation

    async def observe_outer_propagation(polling_store, *args):
        try:
            return await original_poll(polling_store, *args)
        except asyncio.CancelledError as error:
            propagated_cancel.append(id(error))
            raise

    monkeypatch.setattr(PollingStore, "get_investigation", observe_outer_propagation)

    settings = Settings(
        _env_file=None,
        public_demo=True,
        telemetry_mode="persisted",
        replay_dir=Path(__file__).parents[3] / "data" / "showcase",
    )
    raw_app = create_app(database, manage_store=False, settings=settings)
    app = RequestRole(raw_app)
    caplog.set_level(logging.ERROR, logger="sqlalchemy.pool")
    leftovers = []
    try:
        async with server_for(app) as (server, port):
            session = str(uuid4())
            async with httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{port}", headers={"X-Demo-Session": session}
            ) as client:
                assert (await client.post("/api/demo/scenarios/kafka-pricing-lag/run")).status_code == 200
                created = await client.post(
                    "/api/investigations", json={"incident_id": "INC-DEMO-001", "mode": "REPLAY"}
                )
                assert created.status_code == 200
                identifier = created.json()["id"]
                _, writer = await asyncio.open_connection("127.0.0.1", port)
                try:
                    writer.write(
                        f"GET /api/investigations/{identifier}/events HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Demo-Session: {session}\r\n\r\n".encode()
                    )
                    await writer.drain()
                    await asyncio.wait_for(ready.wait(), 3)
                    assert native_query_completed
                    before = database.engine.pool.checkedout()
                    started = asyncio.get_running_loop().time()
                    writer.close()
                    await writer.wait_closed()
                    requests = list(server.server_state.tasks)
                    if requests:
                        await asyncio.wait_for(asyncio.gather(*requests, return_exceptions=True), 3)
                    elapsed = asyncio.get_running_loop().time() - started
                    await asyncio.wait_for(complete.wait(), 3)
                    workers = [
                        task
                        for task in asyncio.all_tasks()
                        if getattr(task.get_coro(), "__qualname__", "").endswith("create_app.<locals>.worker")
                    ]
                    if workers:
                        await asyncio.wait_for(asyncio.gather(*workers, return_exceptions=True), 3)
                    later = await client.get(f"/api/investigations/{identifier}")
                    assert later.status_code == 200
                    row = later.json()
                    artifact = captured_source["investigation"]
                    provenance = captured_source["provenance"]
                    fields = {
                        field: row.get(field)
                        == artifact.get(field, [] if field == "provider_calls" else None)
                        for field in (
                            "provider_proposal",
                            "validation_outcome",
                            "provider_calls",
                            "assessment",
                            "evidence",
                            "usage",
                        )
                    }
                    expected_provenance = {
                        "workflow": "recorded_replay",
                        "transport": "recorded_replay",
                        "original_transport": provenance.get(
                            "transport", artifact.get("provenance", {}).get("transport", "unknown")
                        ),
                        "provider": provenance["provider"],
                        "model_called": False,
                        "generating_model_called": provenance.get("model_called", False),
                        "snapshot_kind": provenance.get("snapshot_kind", "complete_scenario"),
                        "snapshot_cutoff": provenance.get("snapshot_cutoff")
                        or max(item["timestamp"] for item in artifact["evidence"]),
                        "recorded": True,
                        "artifact_schema_version": captured_source["schema_version"],
                        "artifact_generated_at": captured_source["generated_at"],
                        "original_created_at": provenance.get(
                            "original_created_at", artifact.get("created_at")
                        ),
                        "original_model": provenance.get("original_model"),
                        "original_workflow": provenance.get(
                            "workflow", artifact.get("provenance", {}).get("workflow", "unknown")
                        ),
                        "assessment_source": artifact.get("provenance", {}).get("assessment_source"),
                        "playback_model_calls": 0,
                        "showcase": artifact.get("provenance", {}).get("showcase"),
                        "playback_validation": captured_source["playback_validation"],
                    }
                    fields["provenance"] = row["provenance"] == expected_provenance
                    fields["steps"] = row["steps"] == [
                        {
                            **step,
                            "transport": "recorded_replay",
                            "provider": provenance["provider"],
                            "recorded": True,
                        }
                        for step in artifact["steps"]
                    ]
                    errors = [
                        record
                        for record in caplog.records
                        if record.levelno >= logging.ERROR and record.name.startswith("sqlalchemy.pool")
                    ]
                    leftovers = [
                        task
                        for task in asyncio.all_tasks()
                        if "_terminate_graceful_close" in getattr(task.get_coro(), "__qualname__", "")
                        or "Connection.close" in getattr(task.get_coro(), "__qualname__", "")
                    ]
                    print(
                        json.dumps(
                            {
                                "phase": "current-owned-healthy-pre-ping-disconnect",
                                "backend": backend,
                                "native_query_completed_before_cancel": native_query_completed,
                                "read_ordinal": read_ordinal,
                                "physical_checkedout_before": before,
                                "physical_checkedout_after_recovery": database.engine.pool.checkedout(),
                                "event_active_records": len(active),
                                "live_request_tasks": len(server.server_state.tasks),
                                "live_read_tasks": len(live_reads),
                                "live_nested_close_tasks": len(leftovers),
                                "cleanup_errors": len(errors),
                                "elapsed_seconds": elapsed,
                                "later_http_status": later.status_code,
                                "unusable_driver_reused": bool(reused_unusable),
                                "recorded_fields_equal": fields,
                                "child_cancel": child_cancel,
                                **counts,
                            }
                        ),
                        flush=True,
                    )
                    assert all(fields.values())
                    assert live_reads == set() and database.engine.pool.checkedout() == 0 and active == set()
                    assert not reused_unusable
                    assert elapsed < 3
                    assert errors == [], (
                        "Ordinary owned-stream cancellation must not fail connection termination"
                    )
                    assert leftovers == []
                    assert child_cancel == [{"scope_reason": False, "cancellation_calls": 1}]
                    assert raw_app.state.sse_reads.used == 0
                    assert len(outer_cancel) == 1 and outer_cancel[0][1]
                    assert propagated_cancel == [outer_cancel[0][0]]
                finally:
                    release.set()
                    writer.close()
                    await writer.wait_closed()
                    # Failure containment only: join any orphan created by the baseline.
                    for task in leftovers:
                        task.cancel()
                    if leftovers:
                        await asyncio.wait_for(asyncio.gather(*leftovers, return_exceptions=True), 2)
    finally:
        release.set()
        await database.close()
        for thread in threads.values():
            await asyncio.to_thread(thread.join, 1)
        print(
            json.dumps(
                {
                    "phase": "owned-proof-teardown",
                    "native_driver_threads": len(threads),
                    "live_native_driver_threads": sum(thread.is_alive() for thread in threads.values()),
                    "orphan_containment_cancelled_tasks": len(leftovers),
                    "physical_checkedout": database.engine.pool.checkedout(),
                }
            ),
            flush=True,
        )
        assert all(not thread.is_alive() for thread in threads.values())
        if backend == "postgres":
            assert all(driver.is_closed() for driver in drivers_seen)
