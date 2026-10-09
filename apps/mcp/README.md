# CreditOps AI diagnostic MCP server

This is a real Model Context Protocol server using the official Python `mcp` SDK. The implementation uses the current `MCPServer` API, not a homegrown JSON-RPC imitation. See the [official SDK documentation](https://py.sdk.modelcontextprotocol.io/).

CreditOps AI is an independent portfolio project using entirely synthetic data. It is not affiliated with or connected to any trading venue, broker, financial institution, or employer.

CreditOps AI intentionally exposes diagnostic capabilities only. AI recommendations are advisory. Production mutation tools are excluded by design.

## Local stdio

Install the root Python project, start the API, and run:

```sh
python -m creditops_mcp.server
```

The server writes protocol messages to stdout. Logs belong on stderr. It does not need an AI provider API key.

Example compatible client configuration; replace paths for your checkout:

```json
{
  "mcpServers": {
    "creditops-diagnostics": {
      "command": "/absolute/path/creditops-ai/.venv/bin/python",
      "args": ["-m", "creditops_mcp.server"],
      "cwd": "/absolute/path/creditops-ai",
      "env": {
        "CREDITOPS_API_URL": "http://127.0.0.1:8000",
        "MCP_DEMO_SESSION": "00000000-0000-0000-0000-000000000001"
      }
    }
  }
}
```

On Windows the Python executable is `.venv\\Scripts\\python.exe`. Installation (`pip install -e .`) makes the package importable without a custom `PYTHONPATH`.

Demo runs are isolated by session UUID. Set `MCP_DEMO_SESSION` to the dashboard's `creditops-demo-session` localStorage UUID to inspect that active run, or start a dedicated synthetic run through the developer REST API with the same `X-Demo-Session` header. Starting and resetting a demo remain deliberate API/UI actions and are never MCP tools.

## Tool contract

The complete allowlist is:

| Tool | Diagnostic evidence |
| --- | --- |
| `get_incident` | Incident metadata and impact |
| `search_logs` | Sanitized logs with service, severity, trace, text and time filters |
| `query_metrics` | Service metric evidence and time filters |
| `get_service_topology` | Service dependencies |
| `get_recent_deployments` | Application change records |
| `find_similar_incidents` | Historical incidents and match explanations |
| `search_runbooks` | Advisory runbook Markdown |
| `inspect_kafka_lag` | Synthetic Kafka consumer health |
| `inspect_fix_session` | Fictional FIX session diagnostics |
| `inspect_database_health` | Connection-pool and database telemetry |

Inputs are JSON schemas derived from typed Python signatures. Result limits must be integers between 1 and 50. Query strings, IDs and filters have explicit length bounds. Results are structured `{items, untrusted_telemetry, limitation}` objects; each item follows the same Evidence model used by the REST API and investigator. All data comes from fixed `GET /api/diagnostics/{allowlisted_name}` routes. There is no writable database connection, shell runner, cloud SDK, mutation route or model-provider credential in this server.

The bridge applies the API's shared redaction helper again, caps upstream responses at 1 MiB, caps returned evidence at the requested limit, refuses redirects, and uses ten-second network timeouts. API error bodies do not reach the client. Prompt-injection text remains labeled telemetry; it never changes the tool allowlist or triggers commands.

## Private Streamable HTTP

Streamable HTTP is available for a private compatible client with manually configured bearer authentication:

```sh
python -m creditops_mcp.server --transport streamable-http --port 8001
```

Set `MCP_HTTP_TOKEN` to a random server-only secret of at least 32 characters before launch. Requests need `Authorization: Bearer <configured-secret>`. Missing/short token configuration prevents startup. This is a minimal private demo control, not a full OAuth authorization server or automatic OAuth client-discovery implementation.

The listener defaults to `127.0.0.1`. If hosted behind HTTPS, supply `--host 0.0.0.0` and explicitly set `MCP_ALLOWED_HOSTS` to the dedicated endpoint hostname (for example `diagnostics.example.com`). DNS-rebinding checks stay enabled. The endpoint is stateless, has a 64 KiB request-body limit, and admits 120 authenticated HTTP requests per minute per process. Do not expose the local Grafana, PostgreSQL or Kafka ports publicly. Multi-replica usage would require a shared authorization/rate-limit store and a real OAuth provider.

## Verification

The application mode `MCP_DEMO` opens an official `Client` with `StdioServerParameters`, discovers/verifies all ten contracts and sends every diagnostic through this server. The application binds `MCP_INCIDENT_ID`, `MCP_AS_OF` and its session; providers cannot override them. `LIVE_AI` uses the same client with a protected adaptive provider, but no paid calls were executed in this pass. Original offline evaluation uses an explicit direct adapter and replay retains that generating provenance.

The adaptive worker awaits protocol I/O while this bridge calls back into the same asynchronous API. `test_investigation_protocol.py` launches this actual arrangement for all three incidents, compares returned evidence and forces child exit to ensure failure cannot become a successful MCP receipt. Scripted-provider tests separately prove different follow-up tools after different results. These are transport/orchestration proofs, not real-model intelligence measurements.

```sh
python -m pytest apps/mcp/tests
```

Tests use the official SDK client and assert the exact diagnostic allowlist, rejected mutation tools, input bounds, GET-only routes, evidence redaction, result limits, oversized upstream rejection, and fail-closed HTTP authentication. The HTTP bridge keeps the MCP client on the same evidence and safety boundary as the application.
