# CreditOps AI

**AI-assisted incident intelligence for synthetic electronic credit trading systems.**

CreditOps AI correlates logs, metrics, Kafka consumer state, FIX sessions, database health, service dependencies, application changes, historical incidents and runbooks into an evidence-backed investigation. It demonstrates the diagnosis, observability and safety boundaries a Production Support, SRE or AI Enablement engineer needs to design.

> CreditOps AI is an independent portfolio project using entirely synthetic data. It is not affiliated with or connected to any trading venue, broker, financial institution, or employer.

![CreditOps AI operations console](docs/screenshots/overview.png)

## Five-minute demo

1. Open Overview and select **Run Incident Demo**.
2. Choose **Kafka pricing lag**, **FIX connectivity**, or **Database pool exhaustion**, then **Run Incident**.
3. Observe changing telemetry on a clearly labeled simulated clock: one real second represents twelve synthetic seconds.
4. Open the incident and select **MCP · adaptive deterministic** to execute new read-only checks through the real MCP connection. **Replay · deterministic provider** plays a recorded complete scenario snapshot.
5. Review the **Business impact / affected requests** timeline, supported failure condition, candidate triggers and unknowns. Click evidence IDs to inspect the returned records.
6. Open **Evaluations** to inspect generated results and their limitations. Reset the scenario and repeat.

Replay artifacts are produced by the direct diagnostic collection and validation pipeline, with original timestamps and a complete-snapshot cutoff. The keyless MCP mode makes fresh protocol calls and adapts using deterministic rules. Neither path calls a model. Protected `LIVE_AI` implements the same bounded adaptive loop through official OpenAI or Anthropic SDKs; live provider execution is **NOT RUN**, and live-model quality is **UNVERIFIED**.

![Event-derived synthetic RFQ and order impact](docs/screenshots/second-pass-impact-fix-connectivity.png)

[Watch the recorded demo](docs/screenshots/demo.webm) or follow the [two-minute interview script](docs/DEMO_SCRIPT.md).

## The incidents

| Scenario | Independent observations | Probable failure domain |
|---|---|---|
| RFQ latency | Pricing consumer backlog, stale prices, quote age and upstream latency; healthy negative controls | Pricing service / Kafka consumer backlog |
| Acknowledgement delays | FIX heartbeat failures, reconnects, sequence gaps, uncertain synthetic orders; healthy DB/Kafka | FIX session instability |
| Request timeouts | Saturated connection pool, waiters and pool timeout logs, normal CPU | Connection pool exhaustion; a relevant preceding release is only a candidate trigger |

Twelve further labeled cases include stale market data, risk dependency timeouts, CPU pressure and three deliberately insufficient-evidence cases. Evaluation labels never enter diagnostic tools or model context.

## Architecture

```mermaid
flowchart LR
  User[Human operator] --> Web[Next.js operations console]
  Web --> API[FastAPI session-scoped API]
  API --> Agent[Bounded AI investigation]
  Agent --> Client[Official MCP Client: owned stdio connection]
  Client --> MCP[Diagnostic-only MCP server]
  MCP --> Callback[Fixed GET callback into async API]
  Callback --> Tools[Read-only diagnostic allowlist]
  Tools --> DB[(PostgreSQL + optional pgvector)]
  API --> Sim[Synthetic clock and FIX simulator]
  Sim --> Kafka[Local Redpanda]
  Sim --> DB
  API --> Prom[Prometheus]
  Prom --> Grafana[Provisioned Grafana]
  Tools --> Retrieval[Runbooks and historical retrieval]
```

The MCP-backed worker uses the official client, discovers and checks schemas, then receives diagnostic evidence through an owned stdio server and fixed API callback. Local evaluation explicitly uses a direct adapter. There is no silent transport fallback. SQLite supports lightweight development; Docker exercises PostgreSQL and a real Kafka-compatible broker. The [architecture document](docs/ARCHITECTURE.md) describes the boundaries.

Three fictional corporate bonds and event-derived RFQ/quote/order timelines connect telemetry to affected requests. Par amounts and clean prices use decimal strings with explicit currency and per-100-par units. They are not revenue, P&L or settlement values. Missing FIX acknowledgements remain PENDING/UNKNOWN until reconciled; the application never infers execution or creates a replacement order.

## Start locally

Requirements: Python 3.12+, Node.js 22+, pnpm, Git. Docker is optional for the lightweight path.

```sh
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
pnpm install --frozen-lockfile
python -m alembic upgrade head
python scripts/seed.py
python scripts/evaluate.py
python scripts/robustness.py
pnpm dev
```

Open [the console](http://localhost:3000), [API health](http://localhost:8000/health) and [OpenAPI](http://localhost:8000/docs). `pnpm dev` starts both servers. If needed, start them separately with `python -m uvicorn creditops.main:app --host 127.0.0.1 --port 8000` and `pnpm --filter @creditops/web dev`.

On Windows without activating the environment, replace `python` with `.venv\Scripts\python.exe`. Copy `.env.example` to `.env` for local configuration. No AI credentials are required for replay.

## Full local infrastructure

```sh
docker compose -f infra/docker/compose.yml up --build -d
docker compose -f infra/docker/compose.yml ps
```

| Component | Isolated local URL |
|---|---|
| Web | http://localhost:13000 |
| API / OpenAPI | http://localhost:18000/docs |
| PostgreSQL / pgvector | localhost:15432 |
| Redpanda Kafka | localhost:19092 |
| Prometheus | http://localhost:19090 |
| Grafana | http://localhost:13001 |

All host ports bind to loopback. Disposable local credentials in Compose are intentionally fictional and must be replaced for hosting. `docker compose ... down` stops the stack while preserving its named volumes. No real FIX connection is created.

## Developer commands

| Command | Purpose |
|---|---|
| `pnpm dev` / `make dev` | Start API and console |
| `pnpm test` / `make test` | Python and frontend unit tests |
| `pnpm lint` / `make lint` | Python and frontend lint |
| `pnpm typecheck` | Strict frontend TypeScript |
| `pnpm test:dependencies` | Scoped lint dependency compatibility and active rule checks |
| `pnpm test:lifecycle` | Real Playwright/Linux launcher shutdown and descendant cleanup; explicit Unix-proof skip on Windows |
| `pnpm e2e` | Playwright all-scenario and responsive checks |
| `make seed` | Idempotent seed |
| `make eval` | Generate the unchanged 15-case benchmark and versioned replay artifacts |
| `python scripts/robustness.py` | Separate 13-case synthetic robustness/regression report |
| `make reset-demo` | Reset a selected local demo session |

Python packages are pinned in `requirements.lock`; pnpm dependencies are pinned in `pnpm-lock.yaml`. CI runs tests, lint, typecheck, E2E, dependency audits, Bandit and secret scanning.

## Why production mutation is intentionally excluded

CreditOps AI intentionally exposes diagnostic capabilities only. AI recommendations are advisory. Production mutation tools are excluded by design.

AI accelerates evidence collection and diagnosis while human engineers retain operational authority. There is no restart, rollback, scaling, record deletion, shell execution, configuration change or FIX termination tool. Read-only MCP registration and attempted forbidden actions are tested. Runbook commands are reference text and are never automatically executed. Every RCA is **Draft — human review required**.

## Engineering decisions

- **Evidence-grounded investigation:** structured assessments are checked against returned evidence IDs and evidence types. Unknown references invalidate output. Insufficient corroboration causes abstention and escalation.
- **Retrieval:** bounded diagnostic queries and explainable lexical ranking select context rather than dumping entire log stores into a model. Optional pgvector retrieval is available when configured.
- **Replay for public demos:** persisted pipeline artifacts cap spending and work without keys. Replay provenance, generation timestamps and deterministic assessment are visible.
- **Local Kafka, inexpensive cloud:** Redpanda supports real event publication/consumption locally. The public path uses persisted synthetic telemetry without a paid Kafka cluster.
- **Provider abstraction:** official SDKs, server-side configuration, validated tool plans, structured output, request deadlines and no automatic retries that could multiply costs.
- **Support and uncertainty:** scores are uncalibrated rule support, not probabilities. Every assessment requires human review. Valid references do not establish causality; the known-domain rule gate is not a general factuality verifier.

See [tradeoffs](docs/TRADEOFFS.md) for institutional-scale limitations.

## Evaluation methodology

The original 15-case labels remain unchanged, and their original results are preserved under [baseline-v1](artifacts/eval/baseline-v1/latest.md). Current output measures literal label accuracy, evidence recall, invalid references, abstention, escalation and latency. Legacy DB labels include an unsupported causal qualifier and expect some drafts to omit human review, so the corrected implementation reports those mismatches instead of relabeling for a perfect score. The legacy `hallucinated_evidence_count` field means invalid IDs only.

Actual results are in [generated JSON](artifacts/eval/latest.json), [generated report](artifacts/eval/latest.md) and the Evaluations page. These are small, in-distribution fixtures designed alongside the rules. They do not prove generalization, guaranteed AI accuracy, actual customer usage or real production MTTR reduction.

The separate [13-case robustness report](artifacts/robustness/latest.md) checks declared condition/trigger/uncertainty expectations, including missing and contradictory evidence. It is developer-authored and not independently held out. Scripted adaptation, real MCP transport and offline provider-SDK tests have separate receipts in the [second-pass report](docs/SECOND_PASS_REPORT.md). Zero invalid references does not mean zero hallucinations.

`scripts/evaluate.py` is offline only. Prepare a future live check with `python scripts/verify_live.py --provider openai --model MODEL --case-count 1 --max-tool-calls 8 --max-provider-turns 8 --max-spend-usd 0.25 --timeout-seconds 45`. This defaults to a credential-free **dry run**. A separately authorized paid run additionally requires `--execute-paid`, server-side credentials and positive input/output price ceilings covering the selected model. No paid calls or embeddings were made in this pass.

## MCP

The [MCP README](apps/mcp/README.md) includes compatible-client configuration. Ten tools inspect incidents, logs, metrics, dependencies, changes, historical incidents, runbooks, Kafka, FIX and database health. Typed arguments reject unknown fields, enforce bounded results and sanitize secrets. Stdio works locally; hosted Streamable HTTP requires explicit protection.

## Security and configuration

`LIVE_AI` requires a configured server admin key and `Authorization: Bearer ...`, plus an investigation budget. Demo state is scoped to UUID sessions. Request-size caps, result limits, timeouts, log sanitization and evidence validation bound the attack surface. Untrusted telemetry cannot add tools or alter system instructions. An injection fixture and direct tests exercise this boundary. Session identifiers are capability tokens for synthetic data, not customer authentication.

The [version-controlled investigator prompt](apps/api/creditops/prompts/investigator.md) and [security document](docs/SECURITY.md) explain the threat model. The current single-instance in-memory rate limiter needs a shared store before multi-replica hosting. An admin key is a minimal demonstration mechanism, not institutional identity management.

| Variable | Role |
|---|---|
| `DATABASE_URL` | SQLite or asynchronous PostgreSQL URL |
| `API_BASE_URL` | Server-side Next.js proxy destination |
| `TELEMETRY_MODE`, `KAFKA_BOOTSTRAP_SERVERS` | Persisted demo or local Kafka adapter |
| `PUBLIC_DEMO` | Defaults true; prevents paid embedding queries in public diagnostic requests |
| `EMBEDDINGS_ENABLED`, `EMBEDDING_MODEL` | Optional private pgvector retrieval; explicit offline indexing setup |
| `AI_PROVIDER` | `openai` or `anthropic` for protected live mode |
| `OPENAI_MODEL`, `ANTHROPIC_MODEL` | Explicit model choice, no business-logic hardcoding |
| Provider API keys | Server-side only |
| `ADMIN_API_KEY` | Protect expensive live investigation |
| Investigation budget/deadline settings | Bound demo requests and costs |
| Provider pricing variables | Optional user-configured cost estimate |

## Deployment

Target: Vercel frontend, container-hosted FastAPI, Neon PostgreSQL. Docker and Render configuration are included; no cloud deployment was performed in this pass. See [deployment steps](docs/DEPLOYMENT.md), the historical [first-pass report](docs/FINAL_REPORT.md), and the current [second-pass report](docs/SECOND_PASS_REPORT.md). A local build is not a verified cloud deployment.

## Interview materials

- [Two-minute click-and-talk demo](docs/DEMO_SCRIPT.md)
- [Interview walkthrough and honest answers](docs/INTERVIEW_WALKTHROUGH.md)
- [Portfolio/resume summary](docs/PORTFOLIO_SUMMARY.md)
- [Architecture](docs/ARCHITECTURE.md), [tradeoffs](docs/TRADEOFFS.md), [security](docs/SECURITY.md)

Future improvements include independent held-out cases, live-provider comparative benchmarks, calibrated uncertainty, shared rate limiting, institutional authentication, retention controls and operator usability studies. This repository does not connect to a trading venue or perform remediation.
