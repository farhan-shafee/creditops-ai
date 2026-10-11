"""Real pooled database ownership and loopback disconnect regressions.

Instrumentation and barriers are test-only; no SQL, credentials or evidence payloads are logged.
"""

import asyncio
import json
import os
import socket
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
import pytest
import uvicorn
from creditops import store as store_module
from creditops.db import IncidentRow
from creditops.main import create_app
from creditops.settings import Settings
from creditops.store import Store
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class PoolCounts:
    def __init__(self, engine):
        self.checkout = self.checkin = self.invalidation = self.active = self.peak = 0
        self.idle = asyncio.Event()
        self.idle.set()
        event.listen(engine.sync_engine, "checkout", self.checked_out)
        event.listen(engine.sync_engine, "checkin", self.checked_in)
        event.listen(engine.sync_engine, "invalidate", self.invalidated)

    def checked_out(self, *_):
        self.checkout += 1
        self.active += 1
        self.peak = max(self.peak, self.active)
        self.idle.clear()

    def checked_in(self, *_):
        self.checkin += 1
        self.active -= 1
        if self.active == 0:
            self.idle.set()

    def invalidated(self, *_):
        self.invalidation += 1

    def receipt(self):
        return {name: getattr(self, name) for name in ("checkout", "checkin", "invalidation", "active", "peak")}


@asynccontextmanager
async def pooled_store(tmp_path, monkeypatch, *, backend="sqlite", size=None, overflow=None):
    url = os.environ["CREDITOPS_TEST_DATABASE_URL"] if backend == "postgres" else f"sqlite+aiosqlite:///{(tmp_path / 'pooled.db').as_posix()}"
    owner = str(uuid4())
    seeded = Store(url)
    await seeded.initialize()
    await seeded.activate_case(owner, "INC-DEMO-001")
    await seeded.close()
    create_engine = store_module.create_async_engine

    def test_engine(database_url, **options):
        # Only the focused fixture changes pool bounds/timeouts; application defaults stay intact.
        options["pool_timeout"] = 0.35
        if size is not None:
            options.update(pool_size=size, max_overflow=overflow)
        return create_engine(database_url, **options)

    monkeypatch.setattr(store_module, "create_async_engine", test_engine)
    database = Store(url)
    counts = PoolCounts(database.engine)
    try:
        yield database, owner, counts
    finally:
        await database.close()


@pytest.fixture(params=["sqlite", pytest.param("postgres", marks=pytest.mark.skipif(not os.getenv("CREDITOPS_TEST_DATABASE_URL"), reason="Disposable local PostgreSQL URL not configured"))])
def lifecycle_backend(request):
    return request.param


@pytest.mark.parametrize("size,overflow,readers", [(1, 0, 1), (None, None, 15)], ids=["one-connection", "default-five-plus-ten"])
async def test_incident_read_releases_checkout_before_composed_reads(tmp_path, monkeypatch, lifecycle_backend, size, overflow, readers):
    """Moving business_impact back inside the outer session must starve this real pool."""
    async with pooled_store(tmp_path, monkeypatch, backend=lifecycle_backend, size=size, overflow=overflow) as (database, owner, counts):
        barrier = asyncio.Barrier(readers)
        boundary_occupancy = []
        business_impact = database.business_impact

        async def synchronized_impact(*args, **kwargs):
            boundary_occupancy.append(counts.active)
            await asyncio.wait_for(barrier.wait(), 5)
            return await business_impact(*args, **kwargs)

        monkeypatch.setattr(database, "business_impact", synchronized_impact)
        tasks = [asyncio.create_task(database.get_incident(owner, "INC-DEMO-001")) for _ in range(readers)]
        try:
            results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 6)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.wait_for(counts.idle.wait(), 2)
        # An independent checkout afterwards separates starvation from retained leaked connections.
        assert await asyncio.wait_for(database.ping(), 2)
        print(json.dumps({"phase": "composed-read", "readers": readers, "boundary_occupancy": boundary_occupancy, **counts.receipt()}))
        failures = [type(result).__name__ for result in results if isinstance(result, BaseException)]
        assert failures == [], f"Composed reads starved the pool: {failures}; boundary={boundary_occupancy}"
        assert all(result.id == "INC-DEMO-001" for result in results)
        assert counts.active == 0
        assert counts.checkout == counts.checkin
        assert counts.invalidation == 0


@asynccontextmanager
async def loopback_server(app):
    """Use a real HTTP socket, with explicit startup and bounded owned task teardown."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.setblocking(False)
    port = listener.getsockname()[1]
    ready = asyncio.Event()

    class ReadyServer(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets)
            ready.set()

    server = ReadyServer(uvicorn.Config(app, host="127.0.0.1", port=port, lifespan="off", log_config=None, timeout_graceful_shutdown=2))
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        await asyncio.wait_for(ready.wait(), 3)
        yield server, port
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(task, 4)
        finally:
            listener.close()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


async def test_loopback_disconnect_keeps_read_owned_until_completion(tmp_path, monkeypatch, lifecycle_backend):
    """A disconnect retains active work, but ordinary completion must return its checkout."""
    async with pooled_store(tmp_path, monkeypatch, backend=lifecycle_backend, size=1, overflow=0) as (database, owner, counts):
        entered, release, completed = asyncio.Event(), asyncio.Event(), asyncio.Event()
        active_readers = set()
        cancelled = []

        class PausedRead(AsyncSession):
            async def get(self, entity, ident, **kwargs):
                result = await super().get(entity, ident, **kwargs)
                if entity is IncidentRow and not release.is_set():
                    active_readers.add(asyncio.current_task())
                    entered.set()
                    try:
                        await release.wait()
                    except asyncio.CancelledError:
                        cancelled.append(True)
                        raise
                    finally:
                        active_readers.discard(asyncio.current_task())
                        completed.set()
                return result

        database.sessions = async_sessionmaker(database.engine, class_=PausedRead, expire_on_commit=False)
        app = create_app(database, manage_store=False, settings=Settings(_env_file=None, public_demo=True))
        async with loopback_server(app) as (server, port):
            _, writer = await asyncio.open_connection("127.0.0.1", port)
            try:
                writer.write(f"GET /api/incidents/INC-DEMO-001 HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Demo-Session: {owner}\r\n\r\n".encode())
                await writer.drain()
                await asyncio.wait_for(entered.wait(), 2)
                assert counts.active == 1
                writer.close()
                await writer.wait_closed()
                # Uvicorn signals disconnect through receive; it does not cancel the handler.
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(completed.wait(), 0.15)
                assert counts.active == 1
                assert len(active_readers) == 1
                release.set()
                await asyncio.wait_for(completed.wait(), 1)
                await asyncio.wait_for(counts.idle.wait(), 1)
                assert active_readers == set()
                assert cancelled == []
                assert counts.checkout == counts.checkin
                assert counts.invalidation == 0
                release.set()
                async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
                    response = await client.get("/api/incidents/INC-DEMO-001", headers={"X-Demo-Session": owner})
                assert response.status_code == 200
                assert response.json()["id"] == "INC-DEMO-001"
                print(json.dumps({"phase": "socket-disconnect", "live_read_tasks": len(active_readers), "cancelled_reads": len(cancelled), **counts.receipt()}))
            finally:
                release.set()
                writer.close()
                await writer.wait_closed()
                # Even on RED the test owns and joins outstanding server requests.
                pending = list(server.server_state.tasks)
                if pending:
                    await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), 3)

async def test_console_request_pattern_completes_with_default_pool(tmp_path, monkeypatch, lifecycle_backend):
    """Concurrent real overview/incidents/topology requests must not hold all outer checkouts."""
    async with pooled_store(tmp_path, monkeypatch, backend=lifecycle_backend) as (database, owner, counts):
        barrier = asyncio.Barrier(15)
        arrived = 0
        business_impact = database.business_impact

        async def synchronized_impact(*args, **kwargs):
            nonlocal arrived
            arrived += 1
            if arrived <= 15:
                await asyncio.wait_for(barrier.wait(), 5)
            return await business_impact(*args, **kwargs)

        monkeypatch.setattr(database, "business_impact", synchronized_impact)
        app = create_app(database, manage_store=False, settings=Settings(_env_file=None, public_demo=True))
        async with loopback_server(app) as (_, port), httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=6) as client:
            paths = ["/api/overview", "/api/incidents", "/api/services/topology"] * 5
            responses = await asyncio.wait_for(asyncio.gather(*(client.get(path, headers={"X-Demo-Session": owner}) for path in paths)), 8)
            await asyncio.wait_for(counts.idle.wait(), 2)
            later = await client.get("/api/incidents", headers={"X-Demo-Session": owner})
            assert later.status_code == 200
            assert later.json()[0]["id"] == "INC-DEMO-001"
            statuses = [response.status_code for response in responses]
            print(json.dumps({"phase": "console-request-pattern", "statuses": statuses, **counts.receipt()}))
            assert statuses == [200] * 15
            assert counts.active == 0
            assert counts.checkout == counts.checkin
            assert counts.invalidation == 0


async def test_cancelled_read_joins_session_cleanup_before_later_read(tmp_path, monkeypatch, lifecycle_backend):
    """Explicit cancellation must propagate and join real session cleanup, without invalidation."""
    async with pooled_store(tmp_path, monkeypatch, backend=lifecycle_backend, size=1, overflow=0) as (database, owner, counts):
        entered, release = asyncio.Event(), asyncio.Event()

        class PausedRead(AsyncSession):
            async def get(self, entity, ident, **kwargs):
                result = await super().get(entity, ident, **kwargs)
                if entity is IncidentRow and not release.is_set():
                    entered.set()
                    await release.wait()
                return result

        database.sessions = async_sessionmaker(database.engine, class_=PausedRead, expire_on_commit=False)
        task = asyncio.create_task(database.get_incident(owner, "INC-DEMO-001"))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            assert counts.active == 1
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 2)
            await asyncio.wait_for(counts.idle.wait(), 1)
            release.set()
            later = await asyncio.wait_for(database.get_incident(owner, "INC-DEMO-001"), 2)
            assert later.id == "INC-DEMO-001"
            assert counts.active == 0
            assert counts.checkout == counts.checkin
            assert counts.invalidation == 0
            print(json.dumps({"phase": "explicit-cancellation", "task_done": task.done(), **counts.receipt()}))
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_released_read_preserves_frozen_cutoff_isolation_and_reset(tmp_path, monkeypatch, lifecycle_backend):
    """A released outer checkout must keep its original cutoff and independent reset recheck."""
    async with pooled_store(tmp_path, monkeypatch, backend=lifecycle_backend, size=1, overflow=0) as (database, owner, counts):
        other = str(uuid4())
        assert await database.get_incident(other, "INC-DEMO-001") is None
        cutoff_seen = []
        business_impact = database.business_impact

        async def frozen_impact(session_id, incident_id, as_of=None):
            cutoff_seen.append(as_of)
            assert counts.active == 0
            return await business_impact(session_id, incident_id, as_of=as_of)

        monkeypatch.setattr(database, "business_impact", frozen_impact)
        incident = await database.get_incident(owner, "INC-DEMO-001", as_of="2026-10-09T14:00:12Z")
        assert incident.simulated_elapsed_seconds == 12
        assert cutoff_seen == ["2026-10-09T14:00:12+00:00"]
        assert all(item.timestamp <= "2026-10-09T14:00:12Z" for item in incident.timeline)
        impact = await business_impact(owner, "INC-DEMO-001", as_of="2026-10-09T14:00:12Z")
        assert impact.as_of == "2026-10-09T14:00:12Z"
        assert incident.client_impact == impact.summary

        async def reset_before_impact(session_id, incident_id, as_of=None):
            await database.reset_scenario(owner, "kafka-pricing-lag")
            return await business_impact(session_id, incident_id, as_of=as_of)

        monkeypatch.setattr(database, "business_impact", reset_before_impact)
        already_materialized = await database.get_incident(owner, "INC-DEMO-001", as_of="2026-10-09T14:00:12Z")
        assert already_materialized.id == "INC-DEMO-001"
        assert already_materialized.simulated_elapsed_seconds == 12
        assert await database.get_incident(owner, "INC-DEMO-001") is None
        assert await database.list_incidents(owner) == []
        assert await database.list_incidents(other) == []
        assert counts.active == 0
        assert counts.checkout == counts.checkin

async def test_driver_inflight_cancellation_returns_checkout_before_later_ping(tmp_path, monkeypatch, lifecycle_backend):
    """Cancellation inside a real driver await must propagate and join its owned cleanup."""
    import threading

    from sqlalchemy import text

    async with pooled_store(tmp_path, monkeypatch, backend=lifecycle_backend, size=1, overflow=0) as (database, _, counts):
        entered = threading.Event()
        release = threading.Event()
        control = None
        control_connection = None
        lock_key = uuid4().int % 1000000 + 1
        if lifecycle_backend == "sqlite":
            def driver_gate():
                entered.set()
                if not release.wait(4):
                    raise RuntimeError("Owned test driver gate deadline expired")
                return 1

            @event.listens_for(database.engine.sync_engine, "connect")
            def install_gate(connection, _):
                connection.create_function("lifecycle_test_gate", 0, driver_gate)

            replacement = "SELECT lifecycle_test_gate()"
        else:
            control = store_module.create_async_engine(os.environ["CREDITOPS_TEST_DATABASE_URL"])
            control_connection = await control.connect()
            await control_connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_key})
            replacement = f"SELECT pg_advisory_lock({lock_key})"

        @event.listens_for(database.engine.sync_engine, "before_cursor_execute", retval=True)
        def gate_ping(_, __, statement, parameters, ___, ____):
            return (replacement, parameters) if statement == "SELECT 1" and not release.is_set() else (statement, parameters)

        task = asyncio.create_task(database.ping())
        try:
            if lifecycle_backend == "sqlite":
                assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 2), 3)
            else:
                # Observe the actual server-side wait, not a callback before the query starts.
                async with asyncio.timeout(2):
                    while not await control_connection.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND granted=false AND objid=:key)"), {"key": lock_key}):
                        pass
            assert counts.active == 1
            task.cancel()
            # SQLite cannot preempt a Python UDF. Release the controlled driver work
            # before joining cancellation/termination; retained occupancy until then is active cleanup.
            release.set()
            if control_connection is not None:
                await control_connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 3)
            await asyncio.wait_for(counts.idle.wait(), 2)
            assert await asyncio.wait_for(database.ping(), 2)
            assert counts.active == 0
            assert counts.checkout == counts.checkin
            print(json.dumps({"phase": "driver-inflight-cancellation", "backend": lifecycle_backend, "task_done": task.done(), **counts.receipt()}))
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if control_connection is not None:
                await control_connection.close()
            if control is not None:
                await control.dispose()

async def test_sse_disconnect_during_driver_read_joins_cleanup_without_errors(tmp_path, monkeypatch, caplog):
    """Actual streaming disconnect must clean its in-flight DB read under AnyIO cancellation."""
    import logging
    import threading

    from creditops.db import InvestigationRow

    async with pooled_store(tmp_path, monkeypatch, size=1, overflow=0) as (database, owner, counts):
        payload = {"id": "INV-LIFECYCLE", "incident_id": "INC-DEMO-001", "mode": "REPLAY", "status": "running", "provider": "recorded", "created_at": "2026-10-09T14:00:00Z", "steps": [], "evidence": [], "assessment": None, "error": None, "usage": {}}
        await database.save_investigation(owner, payload)
        # Install the UDF on a fresh physical connection rather than altering app data.
        await database.engine.dispose()
        entered, release, driver_finished = threading.Event(), threading.Event(), threading.Event()
        drivers = []
        session_close_tasks = set()
        cancelled = asyncio.Event()
        read_calls = 0
        read_tasks = set()
        cancellation_messages = []

        def driver_gate():
            entered.set()
            try:
                if not release.wait(4):
                    print(json.dumps({"phase": "sse-driver-gate-deadline", "live_read_tasks": len(read_tasks), "live_session_close_tasks": len(session_close_tasks), **counts.receipt()}), flush=True)
                    raise RuntimeError("Owned SSE test driver gate deadline expired")
                return 1
            finally:
                driver_finished.set()

        @event.listens_for(database.engine.sync_engine, "connect")
        def install_gate(connection, _):
            drivers.append(connection.driver_connection)
            connection.create_function("lifecycle_sse_gate", 0, driver_gate)

        @event.listens_for(database.engine.sync_engine, "before_cursor_execute", retval=True)
        def gate_stream_read(_, __, statement, parameters, ___, ____):
            if read_calls == 2 and not release.is_set() and "FROM investigations" in statement:
                return "SELECT lifecycle_sse_gate()", ()
            return statement, parameters

        class ObservedRead(database.sessions.class_):
            async def get(self, entity, ident, **kwargs):
                nonlocal read_calls
                if entity is not InvestigationRow:
                    return await super().get(entity, ident, **kwargs)
                read_calls += 1
                task = asyncio.current_task()
                read_tasks.add(task)
                try:
                    return await super().get(entity, ident, **kwargs)
                except asyncio.CancelledError as error:
                    print(json.dumps({"phase": "sse-driver-cancel-observed"}), flush=True)
                    cancellation_messages.append(str(error))
                    cancelled.set()
                    raise
                finally:
                    read_tasks.discard(task)

            async def __aexit__(self, *args):
                session_close_tasks.add(asyncio.current_task())
                try:
                    return await super().__aexit__(*args)
                finally:
                    session_close_tasks.discard(asyncio.current_task())

        database.sessions = async_sessionmaker(database.engine, class_=ObservedRead, expire_on_commit=False)
        app = create_app(database, manage_store=False, settings=Settings(_env_file=None, public_demo=True))
        caplog.set_level(logging.ERROR, logger="sqlalchemy.pool")
        async with loopback_server(app) as (server, port):
            _, writer = await asyncio.open_connection("127.0.0.1", port)
            try:
                writer.write(f"GET /api/investigations/INV-LIFECYCLE/events HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Demo-Session: {owner}\r\n\r\n".encode())
                await writer.drain()
                assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 2), 3)
                assert counts.active == 1
                disconnect_started = asyncio.get_running_loop().time()
                writer.close()
                await writer.wait_closed()
                await asyncio.wait_for(cancelled.wait(), 3)
                pending = list(server.server_state.tasks)
                if pending:
                    await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), 3)
                await asyncio.wait_for(counts.idle.wait(), 2)
                assert read_tasks == set()
                assert session_close_tasks == set()
                assert 2 <= asyncio.get_running_loop().time() - disconnect_started < 3
                assert not release.is_set() and not driver_finished.is_set()
                assert drivers[0]._thread.is_alive()
                cleanup_tasks = [task for task in asyncio.all_tasks() if "Connection.close" in getattr(task.get_coro(), "__qualname__", "") or "_terminate_graceful_close" in getattr(task.get_coro(), "__qualname__", "") or "_run_to_completion" in getattr(task.get_coro(), "__qualname__", "")]
                assert cleanup_tasks == []
                assert any("cancel scope" in message for message in cancellation_messages)
                print(json.dumps({"phase": "sse-request-cleanup-before-driver-release", "live_read_tasks": len(read_tasks), "live_session_close_tasks": len(session_close_tasks), "live_nested_close_tasks": len(cleanup_tasks), "active_driver_threads": 1, **counts.receipt()}))
                release.set()
                assert await asyncio.wait_for(asyncio.to_thread(driver_finished.wait, 1), 2)
                await asyncio.wait_for(asyncio.to_thread(drivers[0]._thread.join, 1), 2)
                assert not drivers[0]._thread.is_alive()
                async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
                    later = await client.get("/api/investigations/INV-LIFECYCLE", headers={"X-Demo-Session": owner})
                assert later.status_code == 200
                assert later.json()["id"] == "INV-LIFECYCLE"
                errors = [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR and record.name.startswith("sqlalchemy.pool")]
                print(json.dumps({"phase": "sse-driver-disconnect", "live_read_tasks": len(read_tasks), "level_cancelled_reads": len(cancellation_messages), "cleanup_errors": len(errors), **counts.receipt()}))
                assert counts.active == 0
                assert counts.checkout == counts.checkin
                assert errors == []
            finally:
                release.set()
                writer.close()
                await writer.wait_closed()
                pending = list(server.server_state.tasks)
                if pending:
                    await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), 3)
async def test_level_cancelled_transaction_rolls_back_before_later_reset(tmp_path, monkeypatch, lifecycle_backend):
    """A cancelled reset transaction must roll back its real deletion and join all cleanup."""
    from anyio import create_task_group
    from sqlalchemy.sql.dml import Delete

    async with pooled_store(tmp_path, monkeypatch, backend=lifecycle_backend, size=1, overflow=0) as (database, owner, counts):
        entered = asyncio.Event()
        completed = asyncio.Event()
        observed = []

        class PausedWrite(database.sessions.class_):
            async def execute(self, statement, *args, **kwargs):
                result = await super().execute(statement, *args, **kwargs)
                if isinstance(statement, Delete) and not entered.is_set():
                    entered.set()
                    await asyncio.Event().wait()
                return result

        database.sessions.class_ = PausedWrite

        async def reset():
            try:
                await database.reset_scenario(owner, "kafka-pricing-lag")
            except asyncio.CancelledError as error:
                observed.append(error)
                raise
            finally:
                completed.set()

        async with create_task_group() as tasks:
            tasks.start_soon(reset)
            await asyncio.wait_for(entered.wait(), 2)
            assert counts.active == 1
            tasks.cancel_scope.cancel()
        assert completed.is_set()
        assert len(observed) == 1 and "cancel scope" in str(observed[0])
        assert counts.active == 0
        assert counts.checkout == counts.checkin
        assert counts.invalidation == 0
        # The cancelled deletion remains rolled back; the same independent reset still works.
        incident = await asyncio.wait_for(database.get_incident(owner, "INC-DEMO-001"), 2)
        assert incident.id == "INC-DEMO-001"
        await asyncio.wait_for(database.reset_scenario(owner, "kafka-pricing-lag"), 2)
        assert await database.get_incident(owner, "INC-DEMO-001") is None
        print(json.dumps({"phase": "level-cancelled-transaction", "original_cancellation": True, **counts.receipt()}))


@pytest.mark.parametrize("body_error", ["cancel", "value-error"])
async def test_session_cleanup_deadline_preserves_original_exception(tmp_path, monkeypatch, body_error):
    """A real rollback cleanup deadline must preserve the caller's original exception."""
    from anyio import CancelScope, lowlevel

    async with pooled_store(tmp_path, monkeypatch, size=1, overflow=0) as (database, owner, counts):
        await database.engine.dispose()
        entered, release = asyncio.Event(), asyncio.Event()

        @event.listens_for(database.engine.sync_engine, "connect")
        def gate_rollback(connection, _):
            driver = connection.driver_connection
            original = driver.rollback

            async def rollback():
                if not release.is_set():
                    entered.set()
                    await release.wait()
                await original()

            driver.rollback = rollback

        observed = []
        try:
            with CancelScope() as scope:
                try:
                    async with database.sessions() as session:
                        assert await session.get(IncidentRow, "INC-DEMO-001") is not None
                        if body_error == "cancel":
                            scope.cancel()
                            await lowlevel.checkpoint()
                        raise ValueError("Original body failure")
                except BaseException as error:
                    observed.append(error)
                    raise
        except ValueError as error:
            assert body_error == "value-error" and str(error) == "Original body failure"
        finally:
            release.set()
        assert entered.is_set()
        assert len(observed) == 1
        if body_error == "cancel":
            assert isinstance(observed[0], asyncio.CancelledError)
            assert "cancel scope" in str(observed[0])
        else:
            assert isinstance(observed[0], ValueError)
        assert counts.active == 0
        assert counts.checkout == counts.checkin
        assert await asyncio.wait_for(database.ping(), 2)
        print(json.dumps({"phase": "session-cleanup-deadline", "original_exception": body_error, **counts.receipt()}))
@pytest.mark.skipif(not os.getenv("CREDITOPS_TEST_DATABASE_URL"), reason="Disposable local PostgreSQL URL not configured")
async def test_postgres_sse_disconnect_cancels_real_locked_query_and_closes(tmp_path, monkeypatch, caplog):
    """Actual PostgreSQL SSE disconnect cancels a server-confirmed advisory-lock wait."""
    import logging

    from creditops.db import InvestigationRow
    from sqlalchemy import text

    async with pooled_store(tmp_path, monkeypatch, backend="postgres", size=1, overflow=0) as (database, owner, counts):
        payload = {"id": "INV-PG-LIFECYCLE", "incident_id": "INC-DEMO-001", "mode": "REPLAY", "status": "running", "provider": "recorded", "created_at": "2026-10-09T14:00:00Z", "steps": [], "evidence": [], "assessment": None, "error": None, "usage": {}}
        await database.save_investigation(owner, payload)
        await database.engine.dispose()
        control = store_module.create_async_engine(os.environ["CREDITOPS_TEST_DATABASE_URL"])
        key = uuid4().int % 1000000 + 1
        cancelled = asyncio.Event()
        observed, drivers = [], []
        read_calls = 0

        @event.listens_for(database.engine.sync_engine, "connect")
        def observe_driver(connection, _):
            drivers.append(connection.driver_connection)

        @event.listens_for(database.engine.sync_engine, "before_cursor_execute", retval=True)
        def gate_stream_read(_, __, statement, parameters, ___, ____):
            return (f"SELECT pg_advisory_lock({key})", ()) if read_calls == 2 and "FROM investigations" in statement else (statement, parameters)

        class ObservedRead(database.sessions.class_):
            async def get(self, entity, ident, **kwargs):
                nonlocal read_calls
                if entity is InvestigationRow:
                    read_calls += 1
                try:
                    return await super().get(entity, ident, **kwargs)
                except asyncio.CancelledError as error:
                    observed.append(error)
                    cancelled.set()
                    raise

        database.sessions.class_ = ObservedRead
        app = create_app(database, manage_store=False, settings=Settings(_env_file=None, public_demo=True))
        caplog.set_level(logging.ERROR, logger="sqlalchemy.pool")
        try:
            async with control.connect() as connection:
                await connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": key})
                try:
                    async with loopback_server(app) as (server, port):
                        _, writer = await asyncio.open_connection("127.0.0.1", port)
                        try:
                            writer.write(f"GET /api/investigations/INV-PG-LIFECYCLE/events HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Demo-Session: {owner}\r\n\r\n".encode())
                            await writer.drain()
                            async with asyncio.timeout(2):
                                while not await connection.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND granted=false AND objid=:key)"), {"key": key}):
                                    pass
                            assert counts.active == 1
                            writer.close()
                            await writer.wait_closed()
                            await asyncio.wait_for(cancelled.wait(), 3)
                            pending = list(server.server_state.tasks)
                            if pending:
                                await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), 3)
                            assert len(observed) == 1 and "cancel scope" in str(observed[0])
                            assert drivers[0].is_closed()
                            assert counts.active == 0 and counts.checkout == counts.checkin
                            assert counts.invalidation == 1
                            assert not await connection.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND granted=false AND objid=:key)"), {"key": key})
                            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
                                later = await client.get("/api/investigations/INV-PG-LIFECYCLE", headers={"X-Demo-Session": owner})
                            assert later.status_code == 200 and later.json()["id"] == "INV-PG-LIFECYCLE"
                            errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
                            assert errors == []
                            print(json.dumps({"phase": "postgres-sse-driver-disconnect", "original_level_cancellation": True, "cancelled_driver_closed": drivers[0].is_closed(), "cleanup_errors": len(errors), **counts.receipt()}))
                        finally:
                            writer.close()
                            await writer.wait_closed()
                            pending = list(server.server_state.tasks)
                            if pending:
                                await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), 3)
                finally:
                    await connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
        finally:
            await control.dispose()