"""Finite SSE read ownership, cancellation races, capacity and shutdown."""

import asyncio
import logging

import pytest
from anyio import CancelScope
from creditops import main as main_module


class ControlledStore:
    def __init__(self, *, fail_cleanup=False, body_error=False):
        self.started = asyncio.Event()
        self.cleanup_started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0
        self.cancel_calls = []
        self.fail_cleanup = fail_cleanup
        self.body_error = body_error

    async def poll_investigation(self, session, identifier, cleanup):
        resource = object()
        cleanup.add(resource)
        self.calls += 1
        self.started.set()
        try:
            if self.body_error:
                raise ValueError("synthetic read error")
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancel_calls.append(asyncio.current_task().cancelling())
            raise
        finally:
            self.cleanup_started.set()
            with CancelScope(shield=True):
                await self.release.wait()
            if self.fail_cleanup:
                raise RuntimeError("synthetic cleanup error")
            cleanup.remove(resource)


@pytest.fixture
def owner_class():
    owner = getattr(main_module, "PollingReadOwner", None)
    if owner is None:

        def missing_owner(*_args, **_kwargs):
            pytest.fail("SSE polling must have an app-owned finite cleanup service")

        return missing_owner
    return owner


async def cancelled_read(owner, store):
    request = asyncio.create_task(owner.read("session", "investigation"))
    await asyncio.wait_for(store.started.wait(), 1)
    request.cancel()
    await asyncio.wait_for(store.cleanup_started.wait(), 1)
    return request


async def join_cancelled(request):
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(request, 1)


async def test_request_deadline_retains_exact_child_capacity_until_cleanup(owner_class, caplog):
    store = ControlledStore()
    owner = owner_class(store, capacity=1, cleanup_timeout=0.03)
    request = await cancelled_read(owner, store)
    record = owner.records[0]
    child = record.child
    try:
        await join_cancelled(request)
        assert owner.used == 1 and owner.records[0] is record
        assert record.child is child and not child.done()
        assert record.cleanup.pending
        assert store.cancel_calls == [1]
        assert any(item.message == "sse_cleanup_deadline" for item in caplog.records)
        with pytest.raises(main_module.PollingUnavailable):
            owner.reserve()
        assert store.calls == 1
    finally:
        store.release.set()
        await asyncio.wait_for(asyncio.gather(child, return_exceptions=True), 1)
    assert owner.used == 0 and not record.cleanup.pending


async def test_cleanup_before_deadline_preserves_original_outer_cancel(owner_class, monkeypatch, caplog):
    store = ControlledStore()
    owner = owner_class(store, cleanup_timeout=0.5)
    original = asyncio.CancelledError("original parent cancellation")

    async def deliver_cancel(child):
        await store.started.wait()
        raise original

    monkeypatch.setattr(main_module.asyncio, "shield", deliver_cancel)
    request = asyncio.create_task(owner.read("session", "investigation"))
    await asyncio.wait_for(store.cleanup_started.wait(), 1)
    store.release.set()
    try:
        await request
    except asyncio.CancelledError as propagated:
        assert propagated is original
    else:
        pytest.fail("Original cancellation must propagate")
    assert owner.used == 0 and store.cancel_calls == [1]
    assert not any(item.levelno >= logging.ERROR for item in caplog.records)


async def test_completed_child_parent_cancel_does_not_cancel_child(owner_class, monkeypatch):
    class FinishedStore:
        async def poll_investigation(self, *_):
            return {"status": "complete"}

    owner = owner_class(FinishedStore())
    original = asyncio.CancelledError("parent after child completion")
    children = []

    async def cancelled_after_completion(child):
        children.append(child)
        await child
        raise original

    monkeypatch.setattr(main_module.asyncio, "shield", cancelled_after_completion)
    with pytest.raises(asyncio.CancelledError) as caught:
        await owner.read("session", "investigation")
    assert caught.value is original and children[0].cancelling() == 0
    assert owner.used == 0


async def test_boundary_completion_cannot_lose_or_duplicate_retained_owner(owner_class):
    store = ControlledStore()
    owner = owner_class(store, capacity=1, cleanup_timeout=0)
    request = await cancelled_read(owner, store)
    record = owner.records[0]
    store.release.set()
    await join_cancelled(request)
    await asyncio.wait_for(asyncio.gather(record.child, return_exceptions=True), 1)
    assert owner.used == 0 and len(owner.records) == 0, (
        record.observed,
        record.cleanup.pending,
        record.child.done(),
        record.child.cancelling(),
        store.cancel_calls,
    )
    lease = owner.reserve()
    assert owner.used == 1
    owner.release_unused(lease)
    assert owner.used == 0


async def test_cleanup_exception_is_observed_and_unproven_slot_retained(owner_class, caplog):
    store = ControlledStore(fail_cleanup=True)
    owner = owner_class(store, capacity=1, cleanup_timeout=0.5)
    request = await cancelled_read(owner, store)
    record = owner.records[0]
    store.release.set()
    await join_cancelled(request)
    assert record.child.done() and record.cleanup.pending
    assert owner.used == 1
    assert any(
        item.message == "sse_cleanup_failed" and item.error_type == "RuntimeError" for item in caplog.records
    )
    assert not await owner.shutdown(grace=0)
    assert owner.records[0] is record


async def test_body_error_with_successful_cleanup_releases_slot_and_is_visible(owner_class, caplog):
    store = ControlledStore(body_error=True)
    store.release.set()
    owner = owner_class(store)
    with pytest.raises(ValueError, match="synthetic read error"):
        await owner.read("session", "investigation")
    assert owner.used == 0
    assert any(
        item.message == "sse_read_failed" and item.error_type == "ValueError" for item in caplog.records
    )


async def test_capacity_is_per_instance_and_reserved_before_spawn(owner_class):
    first = owner_class(ControlledStore(), capacity=1)
    second = owner_class(ControlledStore(), capacity=1)
    reservation = first.reserve()
    try:
        with pytest.raises(main_module.PollingUnavailable):
            await first.read("session", "investigation")
        assert first.store.calls == 0
        other = second.reserve()
        second.release_unused(other)
    finally:
        first.release_unused(reservation)
    assert first.used == second.used == 0


async def test_create_task_failure_releases_unstarted_reservation(owner_class, monkeypatch):
    owner = owner_class(ControlledStore(), capacity=1)

    def fail_start(*_args, **_kwargs):
        raise RuntimeError("synthetic task creation failure")

    monkeypatch.setattr(main_module.asyncio, "create_task", fail_start)
    with pytest.raises(RuntimeError, match="task creation"):
        await owner.read("session", "investigation")
    assert owner.used == 0


async def test_eager_child_completion_is_still_registered_and_observed(owner_class):
    class FinishedStore:
        async def poll_investigation(self, *_):
            return {"status": "complete"}

    loop = asyncio.get_running_loop()
    previous = loop.get_task_factory()
    loop.set_task_factory(asyncio.eager_task_factory)
    try:
        owner = owner_class(FinishedStore())
        assert await owner.read("session", "investigation") == {"status": "complete"}
        assert owner.used == 0
    finally:
        loop.set_task_factory(previous)


async def test_shutdown_empty_stops_admission(owner_class):
    owner = owner_class(ControlledStore())
    assert await owner.shutdown(grace=0)
    with pytest.raises(main_module.PollingUnavailable):
        owner.reserve()


@pytest.mark.parametrize("release_within_grace", [True, False])
async def test_shutdown_never_recancels_or_discards_retained_child(owner_class, caplog, release_within_grace):
    store = ControlledStore()
    owner = owner_class(store, cleanup_timeout=0)
    request = await cancelled_read(owner, store)
    await join_cancelled(request)
    record = owner.records[0]
    if release_within_grace:
        store.release.set()
    try:
        complete = await owner.shutdown(grace=0.03)
        assert complete is release_within_grace
        assert store.cancel_calls == [1] and record.child.cancelling() == 1
        with pytest.raises(main_module.PollingUnavailable):
            owner.reserve()
        if not release_within_grace:
            assert owner.records[0] is record and not record.child.done()
            assert any(item.message == "sse_shutdown_incomplete" for item in caplog.records)
    finally:
        store.release.set()
        await asyncio.wait_for(asyncio.gather(record.child, return_exceptions=True), 1)
    assert owner.used == 0


class EndpointStore:
    def __init__(self):
        self.calls = 0

    async def get_investigation(self, session, identifier):
        self.calls += 1
        if identifier == "missing":
            return None
        return {"status": "running", "steps": []}

    async def poll_investigation(self, session, identifier, cleanup):
        return await self.get_investigation(session, identifier)


def events_endpoint(app):
    return next(
        route.endpoint
        for route in app.routes
        if getattr(route, "path", None) == "/api/investigations/{id}/events"
    )


def endpoint_app(store):
    from creditops.settings import Settings

    return main_module.create_app(
        store, manage_store=False, settings=Settings(_env_file=None, public_demo=True)
    )


async def test_capacity_refusal_after_unchanged_authorization_before_headers(owner_class):
    from fastapi import HTTPException

    store = EndpointStore()
    app = endpoint_app(store)
    owner = app.state.sse_reads
    leases = [owner.reserve() for _ in range(4)]
    try:
        with pytest.raises(HTTPException) as missing:
            await events_endpoint(app)("missing", "session")
        assert missing.value.status_code == 404
        with pytest.raises(HTTPException) as full:
            await events_endpoint(app)("valid", "session")
        assert full.value.status_code == 503
        assert store.calls == 2 and owner.used == 4
    finally:
        for lease in leases:
            owner.release_unused(lease)


async def test_header_send_cancel_releases_reservation_without_starting_read(owner_class):
    store = EndpointStore()
    app = endpoint_app(store)
    response = await events_endpoint(app)("valid", "session")
    assert app.state.sse_reads.used == 1
    original = asyncio.CancelledError("headers cancelled")

    async def send(message):
        assert message["type"] == "http.response.start"
        raise original

    async def receive():
        await asyncio.Event().wait()

    with pytest.raises(asyncio.CancelledError) as caught:
        await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
    assert caught.value is original
    assert app.state.sse_reads.used == 0 and store.calls == 1


async def test_established_stream_capacity_error_uses_safe_frame_and_closes(owner_class):
    store = EndpointStore()
    app = endpoint_app(store)
    response = await events_endpoint(app)("valid", "session")
    leases = []
    bodies = []

    async def send(message):
        if message["type"] == "http.response.body":
            bodies.append(message.get("body", b""))
            if message.get("body") == b": heartbeat\n\n":
                leases.extend(app.state.sse_reads.reserve() for _ in range(4))

    async def receive():
        await asyncio.Event().wait()

    try:
        await asyncio.wait_for(response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send), 1)
        assert bodies[0] == b": heartbeat\n\n"
        assert bodies[1].startswith(b"event: error\ndata: ")
        assert bodies[-1] == b"" and store.calls == 2
    finally:
        for lease in leases:
            app.state.sse_reads.release_unused(lease)
    assert app.state.sse_reads.used == 0


async def test_lifespan_preserves_pending_cleanup_and_skips_disposal(owner_class, caplog):
    class LifespanStore(ControlledStore):
        def __init__(self):
            super().__init__()
            self.closed = 0

        async def initialize(self):
            pass

        async def topology(self, *_):
            return {"services": []}

        async def close(self):
            self.closed += 1

    from creditops.settings import Settings

    store = LifespanStore()
    app = main_module.create_app(
        store, settings=Settings(_env_file=None, public_demo=True, telemetry_mode="persisted")
    )
    owner = app.state.sse_reads
    owner.cleanup_timeout = 0
    owner.shutdown_grace = 0.03
    record = None
    try:
        with pytest.raises(RuntimeError, match="SSE polling cleanup incomplete"):
            async with app.router.lifespan_context(app):
                request = await cancelled_read(owner, store)
                await join_cancelled(request)
                record = owner.records[0]
        assert store.closed == 0 and owner.records[0] is record
        assert store.cancel_calls == [1]
        assert any(item.message == "sse_shutdown_incomplete" for item in caplog.records)
    finally:
        store.release.set()
        if record:
            await asyncio.wait_for(asyncio.gather(record.child, return_exceptions=True), 1)
    assert owner.used == 0


async def test_reserved_response_after_admission_stop_cannot_start_read(owner_class):
    store = EndpointStore()
    app = endpoint_app(store)
    response = await events_endpoint(app)("valid", "session")
    app.state.sse_reads.stop_admission()
    bodies = []

    async def send(message):
        if message["type"] == "http.response.body":
            bodies.append(message.get("body", b""))

    async def receive():
        await asyncio.Event().wait()

    await asyncio.wait_for(response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send), 1)
    assert store.calls == 1
    assert bodies[0].startswith(b"event: error\ndata: ")
    assert app.state.sse_reads.used == 0
