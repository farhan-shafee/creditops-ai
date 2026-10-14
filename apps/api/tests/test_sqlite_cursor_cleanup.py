"""Real cursor finalization at acquired SSE-query cancellation boundaries."""

import asyncio
import copy
import gc
import json
import os
import sqlite3
import weakref
from pathlib import Path
from uuid import uuid4

import aiosqlite
import pytest
from creditops import store as store_module
from creditops.investigator import create_investigation, read_replay_artifact
from creditops.main import create_app
from creditops.settings import PROJECT_ROOT, Settings
from creditops.sse_reads import PollingReadOwner, PollingUnavailable
from creditops.store import Store
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from test_read_lifecycle import loopback_server


def file_locks(path):
    """Test-only kernel metadata: no SQL parameters or session capabilities."""
    if not Path('/proc/locks').exists():
        return None
    identity = path.stat()
    device_inode = f'{os.major(identity.st_dev):02x}:{os.minor(identity.st_dev):02x}:{identity.st_ino}'
    rows = []
    for line in Path('/proc/locks').read_text().splitlines():
        fields = line.split()
        if len(fields) > 7 and fields[5] == device_inode:
            rows.append({'access': fields[3], 'pid': fields[4], 'start': fields[6], 'end': fields[7]})
    return rows


async def prepared_store(tmp_path):
    path = tmp_path / 'cursor.db'
    database = Store(f'sqlite+aiosqlite:///{path.as_posix()}')
    await database.initialize()
    session = str(uuid4())
    await database.activate_case(session, 'INC-DEMO-001')
    row = await create_investigation(database, session, 'INC-DEMO-001', 'REPLAY', Settings(_env_file=None))
    complete = copy.deepcopy(read_replay_artifact('INC-DEMO-001', PROJECT_ROOT / 'data/showcase')['investigation'])
    complete.update(id=row['id'], mode='REPLAY')
    return database, session, row, complete, path


class CursorBoundary:
    """Own barriers and public error-cursor reference until measurement finishes.

    Reference retention proves finalization cannot depend on garbage collection.
    It is an observation fixture, not evidence of the historical CI lock owner.
    """

    def __init__(self, database, monkeypatch, phase):
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = 0
        self.retained = []
        self.cursor = None
        self.closed = []
        execute = aiosqlite.Cursor.execute
        close = aiosqlite.Cursor.close

        async def observe_execute(cursor, statement, *args, **kwargs):
            target = store_module._POLLING_CLEANUP.get() is not None and 'FROM investigations' in statement
            if target:
                self.cursor = weakref.ref(cursor)
                if phase == 'before_execute':
                    await pause()
            result = await execute(cursor, statement, *args, **kwargs)
            if target and phase == 'after_execute':
                await pause()
            return result

        async def pause():
            self.entered.set()
            try:
                await self.release.wait()
            except asyncio.CancelledError:
                self.cancelled += 1
                raise

        async def observe_close(cursor):
            result = await close(cursor)
            if self.cursor is not None and self.cursor() is cursor:
                self.closed.append('acknowledged')
            return result

        monkeypatch.setattr(aiosqlite.Cursor, 'execute', observe_execute)
        monkeypatch.setattr(aiosqlite.Cursor, 'close', observe_close)
        if phase == 'after_buffering':
            original = database.get_investigation

            async def after_buffering(*args, **kwargs):
                result = await original(*args, **kwargs)
                if store_module._POLLING_CLEANUP.get() is not None:
                    await pause()
                return result

            monkeypatch.setattr(database, 'get_investigation', after_buffering)

        def retain_error(context):
            execution = context.execution_context
            cursor = getattr(execution, 'cursor', None) if execution is not None else None
            if isinstance(context.original_exception, asyncio.CancelledError) and cursor is not None:
                self.retained.append(cursor)

        event.listen(database.engine.sync_engine, 'handle_error', retain_error)

    def release_observation(self):
        self.retained.clear()
        gc.collect()


async def write_and_recover(database, session, row, complete, path, boundary):
    writer = asyncio.create_task(database.save_investigation(session, complete))
    try:
        done, _ = await asyncio.wait({writer}, timeout=1)
        receipt = {'writer_completed_before_reference_release': writer in done, 'cursor_close_acknowledgements': len(boundary.closed), 'locks': file_locks(path)}
    finally:
        boundary.release_observation()
        # A red run still releases the fixture's exact reference and joins work.
        await asyncio.wait_for(writer, 4)
    assert receipt['writer_completed_before_reference_release'], f'Replay commit blocked by cancelled read cursor: {receipt}'
    assert (await database.get_investigation(session, row['id'])) == complete
    assert (await database.get_incident(session, 'INC-DEMO-001')).id == 'INC-DEMO-001'
    other_session = str(uuid4())
    assert await database.get_investigation(other_session, row['id']) is None
    assert await database.list_incidents(other_session) == []
    await database.reset_scenario(session, 'kafka-pricing-lag')
    assert await database.get_investigation(session, row['id']) is None
    assert await database.get_incident(session, 'INC-DEMO-001') is None
    await database.run_scenario(session, 'kafka-pricing-lag')
    assert (await database.get_incident(session, 'INC-DEMO-001')).id == 'INC-DEMO-001'
    assert database.engine.sync_engine.pool.checkedout() == 0
    return receipt


@pytest.mark.parametrize('phase', ['before_execute', 'after_execute', 'after_buffering'])
async def test_poll_cancellation_finalizes_cursor_before_replay_commit(tmp_path, monkeypatch, phase):
    database, session, row, complete, path = await prepared_store(tmp_path)
    owner = PollingReadOwner(database)
    boundary = CursorBoundary(database, monkeypatch, phase)
    reservation = owner.reserve()
    task = asyncio.create_task(owner.read(session, row['id'], reservation))
    try:
        await asyncio.wait_for(boundary.entered.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert boundary.cancelled == 1
        assert reservation.child.cancelled()
        assert owner.used == 0
        receipt = await write_and_recover(database, session, row, complete, path, boundary)
        print(json.dumps({'phase': phase, **receipt}))
        if phase != 'after_buffering':
            assert boundary.closed == ['acknowledged']
        assert await owner.shutdown()
    finally:
        boundary.release.set()
        boundary.release_observation()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await owner.shutdown()
        await database.close()


async def test_real_socket_poll_disconnect_releases_cursor_and_allows_replay_commit(tmp_path, monkeypatch):
    database, session, row, complete, path = await prepared_store(tmp_path)
    boundary = CursorBoundary(database, monkeypatch, 'after_execute')
    app = create_app(database, manage_store=False, settings=Settings(_env_file=None, public_demo=True))
    cancelled = asyncio.Event()
    observed = []
    original = app.state.sse_reads.read

    async def observe_read(*args, **kwargs):
        try:
            return await original(*args, **kwargs)
        except asyncio.CancelledError:
            observed.append('outer-cancellation')
            cancelled.set()
            raise

    monkeypatch.setattr(app.state.sse_reads, 'read', observe_read)
    writer = None
    try:
        async with loopback_server(app) as (_, port):
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(f'GET /api/investigations/{row["id"]}/events HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Demo-Session: {session}\r\n\r\n'.encode())
            await writer.drain()
            assert b'200 OK' in await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 2)
            await asyncio.wait_for(boundary.entered.wait(), 2)
            writer.close()
            await writer.wait_closed()
            await asyncio.wait_for(cancelled.wait(), 3)
            assert observed == ['outer-cancellation']
            assert boundary.cancelled == 1
            receipt = await write_and_recover(database, session, row, complete, path, boundary)
            assert boundary.closed == ['acknowledged']
            assert app.state.sse_reads.used == 0
            assert await app.state.sse_reads.shutdown()
            print(json.dumps({'phase': 'socket-disconnect', **receipt}))
    finally:
        boundary.release.set()
        boundary.release_observation()
        if writer:
            writer.close()
            await writer.wait_closed()
        await database.close()


async def test_genuine_exclusive_lock_remains_bounded_failure_then_recovers(tmp_path):
    database, session, _, _, path = await prepared_store(tmp_path)
    blocker = sqlite3.connect(path)
    blocker.execute('BEGIN EXCLUSIVE')
    try:
        with pytest.raises(OperationalError) as caught:
            await asyncio.wait_for(database.topology(session), 7)
        error = getattr(caught.value, 'orig', None)
        assert isinstance(error, sqlite3.OperationalError)
        assert error.sqlite_errorcode == sqlite3.SQLITE_BUSY
        assert error.sqlite_errorname == 'SQLITE_BUSY'
    finally:
        blocker.rollback()
        blocker.close()
        assert (await database.get_incident(session, 'INC-DEMO-001')).id == 'INC-DEMO-001'
        assert database.engine.sync_engine.pool.checkedout() == 0
        await database.close()

async def test_held_cursor_close_retains_exact_owner_until_acknowledged(tmp_path, monkeypatch, caplog):
    database, session, row, complete, path = await prepared_store(tmp_path)
    boundary = CursorBoundary(database, monkeypatch, 'after_execute')
    close = aiosqlite.Cursor.close
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def held_close(cursor):
        if boundary.cursor is not None and boundary.cursor() is cursor:
            calls.append(cursor)
            entered.set()
            await release.wait()
        return await close(cursor)

    monkeypatch.setattr(aiosqlite.Cursor, 'close', held_close)
    owner = PollingReadOwner(database, cleanup_timeout=0.05, shutdown_grace=0.05)
    record = owner.reserve()
    request = asyncio.create_task(owner.read(session, row['id'], record))
    try:
        await asyncio.wait_for(boundary.entered.wait(), 2)
        request.cancel()
        await asyncio.wait_for(entered.wait(), 2)
        with pytest.raises(asyncio.CancelledError):
            await request
        child = record.child
        assert not child.done() and child.cancelling() == 1
        assert record.cleanup.pending and record.cleanup.releasing and owner.used == 1
        assert len(calls) == 1 and boundary.closed == []
        assert database.engine.pool.checkedout() == 1
        if (locks := file_locks(path)) is not None:
            assert locks, 'A pending cursor is a physical SQLite lock owner'
        extra = [owner.reserve() for _ in range(3)]
        with pytest.raises(PollingUnavailable):
            owner.reserve()
        for unused in extra:
            owner.release_unused(unused)
        assert not await owner.shutdown()
        assert owner.records == (record,) and record.child is child
        assert any(item.message == 'sse_cleanup_deadline' for item in caplog.records)
        assert any(item.message == 'sse_shutdown_incomplete' for item in caplog.records)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(child, 2)
        assert boundary.closed == ['acknowledged'] and child.cancelling() == 1
        assert not record.cleanup.pending and owner.used == 0
        assert database.engine.pool.checkedout() == 0 and file_locks(path) in (None, [])
        await write_and_recover(database, session, row, complete, path, boundary)
        assert await owner.shutdown()
    finally:
        release.set()
        boundary.release.set()
        await asyncio.wait_for(asyncio.gather(request, record.child, return_exceptions=True), 3)
        boundary.release_observation()
        await database.close()


async def test_cursor_close_acknowledgement_error_remains_observed_and_retained(tmp_path, monkeypatch, caplog):
    database, session, row, _, path = await prepared_store(tmp_path)
    boundary = CursorBoundary(database, monkeypatch, 'after_execute')
    close = aiosqlite.Cursor.close
    failed_cursors = []
    invalid_drivers = weakref.WeakSet()
    reused = []

    @event.listens_for(database.engine.sync_engine, 'invalidate')
    def invalidated(connection, *_):
        if connection is not None:
            invalid_drivers.add(connection.driver_connection)

    @event.listens_for(database.engine.sync_engine, 'checkout')
    def checkout(connection, *_):
        if connection.driver_connection in invalid_drivers:
            reused.append(True)

    async def unconfirmed_close(cursor):
        value = await close(cursor)
        if boundary.cursor is not None and boundary.cursor() is cursor:
            failed_cursors.append(cursor)
            raise RuntimeError('injected cursor close acknowledgement failure')
        return value

    monkeypatch.setattr(aiosqlite.Cursor, 'close', unconfirmed_close)
    owner = PollingReadOwner(database)
    record = owner.reserve()
    request = asyncio.create_task(owner.read(session, row['id'], record))
    try:
        await asyncio.wait_for(boundary.entered.wait(), 2)
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
        assert record.child.done() and not record.child.cancelled()
        assert isinstance(record.child.exception(), RuntimeError)
        assert record.observed and record.cleanup.pending and owner.used == 1
        assert failed_cursors and record.cleanup._resources
        # Closure was physically acknowledged by the fixture before its error.
        # Application receipts must nevertheless retain the unconfirmed operation.
        assert boundary.closed == ['acknowledged'] and file_locks(path) in (None, [])
        assert database.engine.pool.checkedout() == 0 and invalid_drivers
        assert not await owner.shutdown(grace=0)
        assert any(item.message == 'sse_cleanup_failed' and item.error_type == 'RuntimeError' for item in caplog.records)
        assert any(item.message == 'sse_shutdown_incomplete' for item in caplog.records)
        assert await database.get_investigation(session, row['id']) is not None
        assert not reused
    finally:
        boundary.release.set()
        boundary.release_observation()
        await asyncio.gather(request, record.child, return_exceptions=True)
        await database.close()
    assert owner.used == 1 and record.cleanup.pending