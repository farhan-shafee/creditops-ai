"""Held native work demonstrates retained ownership, not native preemption."""

import asyncio
import json
import logging
import threading
import weakref
from pathlib import Path
from uuid import uuid4

import aiosqlite
import httpx
import pytest
from creditops import investigator
from creditops.db import InvestigationRow
from creditops.main import create_app
from creditops.settings import Settings
from creditops.store import Store
from sqlalchemy import event, text
from test_sse_socket import ROLE, RequestRole, server_for


@pytest.mark.parametrize("phase", ["pre-ping", "acquired-query"])
async def test_held_native_read_outlives_request_deadline_and_service_grace(
    tmp_path, monkeypatch, caplog, phase
):
    database = Store(f"sqlite+aiosqlite:///{(tmp_path / 'held.db').as_posix()}")
    entered, release = threading.Event(), threading.Event()
    threads = {}
    invalid = weakref.WeakSet()
    reused_invalid = []
    counts = {"checkout": 0, "checkin": 0, "invalidation": 0}
    active = set()
    ordinal = 0
    cancellation_counts = []

    def held_native():
        entered.set()
        release.wait()
        return 1

    @event.listens_for(database.engine.sync_engine, "connect")
    def connected(connection, _):
        driver = connection.driver_connection
        threads[id(driver)] = driver._thread

        async def install(raw):
            await raw.create_function("owned_native_gate", 0, held_native)

        connection.run_async(install)

    @event.listens_for(database.engine.sync_engine, "checkout")
    def checkout(connection, record, _):
        counts["checkout"] += 1
        active.add(id(record))
        if connection.driver_connection in invalid:
            reused_invalid.append(True)

    @event.listens_for(database.engine.sync_engine, "checkin")
    def checkin(_connection, record):
        counts["checkin"] += 1
        active.discard(id(record))

    @event.listens_for(database.engine.sync_engine, "invalidate")
    def invalidate(connection, *_):
        counts["invalidation"] += 1
        if connection is not None:
            invalid.add(connection.driver_connection)

    await database.initialize()
    settings = Settings(
        _env_file=None,
        public_demo=True,
        telemetry_mode="persisted",
        replay_dir=Path(__file__).parents[3] / "data" / "showcase",
    )
    session = str(uuid4())
    await database.activate_case(session, "INC-DEMO-001")
    row = await investigator.create_investigation(database, session, "INC-DEMO-001", "REPLAY", settings)
    original_execute = aiosqlite.Cursor.execute

    async def gated_ping(cursor, statement, parameters=None):
        if (
            phase == "pre-ping"
            and ROLE.get()
            and ordinal >= 2
            and statement == "SELECT 1"
            and not entered.is_set()
        ):
            statement = "SELECT owned_native_gate()"
        return await original_execute(cursor, statement, parameters)

    monkeypatch.setattr(aiosqlite.Cursor, "execute", gated_ping)

    class GatedSession(database.sessions.class_):
        async def get(self, entity, ident, **kwargs):
            nonlocal ordinal
            if ROLE.get() and entity is InvestigationRow:
                ordinal += 1
                try:
                    if phase == "acquired-query" and ordinal == 2:
                        await self.execute(text("SELECT owned_native_gate()"))
                    return await super().get(entity, ident, **kwargs)
                except asyncio.CancelledError:
                    cancellation_counts.append(asyncio.current_task().cancelling())
                    raise
            return await super().get(entity, ident, **kwargs)

    database.sessions.class_ = GatedSession
    app = create_app(database, manage_store=False, settings=settings)
    caplog.set_level(logging.ERROR)
    writer = None
    child = None
    try:
        async with server_for(RequestRole(app)) as (server, port):
            try:
                async with httpx.AsyncClient(
                    base_url=f"http://127.0.0.1:{port}", headers={"X-Demo-Session": session}
                ) as client:
                    _, writer = await asyncio.open_connection("127.0.0.1", port)
                    writer.write(
                        f"GET /api/investigations/{row['id']}/events HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Demo-Session: {session}\r\n\r\n".encode()
                    )
                    await writer.drain()
                    assert await asyncio.to_thread(entered.wait, 3)
                    before = database.engine.pool.checkedout()
                    started = asyncio.get_running_loop().time()
                    writer.close()
                    await writer.wait_closed()
                    requests = list(server.server_state.tasks)
                    if requests:
                        _, pending = await asyncio.wait(requests, timeout=3.5)
                        assert not pending, "Request must return without waiting for held native work"
                    elapsed = asyncio.get_running_loop().time() - started
                    owner = app.state.sse_reads
                    assert owner.used == 1, (
                        "A blocked polling read must retain capacity after request completion"
                    )
                    record = owner.records[0]
                    child = record.child
                    assert not child.done() and record.cleanup.pending
                    assert 1.8 <= elapsed < 3.5 and not release.is_set()
                    assert database.engine.pool.checkedout() >= 1
                    assert any(item.message == "sse_cleanup_deadline" for item in caplog.records)
                    shutdown_started = asyncio.get_running_loop().time()
                    assert not await owner.shutdown(grace=None if phase == "pre-ping" else 0.03)
                    shutdown_elapsed = asyncio.get_running_loop().time() - shutdown_started
                    if phase == "pre-ping":
                        assert 4.8 <= shutdown_elapsed < 6.5
                    assert owner.records[0] is record and not child.done()
                    assert any(item.message == "sse_shutdown_incomplete" for item in caplog.records)
                    later = await client.get(f"/api/investigations/{row['id']}")
                    assert later.status_code == 200
                    print(
                        json.dumps(
                            {
                                "phase": phase,
                                "request_elapsed_seconds": elapsed,
                                "physical_before": before,
                                "physical_while_retained": database.engine.pool.checkedout(),
                                "active_event_records": len(active),
                                "retained_slots": owner.used,
                                "child_done": child.done(),
                                **counts,
                            }
                        )
                    )
                    release.set()
                    with pytest.raises(asyncio.CancelledError):
                        await asyncio.wait_for(child, 3)
                    assert cancellation_counts == [1]
                    assert not record.cleanup.pending and owner.used == 0
                    assert database.engine.pool.checkedout() == 0 and not active
                    assert not reused_invalid
                    assert not any(
                        item.levelno >= logging.ERROR and item.name.startswith("sqlalchemy.pool")
                        for item in caplog.records
                    )
                    assert not [
                        task
                        for task in asyncio.all_tasks()
                        if "_terminate_graceful_close" in getattr(task.get_coro(), "__qualname__", "")
                    ]
                    assert (await client.get(f"/api/investigations/{row['id']}")).status_code == 200
            finally:
                release.set()
                outstanding = set(server.server_state.tasks)
                outstanding.update(
                    task
                    for task in asyncio.all_tasks()
                    if "_terminate_graceful_close" in getattr(task.get_coro(), "__qualname__", "")
                )
                if outstanding:
                    _, pending = await asyncio.wait(outstanding, timeout=3)
                    assert not pending, "Released fixture work must join before server teardown"
    finally:
        release.set()
        if writer:
            writer.close()
            await writer.wait_closed()
        if child:
            await asyncio.wait_for(asyncio.gather(child, return_exceptions=True), 3)
        await database.close()
        for thread in threads.values():
            await asyncio.to_thread(thread.join, 1)
        print(
            json.dumps(
                {
                    "phase": phase,
                    "stage": "teardown",
                    "native_threads_alive": sum(thread.is_alive() for thread in threads.values()),
                    "physical_checkedout": database.engine.pool.checkedout(),
                }
            )
        )
        assert all(not thread.is_alive() for thread in threads.values())


@pytest.mark.parametrize("phase", ["pre-ping", "acquired-query"])
async def test_public_raw_close_failure_retains_receipt_and_retires_driver(
    tmp_path, monkeypatch, caplog, phase
):
    database = Store(f"sqlite+aiosqlite:///{(tmp_path / 'failed-close.db').as_posix()}")
    await database.initialize()
    session = str(uuid4())
    await database.activate_case(session, "INC-DEMO-001")
    settings = Settings(
        _env_file=None,
        public_demo=True,
        telemetry_mode="persisted",
        replay_dir=Path(__file__).parents[3] / "data" / "showcase",
    )
    row = await investigator.create_investigation(database, session, "INC-DEMO-001", "REPLAY", settings)
    app = create_app(database, manage_store=False, settings=settings)
    owner = app.state.sse_reads
    ready, release = asyncio.Event(), asyncio.Event()
    original_execute = aiosqlite.Cursor.execute
    original_close = aiosqlite.Connection.close
    failed_drivers = set()
    invalid_drivers = weakref.WeakSet()
    reused = []

    @event.listens_for(database.engine.sync_engine, "invalidate")
    def invalidated(connection, *_):
        if connection is not None:
            invalid_drivers.add(connection.driver_connection)

    @event.listens_for(database.engine.sync_engine, "checkout")
    def checked_out(connection, *_):
        if connection.driver_connection in invalid_drivers:
            reused.append(True)

    async def schedule_query(cursor, statement, parameters=None):
        value = await original_execute(cursor, statement, parameters)
        match = (
            statement == "SELECT 1"
            if phase == "pre-ping"
            else statement.startswith("SELECT") and statement != "SELECT 1"
        )
        if ROLE.get() and match and not ready.is_set():
            ready.set()
            await release.wait()
        return value

    async def fail_owned_close(driver):
        if ROLE.get():
            failed_drivers.add(driver)
            raise RuntimeError("injected public raw close failure")
        return await original_close(driver)

    monkeypatch.setattr(aiosqlite.Cursor, "execute", schedule_query)
    monkeypatch.setattr(aiosqlite.Connection, "close", fail_owned_close)
    token = ROLE.set(True)
    request = asyncio.create_task(owner.read(session, row["id"]))
    ROLE.reset(token)
    caplog.set_level(logging.ERROR)
    record = None
    try:
        await asyncio.wait_for(ready.wait(), 1)
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(request, 3)
        assert owner.used == 1
        record = owner.records[0]
        assert record.child.done() and record.cleanup.pending
        assert failed_drivers and failed_drivers <= record.cleanup._resources
        assert len(record.cleanup._attempted_drivers) == 1
        assert any(
            item.message == "sse_cleanup_failed" and item.error_type == "RuntimeError"
            for item in caplog.records
        )
        assert not await owner.shutdown(grace=0)
        assert database.engine.pool.checkedout() == 0
        assert await database.get_investigation(session, row["id"]) is not None
        assert not reused
    finally:
        release.set()
        if not request.done():
            _, pending = await asyncio.wait({request}, timeout=3)
            assert not pending
        if record and not record.child.done():
            _, pending = await asyncio.wait({record.child}, timeout=3)
            assert not pending
        # Injected-error containment acknowledges physical closure only in this test.
        # The service conservatively retains its failed receipt/capacity.
        for driver in failed_drivers:
            await original_close(driver)
            await asyncio.to_thread(driver._thread.join, 1)
            assert not driver._thread.is_alive()
        await database.close()
    assert owner.used == 1 and record.cleanup.pending
