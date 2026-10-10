"""Offline runner policy through actual stdio MCP and isolated local HTTP/SQLite.

The provider decisions/receipt/reservation are explicitly scripted fixtures, not
live-model execution or billing evidence. The runner, ledger, progress storage,
orchestrator, MCP SDK/server and diagnostic HTTP boundary are real.
"""

import asyncio
import copy
import importlib.util
import json
import os
import socket
import subprocess
import sys
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from creditops import investigator
from creditops.diagnostic_clients import DiagnosticClientError, MCPDiagnosticClient
from creditops.providers import AdaptiveDecision, DeterministicProvider
from creditops.settings import PROJECT_ROOT
from creditops.store import Store
from mcp import Client
from mcp.client.stdio import StdioServerParameters

SPEC = importlib.util.spec_from_file_location(
    "strict_runner_fixture", PROJECT_ROOT / "scripts/verify_live.py"
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

FIXTURE_RESERVATION = Decimal("0.13320825")
FIXTURE_INPUT_CEILING = 147611

# This boundary is also installed in both child interpreters: no owner's dotenv
# is loaded, and a default HTTP transport cannot reach a provider endpoint.
OFFLINE_CHILD_BOUNDARY = """
from creditops.settings import Settings
Settings.model_config['env_file'] = None
import httpx, httpx2
def protect(library):
    sync = library.HTTPTransport.handle_request
    asynchronous = library.AsyncHTTPTransport.handle_async_request
    def allowed(request):
        if request.url.host not in {'127.0.0.1', 'localhost', '::1'}:
            raise AssertionError('Offline integration forbids external HTTP')
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
"""


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
        code = wintypes.DWORD()
        return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
    finally:
        kernel.CloseHandle(handle)


@pytest.fixture
async def isolated_failure_api(tmp_path):
    """Own only this fixture's fresh database, ephemeral port and child process."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'strict-runner.db').as_posix()}"
    store = Store(database_url)
    await store.initialize()
    requests_path = tmp_path / "diagnostic-requests.jsonl"
    bootstrap = tmp_path / "isolated_api.py"
    bootstrap.write_text(
        OFFLINE_CHILD_BOUNDARY + "\nimport json, uvicorn\nfrom pathlib import Path\n"
        "from starlette.responses import JSONResponse\n"
        "from creditops.main import create_app\n"
        "app = create_app(settings=Settings(_env_file=None))\n"
        "@app.middleware('http')\n"
        "async def controlled_error(request, call_next):\n"
        "    if request.url.path.startswith('/api/diagnostics/'):\n"
        f"        with Path({str(requests_path)!r}).open('a', encoding='utf-8') as output:\n"
        "            output.write(json.dumps({'path': request.url.path, 'arguments': dict(request.query_params), 'session': request.headers.get('x-demo-session')}) + '\\n')\n"
        "    if request.url.path == '/api/diagnostics/query_metrics':\n"
        "        return JSONResponse({'detail': 'Scripted isolated diagnostic failure'}, status_code=503)\n"
        "    return await call_next(request)\n"
        f"uvicorn.run(app, host='127.0.0.1', port={port}, log_level='warning')\n",
        encoding="utf-8",
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT"}
    }
    environment.update(
        DATABASE_URL=database_url,
        MCP_API_URL=url,
        TELEMETRY_MODE="persisted",
        EMBEDDINGS_ENABLED="false",
        PUBLIC_DEMO="true",
        PYTHONPATH=os.pathsep.join([str(PROJECT_ROOT / "apps/api"), str(PROJECT_ROOT / "apps/mcp")]),
    )
    log_path = tmp_path / "owned-api.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, str(bootstrap)], cwd=PROJECT_ROOT, env=environment, stdout=log, stderr=log
        )
        try:
            async with httpx.AsyncClient(base_url=url, timeout=1, trust_env=False) as client:
                for _ in range(150):
                    try:
                        if (await client.get("/health")).status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    assert process.poll() is None, log_path.read_text(encoding="utf-8")
                    await asyncio.sleep(0.05)
                else:
                    raise AssertionError("Owned offline API did not start")
            yield store, database_url, url, requests_path, environment
        finally:
            process.terminate()
            try:
                await asyncio.to_thread(process.wait, 10)
            except subprocess.TimeoutExpired:
                process.kill()
                await asyncio.to_thread(process.wait, 5)
            assert process.poll() is not None
            await store.close()
    assert log.closed


async def test_actual_runner_stops_after_real_mcp_tool_error_with_partial_receipt(
    isolated_failure_api, monkeypatch, tmp_path
):
    store, database_url, url, requests_path, environment = isolated_failure_api
    events = []
    adapters = []
    marker = tmp_path / "owned-mcp.pid"
    bootstrap = tmp_path / "isolated_mcp.py"
    bootstrap.write_text(
        OFFLINE_CHILD_BOUNDARY + "\nimport os\nfrom pathlib import Path\n"
        "from creditops_mcp.server import HttpDiagnosticClient, create_server\n"
        f"Path({str(marker)!r}).write_text(str(os.getpid()), encoding='utf-8')\n"
        "create_server(HttpDiagnosticClient(os.environ['CREDITOPS_API_URL'], os.environ['MCP_DEMO_SESSION'], incident_id=os.environ['MCP_INCIDENT_ID'], as_of=os.environ['MCP_AS_OF'])).run()\n",
        encoding="utf-8",
    )

    class ScriptedClient:
        async def close(self):
            events.append("provider_closed")

    class ScriptedProvider(DeterministicProvider):
        name = "scripted_strict_runner_fixture"

        def __init__(self):
            self.client = ScriptedClient()
            self.decisions = 0
            self.assessments = 0
            self.execution_receipts = []

        def enable_budget(self, maximum, *, reserved_spend, reservation_callback):
            assert maximum == 2 and reserved_spend == 0
            self.reserve = reservation_callback

        async def next_action(self, incident, schemas, observations, evidence):
            self.decisions += 1
            events.append("scripted_decision")
            if self.decisions == 1:
                self.reserve(FIXTURE_RESERVATION)
                self.execution_receipts.append(
                    {
                        "provider": self.name,
                        "status": "scripted_offline_fixture",
                        "request_started": False,
                        "input_tokens_ceiling": FIXTURE_INPUT_CEILING,
                        "reserved_cost_usd": str(FIXTURE_RESERVATION),
                        "usage": {
                            "input_tokens": None,
                            "output_tokens": None,
                            "total_tokens": None,
                            "estimated_cost_usd": None,
                        },
                        "fixture_only": True,
                    }
                )
            request = {"name": "query_metrics"} if self.decisions == 1 else None
            return AdaptiveDecision.model_validate(
                {"action": "tool" if request else "assess", "request": request}
            ), {}

        async def assess(self, *args):
            self.assessments += 1
            events.append("scripted_assessment")
            return await super().assess(*args)

    provider = ScriptedProvider()

    class OwnedRunnerStore(Store):
        async def close(self):
            await super().close()
            events.append("runner_store_closed")

    def owned_resources(configuration):
        # Production allowlist stays intact; only this test's independently
        # owned temporary SQLite and loopback port are permitted by the fixture.
        assert configuration.database_url == database_url
        assert configuration.mcp_api_url == url and url.startswith("http://127.0.0.1:")
        assert configuration.embeddings_enabled is False
        return {"database": "isolated synthetic SQLite fixture", "api": url, "embeddings_enabled": False}

    def real_owned_mcp(session, incident, cutoff):
        parameters = StdioServerParameters(
            command=sys.executable,
            args=[str(bootstrap)],
            cwd=PROJECT_ROOT,
            env={
                **environment,
                "CREDITOPS_API_URL": url,
                "MCP_DEMO_SESSION": session,
                "MCP_INCIDENT_ID": incident,
                "MCP_AS_OF": cutoff,
            },
        )
        adapter = MCPDiagnosticClient(session, incident, cutoff, client=Client(parameters, cache=None))
        adapters.append(adapter)
        return adapter

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("MCP_API_URL", url)
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "false")
    monkeypatch.setenv("STOP_ON_TOOL_ERROR", "false")
    monkeypatch.setattr(runner, "validate_local_resources", owned_resources)
    monkeypatch.setattr(runner, "Store", OwnedRunnerStore)
    monkeypatch.setattr(runner, "source_commit", lambda: "scripted-offline-source-fixture")
    monkeypatch.setattr(runner.subprocess, "check_output", lambda *args, **kwargs: "")
    monkeypatch.setattr(runner, "create_provider", lambda name: provider)
    monkeypatch.setattr(investigator, "MCPDiagnosticClient", real_owned_mcp)
    output = tmp_path / "scripted-offline-receipts"
    arguments = runner.parse_args(
        [
            "--provider",
            "openai",
            "--model",
            "gpt-5.4-mini-2026-03-17",
            "--case-count",
            "1",
            "--max-tool-calls",
            "12",
            "--max-provider-turns",
            "12",
            "--max-spend-usd",
            "2",
            "--timeout-seconds",
            "30",
            "--provider-timeout-seconds",
            "5",
            "--diagnostic-timeout-seconds",
            "10",
            "--total-timeout-seconds",
            "33",
            "--input-price-ceiling",
            "0.75",
            "--output-price-ceiling",
            "4.50",
            "--experiment-id",
            str(uuid4()),
            "--stage",
            "first",
            "--execute-paid",
            "--output-directory",
            str(output),
        ]
    )
    # execute-paid enters the real runner branch only. create_provider above is
    # a scripted fixture; both parent and subprocess HTTP guards remain active.
    with pytest.raises(DiagnosticClientError):
        await runner.run(arguments)

    assert provider.decisions == 1 and provider.assessments == 0
    assert events == ["scripted_decision", "provider_closed", "runner_store_closed"]
    assert len(adapters) == 1 and adapters[0]._entered is False
    assert marker.exists() and not process_is_running(int(marker.read_text(encoding="utf-8")))
    assert not list(output.glob("*.lock"))
    receipt = json.loads(next(output.glob("run-*.json")).read_text(encoding="utf-8"))
    ledger = json.loads(next(output.glob("experiment-*.json")).read_text(encoding="utf-8"))
    assert receipt["execution"] == ledger["state"] == "STOPPED"
    assert receipt["configuration"]["stop_on_tool_error"] is True
    assert ledger["configuration"]["stop_on_tool_error"] is True
    assert receipt["local_identity"]["verified"] is True
    assert receipt["error_category"] == "DiagnosticClientError"
    assert ledger["attempts"][0]["status"] == "interrupted_or_failed"
    assert (
        Decimal(receipt["reserved_spend_usd"]) == Decimal(ledger["reserved_spend_usd"]) == FIXTURE_RESERVATION
    )
    assert receipt["estimated_cost_usd"] is None and receipt["known_cost_subtotal_usd"] is None
    assert receipt["provider_calls"] == provider.execution_receipts
    assert receipt["provider_calls"][0]["input_tokens_ceiling"] == FIXTURE_INPUT_CEILING
    assert receipt["duration_seconds"] > 0 and ledger["elapsed_seconds"] == receipt["duration_seconds"]
    partial = receipt["results"][0]
    assert partial["status"] == "failed"
    assert partial["assessment"] is None and partial["provider_proposal"] is None
    assert partial["provenance"]["model_called"] is False
    assert partial["provenance"]["stop_on_tool_error"] is True
    assert partial["provenance"]["provider_turns"] == 1
    assert partial["provenance"]["tool_calls"] == 2
    assert partial["provenance"]["diagnostic_failure"] == {
        "tool": "query_metrics",
        "category": "error",
        "error_category": "DiagnosticClientError",
    }
    assert partial["provenance"]["stop_reason"]
    assert partial["validation_outcome"]["status"] == "not_validated"
    assert partial["validation_outcome"]["provider_response"] == "not_requested_due_to_diagnostic_failure"
    assert partial["validation_outcome"]["rejected_fields"] == []
    assert [step["tool"] for step in partial["steps"]] == ["get_incident", "query_metrics"]
    assert [step["status"] for step in partial["steps"]] == ["complete", "failed"]
    assert partial["steps"][1]["duration_ms"] > 0 and partial["steps"][1]["error"]
    assert partial["steps"][0]["evidence_ids"] == ["INC-DEMO-001"]
    assert [item["id"] for item in partial["evidence"]] == ["INC-DEMO-001"]
    assert partial["provider_calls"] == receipt["provider_calls"]
    saved = await store.get_investigation(partial["provenance"]["session_id"], partial["id"])
    assert saved["status"] == "failed" and saved["assessment"] is None
    assert saved["provider_calls"] == receipt["provider_calls"]
    requests = [json.loads(line) for line in requests_path.read_text(encoding="utf-8").splitlines()]
    assert [item["path"] for item in requests] == [
        "/api/diagnostics/get_incident",
        "/api/diagnostics/query_metrics",
    ]
    assert all(item["session"] == partial["provenance"]["session_id"] for item in requests)
    assert all(item["arguments"]["incident_id"] == "INC-DEMO-001" for item in requests)
    assert all(item["arguments"]["as_of"] == partial["provenance"]["snapshot_cutoff"] for item in requests)


class ScriptedRunnerActions(DeterministicProvider):
    """Offline decisions; fixture reservations are not real provider charges."""

    name = "scripted_outcome_integrity_fixture"

    def __init__(self, actions):
        self.actions = iter(actions)
        self.decisions = 0
        self.assessments = 0
        self.execution_receipts = []
        self.inputs = []
        self.closed = False
        self.client = self

    def enable_budget(self, maximum, *, reserved_spend, reservation_callback):
        assert maximum == 2 and reserved_spend == 0
        self.reserve = reservation_callback

    async def next_action(self, incident, schemas, observations, evidence):
        self.decisions += 1
        self.inputs.append(
            copy.deepcopy({"schemas": schemas, "observations": observations, "evidence": evidence})
        )
        self.reserve(FIXTURE_RESERVATION * self.decisions)
        self.execution_receipts.append(
            {
                "provider": self.name,
                "status": "scripted_offline_fixture",
                "request_started": False,
                "input_tokens_ceiling": FIXTURE_INPUT_CEILING,
                "reserved_cost_usd": str(FIXTURE_RESERVATION),
                "usage": {
                    "input_tokens": None,
                    "output_tokens": None,
                    "total_tokens": None,
                    "estimated_cost_usd": None,
                },
                "fixture_only": True,
            }
        )
        request = next(self.actions, None)
        return AdaptiveDecision.model_validate(
            {"action": "tool" if request else "assess", "request": request}
        ), {}

    async def assess(self, incident, evidence):
        self.assessments += 1
        return await super().assess(incident, evidence)

    async def close(self):
        self.closed = True


def owned_runner_path(resources, provider, monkeypatch, tmp_path):
    """Keep real runner/Store/MCP; replace only live-provider and resource ownership."""
    _, database_url, url, _, environment = resources
    marker = tmp_path / "outcome-owned-mcp.pid"
    bootstrap = tmp_path / "outcome_owned_mcp.py"
    bootstrap.write_text(
        OFFLINE_CHILD_BOUNDARY + "\nimport os\nfrom pathlib import Path\n"
        "from creditops_mcp.server import HttpDiagnosticClient, create_server\n"
        f"Path({str(marker)!r}).write_text(str(os.getpid()), encoding='utf-8')\n"
        "create_server(HttpDiagnosticClient(os.environ['CREDITOPS_API_URL'], os.environ['MCP_DEMO_SESSION'], incident_id=os.environ['MCP_INCIDENT_ID'], as_of=os.environ['MCP_AS_OF'])).run()\n",
        encoding="utf-8",
    )
    adapters, closed_stores = [], []

    class OwnedRunnerStore(Store):
        async def close(self):
            await super().close()
            closed_stores.append(True)

    def owned_resources(configuration):
        assert configuration.database_url == database_url
        assert configuration.mcp_api_url == url and url.startswith("http://127.0.0.1:")
        assert configuration.embeddings_enabled is False
        return {"database": "isolated synthetic SQLite fixture", "api": url, "embeddings_enabled": False}

    def real_owned_mcp(session, incident, cutoff):
        parameters = StdioServerParameters(
            command=sys.executable,
            args=[str(bootstrap)],
            cwd=PROJECT_ROOT,
            env={
                **environment,
                "CREDITOPS_API_URL": url,
                "MCP_DEMO_SESSION": session,
                "MCP_INCIDENT_ID": incident,
                "MCP_AS_OF": cutoff,
            },
        )
        adapter = MCPDiagnosticClient(session, incident, cutoff, client=Client(parameters, cache=None))
        adapters.append(adapter)
        return adapter

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("MCP_API_URL", url)
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "false")
    monkeypatch.setattr(runner, "validate_local_resources", owned_resources)
    monkeypatch.setattr(runner, "Store", OwnedRunnerStore)
    monkeypatch.setattr(runner, "source_commit", lambda: "scripted-offline-source-fixture")
    monkeypatch.setattr(runner.subprocess, "check_output", lambda *args, **kwargs: "")
    monkeypatch.setattr(runner, "create_provider", lambda name: provider)
    monkeypatch.setattr(investigator, "MCPDiagnosticClient", real_owned_mcp)
    output = tmp_path / "scripted-outcome-receipts"
    arguments = runner.parse_args(
        [
            "--provider",
            "openai",
            "--model",
            "gpt-5.4-mini-2026-03-17",
            "--case-count",
            "1",
            "--max-tool-calls",
            "12",
            "--max-provider-turns",
            "12",
            "--max-spend-usd",
            "2",
            "--timeout-seconds",
            "30",
            "--provider-timeout-seconds",
            "5",
            "--diagnostic-timeout-seconds",
            "10",
            "--total-timeout-seconds",
            "33",
            "--input-price-ceiling",
            "0.75",
            "--output-price-ceiling",
            "4.50",
            "--experiment-id",
            str(uuid4()),
            "--stage",
            "first",
            "--execute-paid",
            "--output-directory",
            str(output),
        ]
    )
    return arguments, output, adapters, marker, closed_stores


async def test_actual_runner_duplicate_topology_stops_without_substitute_assessment(
    isolated_failure_api, monkeypatch, tmp_path
):
    """Catch strict duplicate guards producing a complete deterministic fallback."""
    provider = ScriptedRunnerActions([{"name": "get_service_topology"}, {"name": "get_service_topology"}])
    arguments, output, adapters, marker, closed_stores = owned_runner_path(
        isolated_failure_api, provider, monkeypatch, tmp_path
    )
    with pytest.raises((DiagnosticClientError, ValueError)) as failure:
        await runner.run(arguments)
    receipt = json.loads(next(output.glob("run-*.json")).read_text(encoding="utf-8"))
    ledger = json.loads(next(output.glob("experiment-*.json")).read_text(encoding="utf-8"))
    partial = receipt["results"][0]
    assert partial["status"] == "failed"
    assert isinstance(failure.value, DiagnosticClientError)
    assert receipt["execution"] == ledger["state"] == "STOPPED"
    assert provider.decisions == 2 and provider.assessments == 0
    assert partial["assessment"] is None and partial["provider_proposal"] is None
    assert partial["validation_outcome"]["status"] == "not_validated"
    assert partial["validation_outcome"]["provider_response"] == "not_requested_due_to_guard_stop"
    assert partial["validation_outcome"]["rejected_fields"] == []
    assert partial["provenance"]["action_rejections"] == [
        {
            "stage": "investigation_guard",
            "reason": "duplicate_diagnostic_request",
            "provider_turn": 2,
            "mcp_dispatched": False,
            "action": {"name": "get_service_topology", "arguments": {}},
        }
    ]
    assert partial["provenance"]["tool_calls"] == 2
    assert partial["provenance"]["provider_turns"] == 2
    assert [step["tool"] for step in partial["steps"]] == ["get_incident", "get_service_topology"]
    assert all(step["status"] == "complete" for step in partial["steps"])
    assert {item["id"] for item in partial["evidence"]} == {"INC-DEMO-001", "TOPOLOGY-001"}
    assert (
        Decimal(receipt["reserved_spend_usd"])
        == Decimal(ledger["reserved_spend_usd"])
        == FIXTURE_RESERVATION * 2
    )
    assert receipt["provider_calls"] == partial["provider_calls"] == provider.execution_receipts
    assert receipt["estimated_cost_usd"] is None and receipt["known_cost_subtotal_usd"] is None
    store, _, _, requests_path, _ = isolated_failure_api
    saved = await store.get_investigation(partial["provenance"]["session_id"], partial["id"])
    assert saved["status"] == "failed" and saved["assessment"] is None
    requests = [json.loads(line) for line in requests_path.read_text(encoding="utf-8").splitlines()]
    assert [item["path"] for item in requests] == [
        "/api/diagnostics/get_incident",
        "/api/diagnostics/get_service_topology",
    ]
    assert all(item["session"] == partial["provenance"]["session_id"] for item in requests)
    assert all(item["arguments"]["incident_id"] == "INC-DEMO-001" for item in requests)
    assert all(item["arguments"]["as_of"] == partial["provenance"]["snapshot_cutoff"] for item in requests)
    assert len(adapters) == 1 and adapters[0]._entered is False
    assert provider.closed and closed_stores == [True]
    assert marker.exists() and not process_is_running(int(marker.read_text(encoding="utf-8")))
    assert not list(output.glob("*.lock"))


async def test_actual_mcp_retains_topology_and_allows_distinct_broader_log_query(
    isolated_failure_api, monkeypatch, tmp_path
):
    """Topology exhaustion must not remove parameterized tools or prior evidence."""
    provider = ScriptedRunnerActions(
        [
            {"name": "get_service_topology"},
            {"name": "search_logs", "q": "rfq response OR timeout"},
            {"name": "search_logs", "q": ""},
        ]
    )
    arguments, output, adapters, marker, closed_stores = owned_runner_path(
        isolated_failure_api, provider, monkeypatch, tmp_path
    )
    receipt = await runner.run(arguments)
    result = receipt["results"][0]
    assert receipt["execution"] == "COMPLETED_APPROVED_CASES"
    assert result["status"] == "complete"
    assert provider.decisions == 4 and provider.assessments == 1
    assert "get_service_topology" in {item["name"] for item in provider.inputs[0]["schemas"]}
    for current in provider.inputs[1:]:
        assert {item["name"] for item in current["schemas"]} == {
            "search_logs",
            "query_metrics",
            "get_recent_deployments",
            "find_similar_incidents",
            "search_runbooks",
            "inspect_kafka_lag",
            "inspect_fix_session",
            "inspect_database_health",
        }
        assert "TOPOLOGY-001" in {item["id"] for item in current["evidence"]}
    assert provider.inputs[2]["observations"][-1]["tool"] == "search_logs"
    assert provider.inputs[2]["observations"][-1]["status"] == "complete"
    assert provider.inputs[2]["observations"][-1]["evidence_ids"] == []
    assert provider.inputs[3]["observations"][-1]["evidence_ids"]
    assert result["provenance"]["action_rejections"] == []
    assert result["provenance"]["tool_calls"] == 4
    assert [step["tool"] for step in result["steps"]] == [
        "get_incident",
        "get_service_topology",
        "search_logs",
        "search_logs",
        "assessment_validation",
    ]
    assert result["steps"][2]["safe_arguments"] == {"q": "rfq response OR timeout"}
    assert result["steps"][3]["safe_arguments"] == {"q": ""}
    assert result["steps"][2]["evidence_ids"] == [] and result["steps"][3]["evidence_ids"]
    assert {item["id"] for item in result["evidence"]} >= {"INC-DEMO-001", "TOPOLOGY-001"}
    assert result["provenance"]["model_called"] is False
    assert result["provenance"]["assessment_source"]["kind"] == "scripted_provider"
    _, _, _, requests_path, _ = isolated_failure_api
    requests = [json.loads(line) for line in requests_path.read_text(encoding="utf-8").splitlines()]
    assert [item["path"] for item in requests] == [
        "/api/diagnostics/get_incident",
        "/api/diagnostics/get_service_topology",
        "/api/diagnostics/search_logs",
        "/api/diagnostics/search_logs",
    ]
    assert requests[2]["arguments"]["q"] == "rfq response OR timeout"
    assert requests[3]["arguments"]["q"] == ""
    assert all(item["session"] == result["provenance"]["session_id"] for item in requests)
    assert all(item["arguments"]["incident_id"] == "INC-DEMO-001" for item in requests)
    assert all(item["arguments"]["as_of"] == result["provenance"]["snapshot_cutoff"] for item in requests)
    assert len(adapters) == 1 and adapters[0]._entered is False
    assert provider.closed and closed_stores == [True]
    assert marker.exists() and not process_is_running(int(marker.read_text(encoding="utf-8")))
    assert not list(output.glob("*.lock"))
