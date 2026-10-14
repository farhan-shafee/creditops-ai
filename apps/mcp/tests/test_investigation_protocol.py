"""Actual API -> owned stdio MCP -> API callback; no live model is used."""

import asyncio
import copy
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from creditops.diagnostic_clients import DiagnosticConnectionError, MCPDiagnosticClient
from creditops.investigator import collect_adaptive_investigation
from creditops.providers import AdaptiveDecision, DeterministicProvider
from creditops.store import Store
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from stdio_test_owner import StdioProbe, finish_task, wait_for_tool

ROOT = Path(__file__).resolve().parents[3]

# Install the offline boundary before importing the API in its fresh interpreter.
# Parent pytest fixtures cannot protect a subprocess's dotenv or HTTP transports.
API_BOOTSTRAP = """
from creditops.settings import Settings
Settings.model_config['env_file'] = None
import httpx, httpx2, sys, uvicorn
def protect(library):
    sync = library.HTTPTransport.handle_request
    asynchronous = library.AsyncHTTPTransport.handle_async_request
    def allowed(request):
        if request.url.host not in {'127.0.0.1', 'localhost', '::1'}:
            raise AssertionError('Offline MCP tests forbid external HTTP')
    def guarded_sync(self, request):
        allowed(request)
        return sync(self, request)
    async def guarded_async(self, request):
        allowed(request)
        return await asynchronous(self, request)
    library.HTTPTransport.handle_request = guarded_sync
    library.AsyncHTTPTransport.handle_async_request = guarded_async
protect(httpx)
protect(httpx2)
uvicorn.run('creditops.main:app', host='127.0.0.1', port=int(sys.argv[1]))
"""


@pytest.fixture
async def real_api(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'protocol.db').as_posix()}"
    store = Store(database_url)
    await store.initialize()
    session_id = str(uuid4())
    for index in range(1, 4):
        await store.activate_case(session_id, f"INC-DEMO-{index:03d}")
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper() not in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ADMIN_API_KEY", "MCP_HTTP_TOKEN"}
    }
    env.update({
        "DATABASE_URL": database_url,
        "MCP_API_URL": url,
        "TELEMETRY_MODE": "persisted",
        "EMBEDDINGS_ENABLED": "false",
        "PUBLIC_DEMO": "true",
        "INVESTIGATION_TIMEOUT_SECONDS": "60",
        "PYTHONPATH": os.pathsep.join([str(ROOT / "apps/api"), str(ROOT / "apps/mcp")]),
    })
    log = (tmp_path / "api.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-c", API_BOOTSTRAP, str(port)],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        async with httpx.AsyncClient(base_url=url, headers={"X-Demo-Session": session_id}, timeout=3) as http:
            for _ in range(150):
                try:
                    if (await http.get("/health")).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                if process.poll() is not None:
                    raise AssertionError((tmp_path / "api.log").read_text())
                await asyncio.sleep(0.05)
            else:
                raise AssertionError("Real API did not start before deadline")
            yield http, store, session_id, url
    finally:
        process.terminate()
        try:
            await asyncio.to_thread(process.wait, 10)
        except subprocess.TimeoutExpired:
            process.kill()
            await asyncio.to_thread(process.wait, 5)
        log.close()
        await store.close()


@pytest.mark.parametrize("number", [1, 2, 3])
async def test_api_worker_investigates_through_real_stdio_callback_without_deadlock(real_api, number):
    http, _, _, _ = real_api
    incident_id = f"INC-DEMO-{number:03d}"
    response = await http.post("/api/investigations", json={"incident_id": incident_id, "mode": "MCP_DEMO"})
    assert response.status_code == 200, response.text
    identifier = response.json()["id"]
    for _ in range(400):
        row = (await http.get(f"/api/investigations/{identifier}")).json()
        if row["status"] != "running":
            break
        await asyncio.sleep(0.05)
    assert row["status"] == "complete", row
    assert row["provenance"]["transport"] == "mcp_stdio"
    assert row["provenance"]["workflow"] == "evidence_first_v1"
    assert row["provenance"]["tool_schema_verified"] is True
    assert row["provenance"]["model_called"] is False
    assert row["provider"] == "deterministic"
    tools = [step for step in row["steps"] if step["tool"] != "assessment_validation"]
    assert len(tools) == 10
    assert [step["tool"] for step in tools[:4]] == ["get_incident", "get_service_topology", "query_metrics", "search_logs"]
    assert all(step["selected_by"] == "application_runbook" and step["provider_turn"] == 0 for step in tools[:4])
    assert all(step["selected_by"] == "deterministic" and step["provider_turn"] > 0 for step in tools[4:])
    assert all(step["transport"] == "mcp_stdio" and step["status"] == "complete" for step in tools)
    expected = (
        await http.get(
            "/api/diagnostics/query_metrics",
            params={"incident_id": incident_id, "as_of": row["provenance"]["snapshot_cutoff"], "limit": 50},
        )
    ).json()
    returned = {item["id"]: item for item in row["evidence"]}
    assert expected and all(returned[item["id"]] == item for item in expected)
    assert set(row["assessment"]["supporting_evidence_ids"]) <= returned.keys()
    other = await http.get(f"/api/investigations/{identifier}", headers={"X-Demo-Session": str(uuid4())})
    assert other.status_code == 404


async def test_scripted_typed_actions_traverse_real_stdio_and_preserve_filters(real_api):
    """Actual MCP integration with scripted choices, not live-model verification."""
    _, store, session_id, url = real_api
    incident_id = "INC-DEMO-001"
    cutoff = await store.freeze_snapshot(session_id, incident_id)
    initial_metrics = await store.evidence(session_id, incident_id=incident_id, kind="metric", as_of=cutoff)
    initial_ids = {item.id for item in initial_metrics}
    service_metrics = await store.evidence(
        session_id, incident_id=incident_id, kind="metric", service="quote-service", as_of=cutoff
    )
    # Choose a returned service-filtered observation omitted by the bounded broad
    # query. This is a genuinely new sample, not a fixture answer or a raised
    # no-progress allowance, so its real MCP result can reach another decision.
    sample = next(item for item in service_metrics if item.id not in initial_ids)
    metric_filters = {
        "service": sample.service,
        "metric": sample.data["metric"],
        "start": sample.timestamp,
        "end": sample.timestamp,
    }

    class ScriptedTypedProvider(DeterministicProvider):
        name = "scripted_stdio_contract_test"

        def __init__(self):
            self.actions = iter(
                [
                    {"name": "search_logs", "q": "rfq response OR timeout"},
                    {"name": "query_metrics", **metric_filters},
                ]
            )
            self.observations = []

        async def next_action(self, incident, schemas, observations, evidence):
            self.observations.append(copy.deepcopy({"steps": observations, "evidence": evidence}))
            request = next(self.actions, None)
            return AdaptiveDecision.model_validate(
                {"action": "assess" if request is None else "tool", "request": request}
            ), {}

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "creditops_mcp.server"],
        cwd=ROOT,
        env={
            "PYTHONPATH": os.pathsep.join([str(ROOT / "apps/api"), str(ROOT / "apps/mcp")]),
            "CREDITOPS_API_URL": url,
            "MCP_DEMO_SESSION": session_id,
            "MCP_INCIDENT_ID": incident_id,
            "MCP_AS_OF": cutoff,
        },
    )
    adapter = MCPDiagnosticClient(session_id, incident_id, cutoff, client=Client(parameters, cache=None))
    provider = ScriptedTypedProvider()
    result = await collect_adaptive_investigation(
        store, session_id, incident_id, provider, diagnostic_client=adapter
    )
    tools = [step for step in result["steps"] if step["tool"] != "assessment_validation"]
    assert [step["tool"] for step in tools] == ["get_incident", "get_service_topology", "query_metrics", "search_logs", "search_logs", "query_metrics"]
    assert all(step["status"] == "complete" and step["transport"] == "mcp_stdio" for step in tools)
    assert all(step["selected_by"] == "application_runbook" and step["provider_turn"] == 0 for step in tools[:4])
    assert all(step["selected_by"] == "scripted_provider" and step["provider_turn"] > 0 for step in tools[4:])
    assert [step["tool"] for step in provider.observations[0]["steps"]] == ["get_incident", "get_service_topology", "query_metrics", "search_logs"]
    assert tools[4]["evidence_ids"] == []
    assert provider.observations[1]["steps"][-1]["evidence_ids"] == []
    assert provider.observations[1]["evidence"] == provider.observations[0]["evidence"]
    assert tools[5]["safe_arguments"] == metric_filters
    expected = await store.evidence(
        session_id, incident_id=incident_id, kind="metric", as_of=cutoff, **metric_filters
    )
    assert expected and set(tools[5]["evidence_ids"]) == {item.id for item in expected}
    assert sample.id in tools[5]["evidence_ids"]
    assert sample.id not in {item["id"] for item in provider.observations[1]["evidence"]}
    assert sample.id in {item["id"] for item in provider.observations[2]["evidence"]}
    assert set(provider.observations[2]["steps"][-1]["evidence_ids"]) == {item.id for item in expected}
    assert len(provider.observations) == 3
    assert result["provenance"]["tool_calls"] == 6
    assert result["provenance"]["model_called"] is False
    assert result["provenance"]["assessment_source"] == {
        "kind": "scripted_provider",
        "provider": "scripted_stdio_contract_test",
    }
    assert adapter._entered is False


async def test_malformed_scripted_decision_is_visible_without_false_real_mcp_call(real_api):
    _, store, session_id, url = real_api
    incident_id = "INC-DEMO-001"
    cutoff = await store.freeze_snapshot(session_id, incident_id)

    class InvalidTypedProvider(DeterministicProvider):
        name = "scripted_invalid_contract_test"

        async def next_action(self, *args):
            return {"action": "tool", "request": {"name": "query_metrics", "q": "latency"}}, {}

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "creditops_mcp.server"],
        cwd=ROOT,
        env={
            "PYTHONPATH": os.pathsep.join([str(ROOT / "apps/api"), str(ROOT / "apps/mcp")]),
            "CREDITOPS_API_URL": url,
            "MCP_DEMO_SESSION": session_id,
            "MCP_INCIDENT_ID": incident_id,
            "MCP_AS_OF": cutoff,
        },
    )
    adapter = MCPDiagnosticClient(session_id, incident_id, cutoff, client=Client(parameters, cache=None))
    snapshots = []

    async def capture(row):
        snapshots.append(copy.deepcopy(row))

    with pytest.raises(ValueError, match="invalid bounded diagnostic action"):
        await collect_adaptive_investigation(
            store,
            session_id,
            incident_id,
            InvalidTypedProvider(),
            capture,
            diagnostic_client=adapter,
        )
    failed = snapshots[-1]
    assert failed["status"] == "failed" and failed["assessment"] is None
    assert [step["tool"] for step in failed["steps"]] == ["get_incident", "get_service_topology", "query_metrics", "search_logs"]
    assert all(step["status"] == "complete" and step["selected_by"] == "application_runbook" for step in failed["steps"])
    assert failed["provenance"]["tool_calls"] == 4
    assert failed["provenance"]["action_rejections"] == [
        {
            "stage": "parsed_decision",
            "reason": "invalid_tool_contract",
            "provider_turn": 1,
            "mcp_dispatched": False,
        }
    ]
    assert adapter._entered is False


async def test_real_stdio_disconnect_after_context_cannot_complete_investigation(real_api, tmp_path):
    _, store, session_id, url = real_api
    script = tmp_path / "disconnect.py"
    script.write_text(
        "import os\nfrom creditops_mcp.server import HttpDiagnosticClient, create_server\n"
        "class Disconnect(HttpDiagnosticClient):\n"
        " async def call(self, tool, arguments):\n"
        "  if tool == 'query_metrics': os._exit(7)\n"
        "  return await super().call(tool, arguments)\n"
        f"create_server(Disconnect({url!r}, {session_id!r})).run()\n",
        encoding="utf-8",
    )
    cutoff = await store.freeze_snapshot(session_id, "INC-DEMO-001")
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(script)],
        cwd=ROOT,
        env={"PYTHONPATH": os.pathsep.join([str(ROOT / "apps/api"), str(ROOT / "apps/mcp")])},
    )
    adapter = MCPDiagnosticClient(
        session_id, "INC-DEMO-001", cutoff, client=Client(params, read_timeout_seconds=3)
    )
    snapshots = []

    async def capture(row):
        snapshots.append(json.loads(json.dumps(row)))

    with pytest.raises(DiagnosticConnectionError):
        await collect_adaptive_investigation(
            store, session_id, "INC-DEMO-001", DeterministicProvider(), capture, diagnostic_client=adapter
        )
    assert snapshots[-1]["status"] == "failed"
    assert snapshots[-1]["assessment"] is None
    assert not any(row["status"] == "complete" for row in snapshots)
    assert snapshots[-1]["steps"][0]["evidence_ids"]
    assert [step["tool"] for step in snapshots[-1]["steps"]] == ["get_incident", "get_service_topology", "query_metrics"]
    assert [step["status"] for step in snapshots[-1]["steps"]] == ["complete", "complete", "failed"]
    assert snapshots[-1]["provenance"]["provider_turns"] == 0
    assert snapshots[-1]["provenance"]["tool_calls"] == 3
    assert all(step["selected_by"] == "application_runbook" for step in snapshots[-1]["steps"])
    assert adapter._entered is False


def process_is_running(pid):
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code))) and exit_code.value == 259
    finally:
        kernel.CloseHandle(handle)


async def test_cancelled_real_stdio_investigation_closes_owned_process(real_api, tmp_path, monkeypatch):
    _, store, session_id, url = real_api
    marker = tmp_path / "child.pid"
    child_phases = tmp_path / "child-phases.jsonl"
    script = tmp_path / "waiting.py"
    script.write_text(
        "import os,asyncio,time,json\nfrom pathlib import Path\n"
        f"phase_file=Path({str(child_phases)!r})\n"
        "def phase(name):\n"
        " with phase_file.open('a') as out: out.write(json.dumps({'phase':name,'monotonic':time.monotonic(),'pid':os.getpid()})+'\\n')\n"
        "phase('bootstrap')\nfrom creditops_mcp.server import HttpDiagnosticClient,create_server\nphase('import_complete')\n"
        "class Waiting(HttpDiagnosticClient):\n"
        " async def call(self, tool, arguments):\n"
        "  phase(tool)\n"
        "  if tool == 'query_metrics':\n"
        f"   Path({str(marker)!r}).write_text(str(os.getpid()))\n"
        "   await asyncio.sleep(60)\n"
        "  return await super().call(tool, arguments)\n"
        f"create_server(Waiting({url!r}, {session_id!r})).run()\n",
        encoding="utf-8",
    )
    probe = StdioProbe(tmp_path, script)
    probe.install(monkeypatch)
    cutoff = await store.freeze_snapshot(session_id, "INC-DEMO-001")
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(script)],
        cwd=ROOT,
        env={"PYTHONPATH": os.pathsep.join([str(ROOT / "apps/api"), str(ROOT / "apps/mcp")])},
    )
    adapter = MCPDiagnosticClient(
        session_id, "INC-DEMO-001", cutoff, client=probe.client(parameters)
    )
    original_tasks = asyncio.all_tasks()
    task = asyncio.create_task(
        collect_adaptive_investigation(
            store, session_id, "INC-DEMO-001", DeterministicProvider(), diagnostic_client=adapter
        )
    )
    primary = None
    cleanup_deadline = None
    try:
        await wait_for_tool(task, marker, probe)
        pid = int(marker.read_text())
        assert probe.process is not None and probe.process.pid == pid
        assert process_is_running(pid)
        probe.phase("cancel_requested")
        cleanup_deadline = asyncio.get_running_loop().time() + 10
        task.cancel()
        done, _ = await asyncio.wait({task}, timeout=10)
        assert done, "Cancellation did not complete within existing cleanup bound"
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not process_is_running(pid)
        assert adapter._entered is False
        with pytest.raises(RuntimeError, match="async context manager"):
            _ = adapter.client.session
        await probe.join_exited_child()
        assert not (asyncio.all_tasks() - original_tasks - {task}), "Owned protocol task still pending"
    except BaseException as error:
        primary = error
        probe.phase("body_failed", error_type=type(error).__name__)
        raise
    finally:
        cleanup_errors = []
        try:
            remaining = 10 if cleanup_deadline is None else max(0, cleanup_deadline - asyncio.get_running_loop().time())
            await finish_task(task, primary, timeout=remaining)
            if probe.process is not None:
                await probe.join_exited_child()
            probe.phase("cleanup_complete", task_done=task.done(), cancelled=task.cancelled(), client_entered=adapter._entered, cancellation_requests=task.cancelling())
        except BaseException as cleanup:
            cleanup_errors.append(cleanup)
        finally:
            try:
                await probe.contain_after_failure(task)
            except BaseException as containment:
                cleanup_errors.append(containment)
        cleanup_errors.extend(probe.observation_errors)
        if cleanup_errors:
            errors = ([primary] if primary is not None else []) + cleanup_errors
            raise BaseExceptionGroup("Investigation body and owned cleanup failed", errors) from primary


async def test_body_assertion_still_joins_real_stdio_cleanup(real_api, tmp_path, monkeypatch):
    primary = AssertionError("Controlled assertion after query_metrics entry")
    original_phase = StdioProbe.phase
    def phase(self, name, **details):
        original_phase(self, name, **details)
        if name == "cancel_requested":
            raise primary
    monkeypatch.setattr(StdioProbe, "phase", phase)
    with pytest.raises(AssertionError) as result:
        await test_cancelled_real_stdio_investigation_closes_owned_process(real_api, tmp_path, monkeypatch)
    assert result.value is primary
    rows = [json.loads(line) for line in (tmp_path / "parent-phases.jsonl").read_text().splitlines()]
    assert rows[-1]["phase"] == "cleanup_complete"
    assert rows[-1]["task_done"] and rows[-1]["cancelled"]
    assert not rows[-1]["client_entered"] and rows[-1]["cancellation_requests"] == 1
    assert any(row["phase"] == "child_reaped" and row["returncode"] == 0 for row in rows)
    assert not any(row["phase"] == "emergency_child_containment" for row in rows)


async def test_phase_receipt_failure_cannot_bypass_real_stdio_cleanup(real_api, tmp_path, monkeypatch):
    original = OSError("controlled diagnostic writer failure")
    real_write = StdioProbe._write_phase
    fired = False
    def write(self, name, details):
        nonlocal fired
        if name == "protocol_enter_complete" and not fired:
            fired = True
            raise original
        return real_write(self, name, details)
    monkeypatch.setattr(StdioProbe, "_write_phase", write)
    with pytest.raises(BaseExceptionGroup) as result:
        await test_cancelled_real_stdio_investigation_closes_owned_process(real_api, tmp_path, monkeypatch)
    assert result.value.exceptions == (original,)
    rows = [json.loads(line) for line in (tmp_path / "parent-phases.jsonl").read_text().splitlines()]
    assert rows[-1]["phase"] == "cleanup_complete" and rows[-1]["cancelled"]
    assert not rows[-1]["client_entered"]
    assert any(row["phase"] == "child_reaped" and row["returncode"] == 0 for row in rows)
    assert not any(row["phase"] == "emergency_child_containment" for row in rows)
