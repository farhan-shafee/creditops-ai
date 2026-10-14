"""Test-owned stdio observations; never alter MCP protocol or application deadlines."""
import asyncio
import json
import subprocess
import sys
import time

import anyio
from mcp import Client


async def wait_for_tool(task, marker, probe, *, checks=100, interval=0.05):
    # asyncio.wait observes completion without cancelling the investigated task.
    for _ in range(checks):
        if task.done():
            await task  # Preserve the original exception, including cancellation.
            raise AssertionError("Investigation completed before query_metrics entered")
        if marker.exists():
            return
        process = probe.process
        if process is not None and getattr(probe, "fallback", False):
            process.poll()
        if process is not None and process.returncode is not None:
            raise AssertionError(f"Owned child exited before query_metrics: {process.returncode}; phase={probe.last_phase}")
        await asyncio.wait({task}, timeout=interval)
    if task.done():
        await task
        raise AssertionError("Investigation completed before query_metrics entered")
    if marker.exists():
        return
    raise AssertionError(f"query_metrics not reached within existing readiness bound; task active; phase={probe.last_phase}")


async def finish_task(task, primary=None, *, timeout=10):
    if not task.done() and task.cancelling() == 0:
        task.cancel()
    done, _ = await asyncio.wait({task}, timeout=timeout)
    if not done:
        raise AssertionError("Investigation cleanup exceeded existing ten-second bound; task remains owned")
    try:
        await task  # Observe already-completed failures as well as pending cleanup.
    except asyncio.CancelledError:
        if not task.cancelled():
            raise
    except BaseException as error:
        if error is not primary:
            raise


class StdioProbe:
    def __init__(self, directory, script):
        self.directory, self.script = directory, script
        self.process = None
        self.fallback = False
        self.joined = False
        self.last_phase = "created"
        self.started = time.monotonic()
        self.spawn_receipt = None
        self.retained_task = None
        self.retained_outcome = None
        self.errlog = None
        self.observation_errors = []

    def phase(self, name, **details):
        self.last_phase = name
        try:
            self._write_phase(name, details)
        except Exception as error:
            self.observation_errors.append(error)

    def _write_phase(self, name, details):
        with (self.directory / "parent-phases.jsonl").open("a", encoding="utf-8") as out:
            if self.spawn_receipt is not None:
                out.write(json.dumps(self.spawn_receipt) + "\n")
                self.spawn_receipt = None
            out.write(json.dumps({"phase": name, "elapsed": round(time.monotonic() - self.started, 4), **details}) + "\n")

    def stderr(self):
        if self.errlog is None:
            self.errlog = (self.directory / "child.stderr").open("w", encoding="utf-8")
        return self.errlog

    def install(self, monkeypatch):
        real_open = anyio.open_process
        async def open_process(command, **kwargs):
            if str(self.script) not in command:
                return await real_open(command, **kwargs)
            self.phase("spawn_start")
            kwargs["stderr"] = self.stderr()
            process = await real_open(command, **kwargs)
            # Synchronous capture: no await in SDK's spawn-to-taskgroup handoff.
            self.process, self.fallback = process, False
            self.spawn_receipt = {"phase": "spawn_complete", "pid": process.pid, "elapsed": round(time.monotonic() - self.started, 4)}
            return process
        monkeypatch.setattr(anyio, "open_process", open_process)
        if sys.platform == "win32":
            # The pinned SDK's supported Windows fallback uses public Popen.
            real_popen = subprocess.Popen
            def popen(command, *args, **kwargs):
                selected = str(self.script) in command
                if selected:
                    kwargs["stderr"] = self.stderr()
                process = real_popen(command, *args, **kwargs)
                if selected:
                    self.process, self.fallback = process, True
                    self.spawn_receipt = {"phase": "fallback_spawn_complete", "pid": process.pid, "elapsed": round(time.monotonic() - self.started, 4)}
                return process
            monkeypatch.setattr(subprocess, "Popen", popen)

    def client(self, parameters):
        probe = self
        class ObservedClient(Client):
            async def __aenter__(self):
                probe.phase("protocol_enter_start")
                result = await super().__aenter__()
                probe.phase("protocol_enter_complete")
                return result
            async def list_tools(self, *args, **kwargs):
                probe.phase("discovery_start")
                result = await super().list_tools(*args, **kwargs)
                probe.phase("discovery_complete")
                return result
            async def call_tool(self, name, *args, **kwargs):
                probe.phase("tool_start", tool=name)
                result = await super().call_tool(name, *args, **kwargs)
                probe.phase("tool_complete", tool=name)
                return result
            async def __aexit__(self, *args):
                probe.phase("transport_close_start")
                try:
                    return await super().__aexit__(*args)
                finally:
                    probe.phase("transport_close_end")
        return ObservedClient(parameters, read_timeout_seconds=10)

    async def join_exited_child(self):
        if self.joined:
            return
        assert self.process is not None, "No owned subprocess captured; see child phase/stderr receipts"
        if self.fallback:
            self.process.poll()
        assert self.process.returncode is not None, "SDK transport returned with an owned child still running"
        if self.fallback:
            result = self.process.wait(timeout=10)
        else:
            async with asyncio.timeout(10):
                result = await self.process.wait()
        self.joined = True
        self.phase("child_reaped", pid=self.process.pid, returncode=result)

    async def contain_after_failure(self, task):
        # Keep an explicit reference and observe even a later failure after containment.
        self.retained_task = task
        def observed(completed):
            self.retained_outcome = "cancelled" if completed.cancelled() else completed.exception()
        task.add_done_callback(observed)
        try:
            # Emergency containment is explicitly NOT application cancellation proof.
            process = self.process
            if process is not None:
                if self.fallback:
                    process.poll()
                if process.returncode is None:
                    self.phase("emergency_child_containment", pid=process.pid)
                    process.kill()
                    if self.fallback:
                        await asyncio.to_thread(process.wait, 10)
                    else:
                        async with asyncio.timeout(10):
                            await process.wait()
            done, _ = await asyncio.wait({task}, timeout=10)
            assert done, "Emergency test containment did not join investigation; retained outcome observer remains attached"
            observed(task)
        finally:
            if self.errlog is not None:
                self.errlog.close()
