# CreditOps AI implementation plan

> For agentic workers: use focused parallel implementation with integration and a fresh whole-repository review. The user authorized automatic execution.

**Goal:** Deliver a working, tested, documented synthetic operations platform to the existing private repository.

**Architecture:** FastAPI owns persisted session-scoped simulation and evidence. Next.js proxies browser requests. The investigator and MCP share bounded diagnostic contracts.

**Tech stack:** Python 3.12+, FastAPI, Pydantic, SQLAlchemy, Alembic, official MCP/OpenAI/Anthropic SDKs; Next.js, React, Tailwind, pnpm, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-09-creditops-design.md` and the complete user brief.

## Global constraints
All data is synthetic. Diagnostic capabilities only. No model secrets in frontend. Benchmarks are generated, never invented. Public replay explicitly labels its source. Private GitHub visibility is preserved. No paid resources are created automatically.

## Review focus
Session isolation; concurrent reset/run/investigation behavior; corrupt or invented evidence; oversized and malicious requests; missing credentials and unavailable dependencies.

## Task 1 — persisted synthetic operations backend
- [x] Write and run failing tests for three scenario runs/resets, filtered telemetry, isolation and tools.
- [x] Implement models, settings, database, migrations, deterministic seed, simulator, API and diagnostic tools.
- [x] Run backend tests; verify PostgreSQL migrations and real Redpanda adapter.

## Task 2 — investigator and evaluation
- [x] Write and run failing tests for evidence validation, read-only allowlist, injection and replay provenance.
- [x] Implement collection orchestration, configurable official providers, validation, persistence, SSE and replay artifacts.
- [x] Create at least 15 labeled cases; compare deterministic baseline and pipeline using honest labels; generate JSON/Markdown.

## Task 3 — operations console
- [x] Write E2E specifications for all scenarios, replay, evidence inspection and reset.
- [x] Implement responsive pages, charts, graph, trace, RCA, runbooks, generated benchmark views and architecture.
- [x] Run frontend tests, lint, typecheck, build, E2E and inspect screenshots at all requested widths.

## Task 4 — MCP and infrastructure
- [x] Write registration, input bounds and no mutation tests.
- [x] Implement official MCP stdio and HTTP, Docker stack, Prometheus/Grafana, deployment templates, CI and DX scripts.
- [x] Verify real local dependencies and security scans.

## Task 5 — integrate and publish
- [x] Review all subsystem contracts; fix failures and run the complete check suite.
- [x] Create screenshots, hiring-manager README, interview/demo/tradeoff/portfolio documentation and final report.
- [x] Perform independent security/correctness review and address findings.
- [x] Commit intended files, push to existing private remote, verify commit/visibility/clean tree and update report with exact receipt.
