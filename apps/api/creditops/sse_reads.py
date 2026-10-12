"""Bounded admission and retained cleanup ownership for SSE polling reads only."""

import asyncio
import logging
from dataclasses import dataclass, field

from anyio import CancelScope
from starlette.responses import StreamingResponse

from .store import PollingCleanup

LOGGER = logging.getLogger("creditops.sse")


class PollingUnavailable(RuntimeError):
    pass


@dataclass(eq=False)
class PollingRead:
    cleanup: PollingCleanup = field(default_factory=PollingCleanup)
    child: asyncio.Task | None = None
    cancel_sent: bool = False
    observed: bool = False


class PollingReadOwner:
    """Four active/retained slots; request waiting is bounded, native work is not."""

    def __init__(self, store, *, capacity=4, cleanup_timeout=2, shutdown_grace=5):
        self.store = store
        self.capacity = capacity
        self.cleanup_timeout = cleanup_timeout
        self.shutdown_grace = shutdown_grace
        self._records: set[PollingRead] = set()
        self._accepting = True

    def _observe_completed(self):
        for record in tuple(self._records):
            if record.child is not None and record.child.done():
                self._finished(record)

    @property
    def records(self):
        self._observe_completed()
        return tuple(self._records)

    @property
    def used(self):
        self._observe_completed()
        return len(self._records)

    def reserve(self):
        if not self._accepting or self.used >= self.capacity:
            raise PollingUnavailable(
                "Investigation stream capacity unavailable; retrieve the saved result or retry"
            )
        record = PollingRead()
        self._records.add(record)
        return record

    def release_unused(self, record):
        if record.child is None:
            self._records.discard(record)

    def _finished(self, record):
        if record.observed or not record.child.done():
            return
        record.observed = True
        error = None if record.child.cancelled() else record.child.exception()
        if record.cleanup.pending:
            LOGGER.error(
                "sse_cleanup_failed",
                extra={"error_type": type(error).__name__ if error else "UnconfirmedCleanup"},
            )
            # Even a completed child does not acknowledge failed physical cleanup.
            return
        if error is not None:
            LOGGER.error("sse_read_failed", extra={"error_type": type(error).__name__})
        self._records.discard(record)

    async def read(self, session, identifier, reservation=None):
        if not self._accepting:
            if reservation is not None:
                self.release_unused(reservation)
            raise PollingUnavailable(
                "Investigation stream capacity unavailable; retrieve the saved result or retry"
            )
        record = reservation or self.reserve()
        if record not in self._records or record.child is not None:
            raise PollingUnavailable(
                "Investigation stream capacity unavailable; retrieve the saved result or retry"
            )
        coroutine = self.store.poll_investigation(session, identifier, record.cleanup)
        try:
            record.child = asyncio.create_task(coroutine, name="creditops.sse.poll")
        except BaseException:
            coroutine.close()
            self.release_unused(record)
            raise
        record.child.add_done_callback(lambda _child: self._finished(record))
        try:
            return await asyncio.shield(record.child)
        except asyncio.CancelledError:
            if not record.child.done() and not record.cancel_sent:
                record.cancel_sent = True
                record.child.cancel()
            # asyncio.wait never cancels its wait-set children at expiry.
            with CancelScope(shield=True):
                await asyncio.wait({record.child}, timeout=self.cleanup_timeout)
            if not record.child.done():
                LOGGER.error("sse_cleanup_deadline")
            raise
        finally:
            if record.child.done():
                self._finished(record)

    def stop_admission(self):
        self._accepting = False

    async def shutdown(self, *, grace=None):
        self.stop_admission()
        children = {
            record.child for record in self._records if record.child is not None and not record.child.done()
        }
        if children:
            with CancelScope(shield=True):
                await asyncio.wait(children, timeout=self.shutdown_grace if grace is None else grace)
        for record in tuple(self._records):
            if record.child is not None and record.child.done():
                self._finished(record)
        if self._records:
            LOGGER.error("sse_shutdown_incomplete")
            return False
        return True


class PollingStore:
    def __init__(self, owner, reservation):
        self.owner = owner
        self.reservation = reservation

    async def get_investigation(self, session, identifier):
        reservation, self.reservation = self.reservation, None
        return await self.owner.read(session, identifier, reservation)

    def release_unused(self):
        if self.reservation is not None:
            self.owner.release_unused(self.reservation)
            self.reservation = None


class PollingResponse(StreamingResponse):
    """Own admission even if cancellation prevents the iterator from starting."""

    def __init__(self, content, polling_store, **kwargs):
        super().__init__(content, **kwargs)
        self.polling_store = polling_store

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.polling_store.release_unused()
