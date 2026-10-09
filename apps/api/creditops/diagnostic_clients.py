"""Application-owned diagnostic scope and official-SDK MCP transport.

The model chooses a local allowlisted tool and bounded filters only. It never
chooses the API URL, transport, tenant/session, incident, snapshot, or limits.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from importlib.metadata import version
from typing import Any, Protocol
from uuid import UUID

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from pydantic import TypeAdapter, ValidationError

from .models import Evidence
from .security import sanitize
from .settings import PROJECT_ROOT, Settings
from .tool_contracts import (
    FILTERS,
    MCP_ARGUMENTS,
    MODEL_TOOLS,
    Aggregation,
    Severity,
    model_catalog_entry,
)
from .tools import ALLOWED_TOOLS, DiagnosticTools, canonical_time

MAX_RESULT_BYTES = 1_048_576


def _canonical_schema(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _canonical_schema(item)
            for key, item in value.items()
            if key not in {"title", "description", "default"}
        }
    if isinstance(value, list):
        return [_canonical_schema(item) for item in value]
    return value


def verify_tool_schema(name: str, input_schema: dict, output_schema: dict) -> None:
    # These are local installed contract types, never remotely supplied code.
    # Compare semantics, ignoring documentation/default presentation only.
    from creditops_mcp.server import DiagnosticResult, Identifier, Query, ResultLimit, TimeFilter

    types = {
        "incident_id": Identifier if name == "get_incident" else Identifier | None,
        "service": Identifier | None,
        "q": Query,
        "limit": ResultLimit,
        "severity": Severity | None,
        "trace_id": Identifier | None,
        "start": TimeFilter | None,
        "end": TimeFilter | None,
        "metric": Identifier | None,
        "aggregation": Aggregation | None,
    }
    fields = FILTERS[name] | {"incident_id"} | (set() if name == "get_incident" else {"limit"})
    expected = {
        "type": "object",
        "properties": {key: TypeAdapter(types[key]).json_schema() for key in fields},
    }
    if name == "get_incident":
        expected["required"] = ["incident_id"]
    if _canonical_schema(input_schema) != _canonical_schema(expected):
        raise ValueError(
            "Diagnostic input types, bounds or required fields differ from the installed contract"
        )
    if _canonical_schema(output_schema) != _canonical_schema(DiagnosticResult.model_json_schema()):
        raise ValueError("Structured Evidence output differs from the installed contract")


class DiagnosticClientError(RuntimeError):
    """A bounded tool request failed; it is not healthy or empty telemetry."""


class DiagnosticConnectionError(DiagnosticClientError):
    """Transport or schema verification failed. Never fall back to direct."""


class DiagnosticClient(Protocol):
    transport: str
    schemas: list[dict[str, Any]]
    provenance: dict[str, Any]

    async def __aenter__(self) -> DiagnosticClient: ...
    async def __aexit__(self, *args: Any) -> None: ...
    async def call(self, name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]: ...


def safe_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name not in ALLOWED_TOOLS or not isinstance(arguments, dict) or set(arguments) - FILTERS[name]:
        raise DiagnosticClientError("Tool or arguments are outside the local diagnostic allowlist")
    try:
        checked = MCP_ARGUMENTS[name].model_validate(arguments)
        start, end = getattr(checked, "start", None), getattr(checked, "end", None)
        if start and end and _time(start) > _time(end):
            raise ValueError("Invalid time range")
        for value in (start, end):
            canonical_time(value)
    except (ValidationError, ValueError) as error:
        raise DiagnosticClientError("Invalid bounded diagnostic arguments") from error
    # Omitted/null supported fields mean the MCP function's existing default.
    # This happens only after per-tool validation; unknown fields are not dropped.
    return sanitize(checked.model_dump(exclude_none=True))


def _time(value: str) -> datetime:
    return datetime.fromisoformat(canonical_time(value).replace("Z", "+00:00"))


def validate_items(items: Any, cutoff: str) -> list[dict[str, Any]]:
    if not isinstance(items, list) or len(items) > 50:
        raise DiagnosticClientError("Diagnostic result exceeded the evidence count bound")
    if len(json.dumps(items, ensure_ascii=True, allow_nan=False).encode()) > MAX_RESULT_BYTES:
        raise DiagnosticClientError("Diagnostic result exceeded the response byte bound")
    try:
        rows = [Evidence.model_validate(sanitize(item)).model_dump(mode="json") for item in items]
        if any(_time(item["timestamp"]) > _time(cutoff) for item in rows):
            raise ValueError("Future evidence")
    except (ValidationError, ValueError, TypeError) as error:
        raise DiagnosticClientError("Diagnostic result schema or snapshot cutoff was invalid") from error
    return rows


class DirectDiagnosticClient:
    """Explicit direct adapter for local evaluation/tests; never reports MCP."""

    transport = "direct"

    def __init__(self, store: Any, session_id: str, incident_id: str, as_of: str):
        self.tools = DiagnosticTools(store, session_id, as_of=as_of)
        self.incident_id, self.as_of = incident_id, canonical_time(as_of)
        self.schemas = [model_catalog_entry(name) for name in sorted(MODEL_TOOLS)]
        self.provenance = {
            "transport": self.transport,
            "tool_schema_verified": True,
            "snapshot_cutoff": self.as_of,
        }

    async def __aenter__(self) -> DirectDiagnosticClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def call(self, name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        arguments = safe_arguments(name, arguments)
        try:
            rows = await self.tools.call(
                name,
                {**arguments, "incident_id": self.incident_id, "limit": 1 if name == "get_incident" else 50},
            )
            return validate_items([item.model_dump(mode="json") for item in rows], self.as_of)
        except (ValueError, RuntimeError) as error:
            raise DiagnosticClientError("Direct diagnostic tool failed; human review required") from error


class MCPDiagnosticClient:
    """Owned stdio subprocess with fixed API callback, scope and official lifecycle."""

    def __init__(self, session_id: str, incident_id: str, as_of: str, *, client: Client | None = None):
        self.session_id = str(UUID(session_id))
        self.incident_id, self.as_of = incident_id, canonical_time(as_of)
        self.timeout = Settings().diagnostic_timeout_seconds
        if client is None:
            configuration = Settings()
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "creditops_mcp.server"],
                cwd=PROJECT_ROOT,
                env={
                    "PYTHONPATH": os.pathsep.join(
                        [str(PROJECT_ROOT / "apps/api"), str(PROJECT_ROOT / "apps/mcp")]
                    ),
                    "CREDITOPS_API_URL": configuration.mcp_api_url,
                    "MCP_DEMO_SESSION": self.session_id,
                    "MCP_INCIDENT_ID": self.incident_id,
                    "MCP_AS_OF": self.as_of,
                    "PYTHONUNBUFFERED": "1",
                },
            )
            client = Client(parameters, read_timeout_seconds=self.timeout, cache=None)
        self.client = client
        self.transport = (
            "mcp_stdio" if isinstance(client.server, StdioServerParameters) else "mcp_inprocess_test"
        )
        self.schemas: list[dict[str, Any]] = []
        self._entered = False
        self.provenance = {
            "transport": self.transport,
            "tool_schema_verified": False,
            "snapshot_cutoff": self.as_of,
            "mcp_sdk_version": version("mcp"),
        }

    async def __aenter__(self) -> MCPDiagnosticClient:
        try:
            # Keep SDK context entry/exit in the same task: anyio cancellation scopes
            # belong to that task. asyncio.timeout does not spawn a different task.
            async with asyncio.timeout(self.timeout):
                await self.client.__aenter__()
                self._entered = True
                discovered = (await self.client.list_tools()).tools
                if len(discovered) > 50:
                    raise ValueError("Too many advertised tools")
                tools = {tool.name: tool for tool in discovered}
                if not ALLOWED_TOOLS <= tools.keys():
                    raise ValueError("Missing expected tool")
                for name in sorted(ALLOWED_TOOLS):
                    tool = tools[name]
                    schema = tool.input_schema
                    props = schema.get("properties", {})
                    expected = (
                        FILTERS[name] | {"incident_id"} | (set() if name == "get_incident" else {"limit"})
                    )
                    if (
                        set(props) != expected
                        or not tool.annotations
                        or tool.annotations.read_only_hint is not True
                    ):
                        raise ValueError("Unexpected tool schema or mutability")
                    if name != "get_incident" and (
                        props["limit"].get("maximum") != 50
                        or props["limit"].get("minimum") != 1
                        or props["limit"].get("type") != "integer"
                    ):
                        raise ValueError("Missing result bounds")
                    output = tool.output_schema or {}
                    verify_tool_schema(name, schema, output)
                    items = output.get("properties", {}).get("items", {})
                    if items.get("type") != "array" or items.get("maxItems") != 50:
                        raise ValueError("Missing structured evidence output")
                    if name in MODEL_TOOLS:
                        self.schemas.append(model_catalog_entry(name))
            self.provenance["tool_schema_verified"] = True
            self.provenance["verified_tools"] = sorted(ALLOWED_TOOLS)
            self.provenance["protocol_version"] = self.client.protocol_version
            self.provenance["server_name"] = self.client.server_info.name if self.client.server_info else None
            return self
        except BaseException as error:
            if self._entered:
                await self.client.__aexit__(None, None, None)
                self._entered = False
            if isinstance(error, asyncio.CancelledError):
                raise
            raise DiagnosticConnectionError(
                "MCP connection or diagnostic schema verification failed; no direct fallback"
            ) from error

    async def __aexit__(self, *args: Any) -> None:
        self._entered = False
        # Close the transport without injecting application exceptions into the
        # SDK's nested anyio task groups (which would wrap them in ExceptionGroup).
        # The caller's original exception then propagates unchanged.
        try:
            await self.client.__aexit__(None, None, None)
        except Exception as error:
            if args and args[0] is not None:
                return
            raise DiagnosticConnectionError(
                "MCP connection cleanup failed; investigation unavailable"
            ) from error

    async def call(self, name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        if not self._entered:
            raise DiagnosticConnectionError("MCP connection is closed; no direct fallback")
        arguments = safe_arguments(name, arguments)
        scoped = {**arguments, "incident_id": self.incident_id}
        if name != "get_incident":
            scoped["limit"] = 50
        try:
            async with asyncio.timeout(self.timeout):
                result = await self.client.call_tool(name, scoped)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise DiagnosticConnectionError("MCP protocol connection failed; no direct fallback") from error
        if result.is_error:
            raise DiagnosticClientError("MCP diagnostic tool failed; no healthy result was returned")
        payload = result.structured_content
        if (
            not isinstance(payload, dict)
            or payload.get("untrusted_telemetry") is not True
            or set(payload) - {"items", "untrusted_telemetry", "limitation"}
        ):
            raise DiagnosticClientError("MCP returned an invalid structured diagnostic envelope")
        return validate_items(payload.get("items"), self.as_of)
