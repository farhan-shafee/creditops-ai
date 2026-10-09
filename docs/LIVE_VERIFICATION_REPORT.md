# Live verification preparation

**LIVE REQUESTS NOT RUN — AWAITING OWNER AUTHORIZATION.**

## Minimum implementation note

The clean `main` checkout starts at documentation receipt
`76d1e03d88e796d2fd5f562e7bc6fd289ef970c2`; the previous CI-tested source is
`4e8cd4ee9809d1d682e3d72d79cdfcd7a3242862`.

Source inspection confirms an evidence-adaptive investigation using the real MCP
client, provider SDK coverage using offline mocks only, and in-place diagnostic
validation which can replace accepted fields with deterministic domain wording.
The existing live CLI has a dry-run boundary, finite limits and one in-memory
reservation ledger shared by cases. That ledger currently does not survive a
second invocation, and unsuccessful cases need fuller partial receipts.

The minimum changes for this pass are:

1. Preserve a sanitized deep copy of the structured proposal before validation;
   retain changed/rejected fields, rule reasons, and the separate final assessment.
   Identify deterministic, scripted and fallback sources accurately.
2. Extend existing provider execution records with public SDK metadata, nullable
   usage/cost, conservative reservations and interruption/error categories. Keep
   retries disabled and never record private reasoning or credential values.
3. Extend `scripts/verify_live.py` with distinct run receipts and a persistent
   shared experiment reservation ledger. Stop after the first case for review;
   continuation uses the same immutable limits and ledger. Reject unrelated or
   remote databases before initialization. Retain partial attempts.
4. Add focused offline regressions, retain the existing benchmarks and replay
   artifacts, and run normal project verification and CI. No new UI page or
   evaluation framework is needed: structured receipts provide the comparison.
5. Document a concrete three-case OpenAI proposal with current official pricing,
   local configuration checks and commands, then stop for owner authorization.

Offline edits, tests and private-main publication are authorized. The proposed
USD 5 ceiling does not authorize paid requests. Account/model access and live
diagnostic quality remain unverified until an approved execution exists.

## Historical evaluation limits

The original 15 labels and archived artifacts remain unchanged. Three database
exact-label mismatches reflect removal of unsupported application-change
attribution. The risk case has an earlier anomalous observation and a later
observation below the threshold; current-state diagnosis differs from historical
incident explanation. Mandatory human review differs from legacy escalation
expectations. The 13-case robustness suite is developer-authored, not an
independent held-out evaluation. This pass adds no benchmark cases.

## Proposed paid experiment — approval required

| Setting | Exact proposed scope |
|---|---|
| Provider / model | OpenAI, `gpt-5.4-mini-2026-03-17`; no automatic substitute |
| Endpoint / tier | `https://api.openai.com/v1`, `service_tier=default`, environment proxies disabled |
| Cases | `INC-DEMO-001` first; `INC-DEMO-002`, `INC-DEMO-003` only after first-case review warrants continuation |
| Snapshot | Existing completed synthetic fixtures (`fixed_elapsed=300`), fresh isolated session per invocation; freeze one cutoff per case and pass it to every MCP call |
| Price ceilings per 1M tokens | USD 0.75 input / USD 4.50 output; cached input officially USD 0.075, conservatively estimated here at the full input ceiling |
| Shared maximum | **USD 5 for the entire experiment**, including uncertain/interrupted calls; never refund reservations or reset the ledger |
| Model / diagnostic calls | At most 12 model calls and 12 diagnostic calls (including initial incident context) per case; at most 36 of each across three cases |
| Output / context | 5,000 output tokens per request, including reasoning tokens; 120,000 serialized diagnostic-data characters, 250 evidence rows / 90,000 evidence bytes |
| Deadlines | 90 s/provider call, 15 s/diagnostic call, 300 s/case, 900 s/shared active execution including setup; local preflight capped at 15 s; review waiting time excluded |
| Retry / paid extras | Zero automatic provider retries; no embeddings, hosted search or other paid features |

Official documentation checked on 2026-10-09: [model and pinned snapshot](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [current pricing](https://developers.openai.com/api/docs/pricing), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Responses metadata/tier/output cap](https://developers.openai.com/api/reference/resources/responses/methods/create), [Python SDK request IDs, raw response access and retries](https://developers.openai.com/api/reference/python).
The existing Pydantic action/assessment schemas fit documented Structured Outputs
support and pass installed-SDK offline serialization/parsing tests. This verifies
schema compatibility, not account access or diagnostic quality. No API request was
made to test a credential or account availability. Regional/custom endpoints or
different pricing require a new plan; the runner rejects a custom OpenAI endpoint.

Each request reserves
`((serialized input UTF-8 bytes + schema/prompt/instruction bytes + 16,384) × input ceiling + 5,000 × output ceiling) / 1,000,000`.
At the reviewed source limits, a conservative maximum is 144,391 input tokens
by byte ceiling, giving USD 0.13079325/request and **USD 4.708557 for 36 calls**.
The USD 5 ledger remains the hard guard before every request. Reservations differ
from usage estimates and billing; cached discounts are omitted from estimates and
reasoning tokens are not charged twice. Missing usage/cost is UNKNOWN. A timeout
or parsing failure may still incur charges; it is retained and never retried.

Local preparation verified the runner and refreshed API share the repository's
`artifacts/creditops.db` at `http://127.0.0.1:8000`: the API read a fresh UUID record
written by the runner in its isolated session. `/health` confirms synthetic,
read-only diagnostics with embeddings disabled. The final configuration check
completed at `2026-10-09T18:44:34.015596+00:00`; session
`322b682a-a1bd-4e8a-bf9f-c841b56c0c8d`, record
`3724d16c-8f87-488e-8d19-31063c4d5dbc`. This was local preflight only, with no model
calls, database seeding/migration/reset or remote database access by the runner.

**Credential boundary:** `OPENAI_API_KEY` is absent from effective server-side
configuration. Configure it securely in the repository root's gitignored `.env`
(`D:\Dev\Repos\creditops-ai\.env`) or the server process environment. Never send
the key in chat or commit it. Account access to the pinned candidate remains
UNKNOWN. The key's presence would not authorize execution.

After explicit owner approval and secure credential configuration, the initial
command is:

```powershell
.venv\Scripts\python.exe scripts/verify_live.py --provider openai --model gpt-5.4-mini-2026-03-17 --case-count 3 --max-tool-calls 12 --max-provider-turns 12 --max-spend-usd 5 --timeout-seconds 300 --provider-timeout-seconds 90 --diagnostic-timeout-seconds 15 --total-timeout-seconds 900 --input-price-ceiling 0.75 --output-price-ceiling 4.50 --experiment-id 4ce25b27-307a-4c20-aa51-6c838e058997 --stage first --execute-paid
```

Removing `--execute-paid` produces the credential-free dry-run. Replacing it with
`--preflight` checks local configuration/persistence only. The first paid invocation
stops after case 001. Review evidence selection, prior-result consumption, citation
validity, unsupported claims, business-state interpretation, uncertainty and
proposal/validator differences. Continue only if the execution is inspectable and
there is no blocking correctness/security issue, using the identical command with
`--stage remaining --continue-reviewed` in place of `--stage first`. It reuses the
same experiment ID, immutable configuration and reservation ledger. No failed case
is repeated, no model is changed, and unused budget funds no additional experiment.

Stop for refusal/incomplete/malformed output, timeout/error, rejected citations,
MCP transport failure, any failed tool at the case completion gate, absent provider
proposal, orchestrator fallback, budget/deadline exhaustion or a blocking review
finding. Preserve every partial attempt. Diagnose corrections offline; a paid
fix/retry requires separate approval.

## Observable result and later recording

`provider_proposal` preserves only sanitized structured advisory fields before
in-place validation. `validation_outcome` distinguishes structural parsing,
accepted domain, known-domain normalization, abstention/downgrade and rejection.
Changes identify diagnostic-validation versus orchestration rules. Invalid citation
counts mean distinct missing IDs; rejected field paths retain each use. The final
`assessment` is the human-review draft. No field claims a general factuality check.
Deterministic, scripted and fallback sources are explicit.

`provider_calls` retains public execution identity, time, status, sanitized typed
decisions, reported usage/details, recorded price ceilings and reservations.
OpenAI metadata survives structured parsing failures through documented raw
response access. Anthropic's current public parse helper may not return metadata
when parsing fails; those identities/usage stay UNKNOWN. No raw reasoning,
arbitrary headers, environment dump, unsafe HTML execution or credentials are
retained. Untrusted proposals are not approved advice or trusted model/runbook input.

Distinct `run-<UUID>.json` receipts and a durable `experiment-<UUID>.json` ledger
live under gitignored `artifacts/live-verification`; `latest.json` is a pointer.
Partial investigations also use existing session persistence. Only reviewed,
sanitized receipts may be separately published after a real approved run. Existing
deterministic replay artifacts are preserved; any live replay export needs its own
run directory and must identify recorded investigation, original provider/model,
original run time/cutoff, and no new model calls during playback.

There are **no attempted live cases, live usage or billing results** to report.
After execution, use a compact table covering execution stop/completion, actual
calls/MCP evidence, proposed domain/support, invalid IDs/unsupported claims,
validation changes, final limitations, RFQ/order state, latency, usage, usage-based
estimate and conservative reservation. Compare the deterministic path at the same
cutoff where feasible, while distinguishing differently retrieved evidence.
Three synthetic cases demonstrate a small integration/quality check only; they do
not establish generalization, production reliability or MTTR savings.

## Offline verification and publication

| Executed check | Result |
|---|---|
| Full Python API/MCP suite, existing local synthetic PostgreSQL enabled | 193 passed, no skips, 54.82 s; `artifacts/test-results/live-preparation-python.xml` |
| Final provider metadata / runner subset after the last metadata additions | 32 passed, 7.15 s; installed SDKs use offline HTTP transports |
| Frontend unit / dependency compatibility tests | 13 / 2 passed |
| Production Chromium lifecycle / business-state / replay / MCP tests | 19 passed, 47.8 s, against the current local API and production build |
| Ruff, ESLint, typecheck, production build | Passed |
| pip-audit, pnpm audit, Bandit | No known dependency vulnerabilities or reported application security issues |
| Original deterministic pipeline evaluation | 11/15 exact labels, four explained mismatches, 3/15 legacy escalation match; artifacts generated separately without replacing history |
| Developer-authored robustness suite | 13/13 passed, four abstentions, zero invalid references or failed substantive checks |

The original labels, archived baseline, tracked evaluation/robustness results and
deterministic replay files are unchanged. Only additive investigation contracts
were regenerated. The final provider subset includes one additional failed-response
regression beyond the 193-test full-suite run; hosted CI must run the complete
final source before this preparation is considered published and verified.

Private-main commit/push and hosted CI receipt: pending publication. Paid execution
remains unauthorized and the server-side OpenAI credential is absent.
