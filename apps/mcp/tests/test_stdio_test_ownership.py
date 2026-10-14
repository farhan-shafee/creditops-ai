"""Controlled test-owner failures; real transport proof remains in the protocol test."""
import asyncio
from types import SimpleNamespace

import pytest
from stdio_test_owner import finish_task, wait_for_tool


class EarlyFailure(Exception):
    pass

def probe(returncode=None):
    return SimpleNamespace(process=SimpleNamespace(returncode=returncode), last_phase="protocol_enter")

async def test_early_exception_retains_original_identity(tmp_path):
    original = EarlyFailure("controlled pre-tool failure")
    async def failed():
        raise original
    task = asyncio.create_task(failed())
    await asyncio.wait({task})
    try:
        with pytest.raises(EarlyFailure) as result:
            await wait_for_tool(task, tmp_path / "missing", probe(), checks=1, interval=0)
        assert result.value is original
    finally:
        task.exception()

async def test_early_success_is_not_a_cancellation_test(tmp_path):
    async def completed():
        return None
    task = asyncio.create_task(completed())
    await task
    with pytest.raises(AssertionError, match="completed before query_metrics"):
        await wait_for_tool(task, tmp_path / "missing", probe(), checks=1, interval=0)

@pytest.mark.parametrize("returncode,message", [(7,"child exited before query_metrics.*7"), (None,"query_metrics.*task active.*protocol_enter")])
async def test_missing_marker_exposes_child_or_active_phase_without_cancelling(tmp_path, returncode, message):
    blocked = asyncio.Event()
    task = asyncio.create_task(blocked.wait())
    try:
        with pytest.raises(AssertionError, match=message):
            await wait_for_tool(task, tmp_path / "missing", probe(returncode), checks=1, interval=0)
        assert not task.done() and task.cancelling() == 0
    finally:
        await finish_task(task)

async def test_cleanup_observes_already_failed_task():
    original = EarlyFailure("controlled completed failure")
    async def failed():
        raise original
    task = asyncio.create_task(failed())
    await asyncio.wait({task})
    try:
        with pytest.raises(EarlyFailure) as result:
            await finish_task(task)
        assert result.value is original
    finally:
        task.exception()

async def test_assertion_failure_still_joins_cleanup_and_retains_primary():
    entered, cleaned = asyncio.Event(), asyncio.Event()
    async def work():
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()
    task = asyncio.create_task(work())
    await entered.wait()
    primary = AssertionError("controlled body assertion")
    with pytest.raises(AssertionError) as result:
        try:
            raise primary
        finally:
            await finish_task(task, primary)
    assert result.value is primary
    assert task.done() and task.cancelled() and cleaned.is_set()


async def test_cleanup_waits_for_acknowledgement_without_second_cancellation():
    entered, cleanup_entered, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def work():
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleanup_entered.set()
            await release.wait()
    task = asyncio.create_task(work())
    await entered.wait()
    task.cancel()
    await cleanup_entered.wait()
    joining = asyncio.create_task(finish_task(task, AssertionError("body failed while cleanup active")))
    try:
        assert not task.done() and task.cancelling() == 1
        release.set()
        await joining
        assert task.done() and task.cancelled() and task.cancelling() == 1
    finally:
        release.set()
        await joining


async def test_cleanup_exception_remains_visible_with_a_primary_failure():
    original = EarlyFailure("controlled cleanup failure")
    async def failed():
        raise original
    task = asyncio.create_task(failed())
    await asyncio.wait({task})
    with pytest.raises(EarlyFailure) as result:
        await finish_task(task, AssertionError("distinct primary"))
    assert result.value is original
