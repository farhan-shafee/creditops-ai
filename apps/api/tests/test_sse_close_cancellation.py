"""Cancellation after a completed query must not interrupt already-owned rollback."""

import asyncio
import json
import logging
import os
from uuid import uuid4

import aiosqlite
import pytest
from creditops import store as store_module
from creditops.db import InvestigationRow
from creditops.sse_reads import PollingReadOwner
from creditops.store import Store
from sqlalchemy import event


@pytest.mark.parametrize("backend", ["sqlite", pytest.param("postgres", marks=pytest.mark.skipif(not os.getenv("CREDITOPS_TEST_DATABASE_URL"), reason="Disposable local PostgreSQL URL not configured"))])
@pytest.mark.parametrize("phase", ["before-close", "during-rollback", "during-pool-reset", "after-completion"])
async def test_polling_cancel_respects_public_release_phase(tmp_path, monkeypatch, caplog, backend, phase):
    database = Store(os.environ["CREDITOPS_TEST_DATABASE_URL"] if backend == "postgres" else f"sqlite+aiosqlite:///{(tmp_path / 'rollback.db').as_posix()}")
    await database.initialize()
    session_id = str(uuid4())
    identifier = str(uuid4())
    payload = {"id": identifier, "incident_id": "INC-DEMO-001", "mode": "REPLAY", "status": "complete", "created_at": "2026-10-12T12:00:00Z", "steps": [], "evidence": [], "assessment": None}
    await database.save_investigation(session_id, payload)
    entered, release = asyncio.Event(), asyncio.Event()
    observations = []
    drivers = []
    invalidated = set()
    reused_invalid = []
    @event.listens_for(database.engine.sync_engine, "reset")
    def observed_pool_reset(connection, _record, state):
        if store_module._POLLING_CLEANUP.get() and phase == "during-pool-reset" and not entered.is_set():
            assert state.asyncio_safe
            observations.append("pool-reset-enter")
            entered.set()

            async def hold(_driver):
                await release.wait()

            connection.run_async(hold)
            observations.append("pool-reset-ack")

    original_shield = asyncio.shield
    original_get = database.sessions.class_.get

    @event.listens_for(database.engine.sync_engine, "checkout")
    def checkout(connection, *_):
        driver = connection.driver_connection
        if driver not in drivers:
            drivers.append(driver)
        if driver in invalidated:
            reused_invalid.append(driver)

    @event.listens_for(database.engine.sync_engine, "invalidate")
    def invalidate(connection, *_):
        if connection is not None:
            invalidated.add(connection.driver_connection)

    class ObservedSession(database.sessions.class_):
        async def get(self, entity, ident, **kwargs):
            result = await original_get(self, entity, ident, **kwargs)
            if store_module._POLLING_CLEANUP.get() and entity is InvestigationRow:
                observations.append("query-completed")
                if phase == "before-close" and not entered.is_set():
                    entered.set()
                    await release.wait()
            return result

    database.sessions.class_ = ObservedSession
    if backend == "sqlite":
        rollback = aiosqlite.Connection.rollback

        async def observed_rollback(driver):
            if store_module._POLLING_CLEANUP.get():
                observations.append("public-rollback-enter")
                if phase == "during-rollback" and not entered.is_set():
                    entered.set()
                    await release.wait()
            result = await rollback(driver)
            if store_module._POLLING_CLEANUP.get():
                observations.append("public-rollback-ack")
            return result

        monkeypatch.setattr(aiosqlite.Connection, "rollback", observed_rollback)
    else:
        # SQLAlchemy's supported adapted-connection run_async scheduling boundary.
        dialect = database.engine.sync_engine.dialect
        rollback = dialect.do_rollback

        def observed_rollback(connection):
            if store_module._POLLING_CLEANUP.get():
                observations.append("public-rollback-enter")
                if phase == "during-rollback" and not entered.is_set():
                    entered.set()

                    async def hold(_driver):
                        await release.wait()

                    connection.run_async(hold)
            result = rollback(connection)
            if store_module._POLLING_CLEANUP.get():
                observations.append("public-rollback-ack")
            return result

        monkeypatch.setattr(dialect, "do_rollback", observed_rollback)

    if phase == "after-completion":
        async def after_child(child):
            value = await original_shield(child)
            observations.append("child-completed")
            entered.set()
            await release.wait()
            return value

        monkeypatch.setattr(asyncio, "shield", after_child)

    owner = PollingReadOwner(database, cleanup_timeout=0.03)
    request = asyncio.create_task(owner.read(session_id, identifier), name="test.request")
    record = None
    try:
        await asyncio.wait_for(entered.wait(), 2)
        record = owner.records[0] if owner.records else None
        # Completed children release the slot before the parent resumes.
        child = record.child if record else None
        observations.append("parent-cancel-issued")
        request.cancel("original-outer-cancel")
        with pytest.raises(asyncio.CancelledError, match="original-outer-cancel"):
            await asyncio.wait_for(request, 1)
        if phase in {"during-rollback", "during-pool-reset"}:
            assert record is not None
            observations.append(f"child-cancellations:{child.cancelling()}")
            print(json.dumps({"phase": phase, "backend": backend, "order": observations, "child_done": child.done(), "pending_receipt": record.cleanup.pending, "owned_slots": owner.used, "physical_checkouts": database.engine.pool.checkedout()}))
            assert not child.done(), "Cancellation must not interrupt rollback already releasing the session"
            assert child.cancelling() == 0
            assert owner.used == 1 and record.cleanup.pending
            assert database.engine.pool.checkedout() == 1
            assert not await owner.shutdown(grace=0)
            release.set()
            await asyncio.wait_for(child, 2)
            assert ("pool-reset-ack" if phase == "during-pool-reset" else "public-rollback-ack") in observations
            assert not record.cleanup.pending and owner.used == 0
        elif phase == "before-close":
            assert child.cancelling() == 1 and child.cancelled()
            assert ("pool-reset-ack" if phase == "during-pool-reset" else "public-rollback-ack") in observations
            assert not record.cleanup.pending and owner.used == 0
        else:
            assert owner.used == 0
        # No restart, no retry: independent read uses the same service and pool.
        monkeypatch.setattr(asyncio, "shield", original_shield)
        assert await database.get_investigation(session_id, identifier) == payload
        assert await database.ping()
        assert reused_invalid == []
        assert database.engine.pool.checkedout() == 0
        assert await owner.shutdown()
        assert not any(r.message in {"sse_cleanup_failed", "sse_read_failed"} or r.name.startswith("sqlalchemy.pool") and r.levelno >= logging.ERROR for r in caplog.records)
    finally:
        release.set()
        if not request.done():
            request.cancel()
        await asyncio.gather(request, return_exceptions=True)
        if record is not None:
            await asyncio.gather(record.child, return_exceptions=True)
        await database.close()
        if backend == "sqlite":
            for driver in drivers:
                # Test-only physical worker observation, separate from pool counts.
                await asyncio.to_thread(driver._thread.join, 1)
                assert not driver._thread.is_alive()
