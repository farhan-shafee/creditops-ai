# CreditOps AI design

The supplied project brief is the binding specification. The user explicitly authorized continuous implementation, validation, commit, and push, so the workflow's additional design approval pauses are superseded.

## Intent
Build an independent portfolio operations product that lets a hiring manager run three synthetic trading incidents, observe telemetry, investigate with read-only tools, inspect evidence, and inspect reproducible evaluations. No production system, institution, or customer is connected. No measured human MTTR claim is permitted.

## Selected architecture
Next.js/TypeScript operations console consumes FastAPI through a same-origin server proxy. FastAPI uses SQLAlchemy persistence with PostgreSQL/pgvector in Docker and a SQLite development fallback. The synthetic simulator stores immutable evidence and deterministic timelines. Each browser session owns its demo runs. Read-only diagnostic tools are shared by the investigator and official MCP SDK server. A protected LIVE_AI mode uses official OpenAI Responses or Anthropic Messages APIs. REPLAY loads artifacts produced by the identical collection/validation pipeline with an explicitly labeled deterministic assessment provider; live model benchmarks remain unavailable until actually run.

The public replay path requires no keys, paid Kafka, or external observability. Docker adds real Redpanda publication/consumption, PostgreSQL, Prometheus, and Grafana. Optional embeddings use pgvector; lexical retrieval works without keys. Every assertion references returned evidence; unknown citations invalidate output and insufficient evidence triggers human review.

## Boundaries
- `apps/api/creditops`: settings, Pydantic models, SQLAlchemy persistence, synthetic data, simulator, diagnostic tools, REST APIs, investigator, providers, evaluation.
- `apps/web`: polished responsive console, typed API client, SSE investigation events, evidence drawer, dashboards and documentation views.
- `apps/mcp`: official typed MCPServer diagnostic server using HTTP API rather than a second database owner.
- `data`: seeded synthetic evidence, runbooks, labeled evaluations.
- `infra`: disposable local infrastructure, migrations, observability and cloud deployment configuration.

## Safety and failure behavior
No agent mutation tool exists. Telemetry is untrusted, bounded, sanitized data. Live calls require server-side admin authorization, request limits, timeouts, and a run budget. Session scope protects demo state. Replay corruption is surfaced, not silently replaced by fake model results. Operational health reports actual dependencies. External deployments are performed only with existing authorized credentials; otherwise configuration and exact commands are delivered.

## Verification
Direct tests cover isolation, evidence integrity, input bounds, redaction, injection data handling, provider failures, abstention, replay provenance, evaluation arithmetic, MCP registration, and no mutation tools. Playwright exercises all scenarios and evidence inspection. Visual QA covers 1440, 1024, 768, 390 and 320 pixels. Scan results and any unavailable checks are recorded honestly.
