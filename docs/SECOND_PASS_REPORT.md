# CreditOps AI second-pass report

Verification date: 2026-10-09. This targeted pass extends the existing application. All securities, clients, RFQs, orders, FIX activity and incident telemetry are fictional. No paid model/embedding calls, cloud deployment, external provisioning or recruiter messages were performed.

## Baseline and source review

The checkout began clean on `main` at `d8699a1ed7c07e683b3895a77894f1aca6e00ba3`, matching the reported baseline and private origin `farhan-shafee/creditops-ai`. No user changes were discarded; no reset, history rewrite or visibility change was used. The incremental plan is [recorded here](superpowers/plans/2026-10-09-creditops-second-pass.md).

All six starting observations were confirmed at that commit: direct `DiagnosticTools` construction; provider plan before its results; a separately exposed real MCP server; DB label containing “following application change” without requiring a relevant preceding change; deterministic evaluation artifacts; and operational telemetry without explicit instrument/RFQ/order entities. They were confirmed by inspecting the source and artifacts before editing.

## Changes and their purpose

- Diagnostic results now separate source observations, supported condition, candidate trigger, confirmed cause and unknowns. Pool exhaustion does not require a deployment. Unrelated/later changes are excluded; relevant earlier changes remain hypotheses. All current drafts require human review and display uncalibrated support points.
- The known-domain validator checks citations separately from support, considers contradictory current evidence, and replaces unsupported causal prose. It is explicitly a limited synthetic-domain rule gate, not a general factuality guarantee.
- A small diagnostic-client interface separates direct offline collection from the official-SDK MCP path. The latter verifies schemas, applies a local allowlist, binds scope/cutoff/configuration, validates results and fails closed on protocol loss.
- `MCP_DEMO` runs new stdio diagnostics with an adaptive deterministic provider. Actual results/errors precede subsequent decisions. Protected live providers use the same bounded loop through their official SDKs; they were exercised only with offline network mocks.
- Three fictional corporate bonds and exact Decimal amounts connect six RFQs to quote/order/processing events. One existing incident panel exposes computed counters and a source timeline. Quote/RFQ expiry and acknowledgement remain separate states.
- Investigations freeze simulated time T. Operational and business records must satisfy both reveal and timestamp bounds. Retrieval excludes current-incident answer material. Replay v2 preserves original observations/step times and complete-snapshot provenance; v1 remains readable.
- The original 15-case labels and historical results are preserved. A separate 13-case developer-authored regression suite reports support checks separately from citation validity. The future paid-verification command defaults to a no-network dry run.

No new navigation pages, agent framework, trading engine or autonomous remediation capability was added.

## Real MCP and adaptive proof

`apps/mcp/tests/test_investigation_protocol.py` starts the actual async API worker arrangement. An official `Client` owns a stdio server, discovers the ten expected contracts, then returns fixed-GET diagnostic responses from that same API. Three scenario tests compare returned metric evidence exactly, verify scope and `mcp_stdio` provenance. A fourth test terminates the MCP child and verifies failure with no completed assessment. A fifth cancels an active investigation and verifies that the owned process has stopped after SDK cleanup. These tests prove protocol/orchestration behavior with synthetic data, not real-model intelligence.

Scripted-provider tests present identical initial latency context, then different actual metric results: consumer lag selects `inspect_kafka_lag`; pool saturation selects `inspect_database_health`. They also cover failed/empty/contradictory telemetry, unsupported calls, scope overrides, duplicate/no-progress termination and deadlines. Both provider SDKs serialize/parse adaptive decisions under mocked HTTP transports. A mock response is never counted as a live-provider receipt.

Default bounds are 12 provider turns, 12 diagnostics, two unproductive calls, 250 evidence objects/90 KB, 120 KB provider input, 10 seconds per diagnostic, 20 per provider call and 45 total. Model output cannot change these limits. The application-owned scope includes session, incident, time cutoff and API destination. No direct fallback is used for MCP failures.

## Attribution and lifecycle examples

Initial attribution regressions failed against the baseline and passed after condition/trigger separation: absent, unrelated and post-onset deployments do not become triggers, while a relevant preceding deployment is only a candidate. A valid evidence ID attached to false causal prose is insufficient. Independent review added a regression where failure was observed at 14:30, deployment at 14:35 and repeated failure at 14:40: latest-sample selection must not rewrite onset to 14:40. The corrected association uses the earliest relevant anomalous observation returned.

For pricing, `BOND-DEMO-001` is Demo Aster Manufacturing's fictional USD corporate bond. Two RFQs request USD 1,000,000.00 and 750,000.00 par. One quote at 99.875 per 100 par becomes stale and expires; the other is unavailable. Two later RFQ expiry events produce two missed deadlines. Requested par is not financial loss, revenue or settlement value. FIX has two valid quote acceptances and two economic orders whose acknowledgements become UNKNOWN; retransmissions retain their existing IDs. DB has two processing timeouts while waiting for a connection. The state reducer rejects expired acceptance and cannot invent execution.

Coupon percent, clean price per 100 par and requested par use explicit decimal strings. No accrued interest, fees, settlement, yield curve, valuation or P&L engine is implied. Synthetic session UUIDs are demo capabilities, not institutional customer authentication.

## Evaluation receipts and limitations

The original `data/evaluations/cases.json` remains unchanged. Historical `latest.json` and `latest.md` were copied byte-for-byte from the baseline into [baseline-v1](../artifacts/eval/baseline-v1/latest.md). Current [JSON](../artifacts/eval/latest.json) and [report](../artifacts/eval/latest.md) are freshly generated.

| Deterministic evaluation | Correct top-1 | Mismatches | Total abstentions | Correct expected abstentions | Invalid references |
|---|---:|---:|---:|---:|---:|
| Log-signature baseline |12/15|3/15|3/15|3/3|0|
| Direct orchestrated pipeline |11/15|4/15|4/15|3/3|0|

The three DB labels still contain the unsupported “following application change” qualifier; current condition-only output intentionally mismatches them. `INC-EVAL-011` retains an 1840 ms primary risk observation followed by 1450 ms telemetry below the 1500 ms threshold. The current-evidence rule abstains at the complete cutoff; that fourth mismatch is preserved. Mandatory review yields 3/15 matches against the old escalation expectations. Evidence recall is 80%, runbook recall 100% and tool error rate 0 for the pipeline. These are literal original-scorer outcomes, not an overall production-quality score.

The separate [synthetic robustness report](../artifacts/robustness/latest.md) passes 13/13 cases, with 0 failed cases, 4 abstentions and 0 invalid references. Its 68 declared substantive checks have 0 failures. The tool-failure variant represents absent evidence; actual MCP failure is tested separately. Expectations were written before the first diagnostic logic change and are scorer-only inputs. The cases are developer-authored/tuned, not independently held out. ID validity and substantive support remain different measurements; zero invalid IDs is not zero hallucinations.

Live-provider execution: **NOT RUN**. Live-model quality: **UNVERIFIED**. No measured model cost, human time saved, customer impact or MTTR reduction is claimed.

## Verification receipts

| Check | Actual local result |
|---|---|
| Python API + MCP suite with PostgreSQL enabled |159 passed, 0 failed, 0 skipped, 53.05 s; JUnit `artifacts/test-results/second-pass-python.xml` |
| Real stdio protocol integration (included above) |5/5: three scenarios, forced disconnect and actual subprocess cancellation cleanup |
| Adaptive orchestration (included above) |13/13 scripted/deterministic tests; these are not live-model tests |
| Diagnostic clients / MCP server (included above) |15/15 client checks and 13/13 server checks |
| Official provider SDK tests (included above) |5/5 offline tests, including adaptive result input and pre-request budget refusal |
| Frontend unit suite |13 passed; ESLint and strict TypeScript passed |
| Full development Playwright suite |19 passed in 1.7 min: original 14 behavior regressions plus 5 new business/MCP checks |
| Full production Docker Playwright suite |19 passed in 1.2 min on the final API/web stack; all original and new regressions passed |
| Real Linux Playwright lifecycle in local Docker |1 passed; inherited pipes closed in 60.4 ms and all 4 controlled child processes stopped |
| Lint dependency compatibility |2 passed |
| Production builds / local infrastructure |Next optimized Docker build and API build passed; all 6 Compose services healthy, real broker connected |
| Ruff / Bandit |Passed; Bandit 0 issues,0 suppressed lines |
| pip-audit / full pnpm audit |No known vulnerabilities; pip-audit notes the local project itself is not a PyPI package |
| Gitleaks 8.30.1 |Existing Git history and the complete staged second-pass diff scanned with default rules plus the unchanged exact synthetic-fixture allowlist; no leaks found |
| Preserved original artifacts/labels |Baseline evaluation JSON/Markdown and original 15-case labels verified byte-identical |
| Future live verification CLI |Dry run printed NOT RUN / UNVERIFIED; no provider request |

Commands include `python -m pytest --basetemp=artifacts/test-tmp/second-pass-final --junitxml=artifacts/test-results/second-pass-python.xml` with the disposable local PostgreSQL integration URL, `python -m ruff check apps scripts`, `python -m bandit -r apps/api/creditops apps/mcp/creditops_mcp -ll`, `python -m pip_audit`, `pnpm audit --audit-level high`, `pnpm test:dependencies`, `python scripts/evaluate.py` and `python scripts/robustness.py`. The Linux regression used the actual pinned Playwright plugin in the local web build-stage image. Counts above are executed test cases, not robustness fixture denominators.

The production browser run uses `E2E_EXTERNAL_SERVER=1` and `E2E_BASE_URL=http://127.0.0.1:13000`, exercising the built Next.js frontend, real PostgreSQL and the API's owned MCP subprocess. Hosted CI publication is recorded separately below.

## Failed checks and disposition

- Baseline attribution regressions failed as intended before implementation. Later onset and unit regressions were added from independent review rather than relaxing assertions.
- Percent/ratio tests exposed 0.99% being treated as 99%. Shared normalization now respects explicit units and percent field names, permits known raw fractions and rejects ambiguous/conflicting values; adaptive DB routing uses the same utility.
- Business review reproduced quote age frozen at publication and order submission accepting a contradictory quote ID. Four failing regressions now pass: age uses the snapshot cutoff while status stays event-derived, and order submission requires the accepted quote ID.
- Forced MCP exit initially exposed the official SDK wrapping an application exception in nested task-group exceptions. Cleanup now preserves the original failure and the fail-closed regression passes.
- The old browser persisted-evidence test assumed one superseded quote-age ID. Its exact-source/zero-live-window-read assertions now inspect the currently cited quote-age object from the generated replay, preserving the original behavior requirement.
- Initial new browser checks exposed mismatched instrument property names in the UI; the panel now uses the real coupon/maturity contract and asserts a numeric coupon. Fixture assumptions about service/status spelling were corrected without reducing lifecycle assertions. The standalone capture helper's initial five-second wait was shorter than the observed expiry sequence; its explicit twenty-second wait captures the real state. Final production browser checks pass.
- A local `alembic upgrade head` attempt on the previously auto-created, unversioned SQLite demo database failed because baseline tables already existed. It was preserved without destructive reset or an unverified stamp. A fresh SQLite migration through the new head and the incremental PostgreSQL upgrade both passed; seeded existing SQLite remains usable.
- All four original-evaluation label mismatches remain visible as described above. No fixtures or labels were changed to obtain a perfect result.

## Live boundary and next authorized verification

`python scripts/verify_live.py --provider openai --model MODEL --case-count 1 --max-tool-calls 8 --max-provider-turns 8 --max-spend-usd 0.25 --timeout-seconds 45` prepares a dry run and prints NOT RUN/UNVERIFIED. A future paid run requires separate authorization and `--execute-paid`, a running local API sharing the database, server-only credentials, and positive input/output price ceilings covering the chosen model. Each call reserves input bytes plus schema/overhead and the full 5000-token output cap; unused reservations are not refunded, automatic retries are disabled and all cases share one spend ledger. This depends on accurate conservative price ceilings; it is not a billing oracle.

Before institutional use: enterprise identity/entitlements, durable jobs, shared rate/cost limits, retained immutable audit trails, validated source clocks/data quality, authoritative order reconciliation, held-out evaluation, calibrated uncertainty and human change controls. The existing deployment configuration was left as preparation; no cloud deployment was performed.

## Changed-file summary

Eight genuine captures were produced by `apps/web/scripts/capture-second-pass.mjs` against the local production Docker stack. It operates the normal UI, waits for actual events/results and saves unmodified browser screenshots. The original baseline captures are preserved.

- [Fresh adaptive MCP trace and assessment](screenshots/second-pass-adaptive-mcp.png): deterministic provider, newly executed stdio calls, original evidence cutoff and schema verification.
- [Pricing request impact](screenshots/second-pass-impact-kafka-pricing-lag.png), [FIX acknowledgement uncertainty](screenshots/second-pass-impact-fix-connectivity.png), and [DB processing timeouts](screenshots/second-pass-impact-db-pool-exhaustion.png): event-derived states for all three scenarios.
- [Business source evidence](screenshots/second-pass-business-evidence.png), [320px request view](screenshots/second-pass-mobile-320.png), and [current original-label evaluation](screenshots/second-pass-evaluations.png).
- [DB assessment from recorded replay](screenshots/second-pass-db-assessment.png): supported exhaustion and candidate trigger; this screenshot is a recorded complete snapshot, not a newly executed diagnostic/model run.

Backend: new diagnostics/validation/client/lifecycle/robustness modules; incremental store/models/tools/API/provider/orchestrator updates and one migration. MCP: existing server scope, schema and response validation plus real client/protocol tests. Frontend: one affected-requests panel, structured uncertainty, honest support/provenance labels and existing evaluation text. Data: three-bond/six-RFQ events, schema-v2 replay, archived original evaluation and separate robustness expectations/results. Verification: Python, SDK, MCP, browser/unit regressions and CI robustness command. Documentation: existing README, architecture, security, contract, tradeoffs, demo/interview materials and this report. Linux process teardown, stream generation, persisted evidence, running restoration and run/reset protections remain covered.

## Publication receipt

Source commit and actual hosted CI outcome will be added after publication. Any later documentation-only receipt is distinguished from the tested application commit.
