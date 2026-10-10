# Live verification and offline investigation repairs

**OFFLINE REPAIR — NO LIVE REQUESTS IN THIS PASS. LIVE-MODEL QUALITY UNVERIFIED.**

## Failed first attempt

The owner approved only `INC-DEMO-001` under the existing USD 5 envelope.
Execution source: `5720749903bee1213c531842bcf959b3054c4fc8`.
Experiment: `4ce25b27-307a-4c20-aa51-6c838e058997`.
Local sanitized receipt: `artifacts/live-verification/run-f6b52516-bf41-42ac-b8d4-f60229dfbfe5.json`.
Ledger: `artifacts/live-verification/experiment-4ce25b27-307a-4c20-aa51-6c838e058997.json`.

| Case | Actual execution and evidence | Model / validation / final output |
|---|---|---|
| INC-DEMO-001 | STOPPED in 11.376 s; three OpenAI decision responses; actual MCP `get_incident` → `INC-DEMO-001`, `get_service_topology` → `TOPOLOGY-001`, `search_logs` → no rows | Proposed `query_metrics` with unsupported non-null `q`; rejected locally before dispatch. No assessment proposal, assessment validation, final diagnosis or fallback. Business impact/RFQ/order state and assessment citations were unassessed. |

Requested and returned model: `gpt-5.4-mini-2026-03-17`, default service tier.
Run time: 2026-10-09 20:47:04–20:47:15 UTC; frozen completed-fixture cutoff
`2026-10-09T15:00:00Z` (`fixed_elapsed=300` with the existing 12× simulation clock).
Reported usage: 7,110 input + 234 output = 7,344 tokens; 3,584 cached input,
zero reported reasoning tokens. Conservative usage estimate: USD 0.0063855,
without cached-input discounts. Retained reservation: USD 0.12633525.
Neither quantity is confirmed billing. Three successful SDK responses were
structured action outputs, not a successful diagnosis. Cases 002/003 were not run.

## Root cause and minimum correction

The boundary was: verified MCP catalog → provider output schema → parsed action
→ investigator argument extraction → `safe_arguments` → MCP → backend filters.
Before repair, `providers.DiagnosticRequest` had generic `name/service/q` fields,
so the SDK schema permitted `query_metrics + q`; `diagnostic_clients.FILTERS`
correctly excluded `q` for that tool. The investigator then extracted generic
fields and stopped at the runtime guard. `MCPDiagnosticClient.__aenter__` dropped
tool descriptions from the model catalog. `Store._evidence_query` uses a literal
case-insensitive substring, so the Boolean-looking OR query matched nothing.
`security.SENSITIVE_KEYS` also matched singular `input_token_ceiling` and redacted it.

The focused repair keeps the adaptive architecture and conservative validator:

- `tool_contracts.py` supplies shared bounded scalar types, closed per-tool
  requests, allowed fields and locally reviewed descriptions. `AdaptiveDecision`
  remains an object root with a nested request `anyOf`; tool names use one-value
  enums. Unknown fields, metrics `q` (including null), topology filters, and
  model-supplied session/incident/cutoff/limit controls are rejected.
- Nine tools are model-selectable; all ten MCP tools are still verified.
  Initial incident context remains application-owned. Supported nullable filters
  become omitted MCP arguments only after validation; unsupported fields are
  never silently removed. Both adaptive and existing plan extraction use the
  validated request's own fields. Historical action receipts/replays stay readable
  and are never accepted as new executable commands.
- Owned descriptions are retained after schema verification, never replaced by
  arbitrary remote descriptions. Logs search `summary` and serialized `data` as
  case-insensitive literal substrings: no Boolean OR/AND, SQL, regex or semantic
  syntax. Empty/null/omitted `q` removes only the text filter. No matches remains
  unknown; a distinct broader query may retrieve evidence within existing bounds.
- Metrics use exact identifiers, inclusive timezone bounds and the frozen cutoff.
  Omit/null `metric` to discover bounded incident-scoped raw rows. Existing full
  MCP `aggregation` is ignored by the backend; it remains compatibility metadata
  but is excluded from model requests/catalog. History `service` boosts lexical
  ranking rather than filtering; descriptions state that behavior.
- Local action rejection records the schema/parse/argument stage and
  `mcp_dispatched=false`; partial receipts retain actual dispatched-call counts.
  Assessment proposal/validator/final-output separation remains unchanged.
- Future numeric receipts use `input_tokens_ceiling`, an internally computed
  positive integer. The sensitive-key pattern is unchanged; string protection
  now also catches refresh-token assignments. Secrets under harmless metadata
  keys remain sanitized. Old redacted ceilings remain unavailable.

[Official Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs)
requires an object root, closed objects and required properties, with supported
nested `anyOf`/definitions and nullable fields. Tests inspect the actual installed
SDK's outgoing `text.format.schema` over an offline HTTP transport. Calendar/time
ordering and action/request coherence also require local Pydantic/runtime checks;
`model_validator` is not claimed to serialize those conditions into JSON Schema.
Schema serialization tests do not establish new live model capability.

## Executed offline verification

The required regression first failed because the actual SDK schema accepted the
reported payload while the guard rejected it. It now rejects that payload,
including a fully populated metrics object with an added `q` or `q:null`.
A matrix covers every model-selectable tool's valid request, cross-tool/unknown
fields, types/bounds and protected-scope injection. Real local MCP scripted tests
verify unchanged metric/service/time filters, prior-result delivery, literal search,
no-match uncertainty, broader retrieval, rejection counts and process cleanup.
They verify integration and are explicitly scripted, not live-model evaluations.

| Check | Actual result |
|---|---|
| Final full API/MCP/PostgreSQL suite | 233 passed, no skips, 67.17 s; `artifacts/test-results/tool-contract-python-final.xml` |
| Frontend / dependency compatibility | 13 / 2 passed |
| Existing Chromium browser regressions | 19 passed, 50.6 s; isolated synthetic API with credentials disabled and external HTTP blocked |
| Ruff / ESLint / types / production build | Passed; public schema export produced no artifact diff |
| pip-audit / pnpm audit / Bandit / redacted Git-history Gitleaks | Passed; local package itself is not a PyPI audit target |
| Linux process-group lifecycle | Windows platform skip locally; one test passed in hosted Linux CI |
| Original 15-case evaluation, separate output directory | Pipeline 11/15 exact labels, zero invalid references, 3/15 legacy escalation matches |
| Developer-authored robustness, separate output directory | 13/13 passed; four abstentions; zero invalid references or failed substantive checks |

Pytest disables dotenv loading and blocks default external `httpx` and `httpx2`
transports; SDK tests use offline transports with synthetic credentials. The owner's
`.env` stays ignored/untracked and unchanged. No provider inference or embedding
request occurred in this repair. Independent code/security review found no blockers.
[Hosted CI](https://github.com/farhan-shafee/creditops-ai/actions/runs/37994165621)
passed all four jobs on source `028223dab4ddd88453a1802168d29c08a1510fa9`:
233 Python tests (no skips, 39.68 s), 13 frontend tests, two dependency checks,
19 browser regressions (3.2 min), and one Linux process-group lifecycle test.
PostgreSQL migrations, original evaluation/robustness, lint/types/build, dependency
audits, Bandit and the full Git-history secret scan also passed. This later
documentation receipt changes no application source, schema or CI configuration.

[Initial repair CI](https://github.com/farhan-shafee/creditops-ai/actions/runs/37993269522)
on `f935412eeb617f77aae4e0a350ffab3935effa11` passed web/browser/Linux lifecycle,
but Python service initialization and the secret scanner were blocked by Docker
Hub pull limits before application checks/scanning. One failed-job rerun confirmed
the registry failure. CI now pins the exact locally tested pg17/pgvector digest
from [Google's Docker Hub cache](https://docs.cloud.google.com/artifact-registry/docs/pull-cached-dockerhub-images)
and the same Gitleaks 8.30.1 from its [official registry](https://github.com/gitleaks/gitleaks/pkgs/container/gitleaks/).
Digest equality and the complete redacted history scan were verified locally;
no test, scanner rule, migration or assertion was weakened. Cache availability
remains an external dependency. The corrected source CI passed all required checks.

Three database label mismatches retain removal of unsupported change attribution.
The original risk case still has earlier 1,840 ms and later 1,450 ms observations
against a 1,500 ms current-state threshold. Current diagnosis differs from historical
incident explanation; mandatory human review differs from legacy escalation labels.
No labels, thresholds or benchmark cases were changed. The robustness suite is
not an independent held-out evaluation or evidence of production reliability/MTTR.

## Artifact preservation

Before/after SHA-256 checks cover 13 original receipt/ledger/history/replay files;
all match. Manifests are local under `artifacts/test-results/tool-contract-preservation-{before,after}.json`.

- Failed receipt: `e32502aad350ab195da7e48ff4469e7275ff65be94783822126d3cf2a4060090`.
- STOPPED ledger: `5a90b70e92dbd2005218ef886ce8fd696dd37e244b16c9161e0c078bbd7402bd`.

The original ledger is not reopened/reset, reservations are not refunded, and the
runner's stopped-state/continuation guards are unchanged. No original receipt is
rewritten or fabricated. Any later playback must identify a recorded investigation,
original provider/model/time/cutoff, and no new model calls during playback.

## Proposed first-case retry — not authorized

Ledger-verified headroom is USD 5 − USD 0.12633525 = **USD 4.87366475**.
Keep OpenAI `gpt-5.4-mini-2026-03-17`, default tier, price ceilings USD 0.75/4.50
per million input/output tokens, 12 model/12 diagnostic calls, 5,000 output tokens,
90 s/provider, 15 s/tool, 300 s/case, existing context bounds and zero retries.
No paid extras or automatic model changes. No cases 002/003.

Offline SDK capture after repair measured 7,065 raw / 6,934 strict action-schema
bytes. Existing reservation formula now has a maximum 147,603 input tokens by
UTF-8 byte ceiling (120,000 data + 96 prefix + 3,415 prompt + 643 instruction
+ 7,065 schema + 16,384 overhead). At recorded ceilings, maximum reservation is
**USD 0.13320225/call**, **USD 1.598427 for twelve calls**, and **USD 1.72476225**
including retained earlier spending reservations. SDK format expansion above raw
schema is at most 162 bytes, covered by the unchanged protocol allowance. This
is a conservative offline calculation, not usage or billing. Local calculation:
`artifacts/test-results/tool-contract-reservations.json`.

Smallest arrangement supported by the current runner: only after fresh explicit
owner approval, a new identified first-stage attempt linked in the reviewed plan
to the stopped experiment, with `--case-count 1` and `--max-spend-usd 4.87366475`.
Preserve the original ledger and reservation. Keep total active time inside the
original 900 s envelope by proposing `--total-timeout-seconds 888.624`, after
subtracting the recorded 11.376 s. All other call/output/deadline controls stay as
above. Do not use `--stage remaining` or `--continue-reviewed`.

**Enforcement gap:** a new ledger enforces its reduced cap, but the existing
runner does not automatically link separate ledgers or enforce aggregate spending
and active time across them. Approval/setup must review that linkage and retained
reservation; the CLI alone is not independent cumulative-budget enforcement.
No replacement ID/ledger was created and no retry command was executed.
A fresh approved attempt needs the reviewed repaired SHA, secure credential
presence check and existing local-only preflight before its first paid request.

The model selects diagnostic actions and proposes an assessment. MCP provides
controlled access to evidence. A separate conservative rule layer checks and may
normalize the output. Model proposals and final system outputs are evaluated
separately. **OFFLINE REPAIR — NO LIVE REQUESTS IN THIS PASS. LIVE-MODEL QUALITY UNVERIFIED.**

## Strict verification stopping correction

Normal recovery records ordinary diagnostic failures as unknown and allows another
check. Controlled verification must stop immediately. `collect_adaptive_investigation`
now accepts application-owned `stop_on_tool_error=False`; `verify_live.run` always
passes `True` and records it in configuration/provenance. The model, environment
and omitted CLI options cannot disable it.

In strict mode the ordinary-error boundary records the failed tool, error/timeout
category and sanitized stop reason, then raises before returning to the loop.
Existing callbacks retain duration, evidence, provider receipts and reservations;
MCP unwinds and the runner persists STOPPED and closes resources. Persistence
failure remains fatal. No later decision, assessment, tool, retry or fallback runs.
Assessment absence is explicitly `not_validated` / `not_requested_due_to_diagnostic_failure`,
not validator rejection. Existing fatal argument/scope/transport/cancellation guards
and default recovery remain unchanged. Successful empty results can still broaden.

`test_strict_failure_stops_before_the_next_provider_decision_or_assessment` first
failed with two decisions and one assessment, then passed. Actual scripted counts:

| Case | Decisions / assessments / diagnostics |
|---|---|
| Initial context failure | 0 / 0 / 1 |
| Error, timeout, invalid result, final-slot or callback-write failure | 1 / 0 / 2 |
| Successful empty result then broader query, or default recovery | 3 / 1 / 3 |

The actual runner/stdio-MCP/isolated API test dispatches only `get_incident` and a
scripted failing `query_metrics`. It preserves STOPPED receipt/ledger/Store state,
context and numeric ceiling; its labeled offline reservation is unchanged and
usage unknown. MCP child, provider, Store, lock and owned API/log teardown pass.
These are integration checks, not live-model quality. Test dotenv suppression now
precedes collection/child API imports; external HTTP guards remain active.

Final local `pnpm test`: 251 Python passed (no skips, 74.24 s), 13 frontend and two
dependency checks. Lint/types/build, dependency audits and Bandit passed. Linux
lifecycle skips locally on Windows. [CI 38000374090](https://github.com/farhan-shafee/creditops-ai/actions/runs/38000374090)
passed all four jobs for source `f82a6a7863a7b441c2b04a194d8753941d979e42`:
251 Python tests (no skips), 13 frontend tests, two dependency checks, 19 browser
tests and one Linux lifecycle test, plus lint/types/build, audits, Bandit and full
Git-history secret scanning. Separate-output and CI evaluation remain 11/15;
developer-authored robustness remains 13/13. This later documentation receipt
changes no application, schema or configuration files.

All 13 protected artifacts, the historical linkage note and `.env` match their
before/after checksums. Original ledger: STOPPED, USD 0.12633525 retained. Allocated
ID `7d557a47-f018-4f8c-bcd1-be0a24a5f9eb` remains unused, with no real execution
receipt/ledger or replacement ID. Its unchanged historical note does not authorize
revised source. Cross-ledger aggregation remains a local review requirement.

Credential-free dry-run: strict policy enabled; no provider/Store/live ledger.
No execution preflight or live request ran. The earlier retry proposal above is
historical; the next proposal is USD 2 additional with 330 s total and the unchanged
model/call/context/output limits below. Fresh schema ceiling: 147,611 input tokens,
USD 0.13320825/call, USD 1.598499/12 calls, USD 1.72483425 including retained
reservation. This corrects the earlier pre-finalization count by eight schema bytes;
it is not usage/billing. Prior reservation + allocation: USD 2.12633525 < USD 5.
Prior time + deadline: 341.376 s < 900 s. The source-bound dry-run is
`artifacts/test-results/strict-tool-stop-reviewed-source-dry-run.json`; calculation
is `artifacts/test-results/strict-tool-stop-reservations.json`. Both are local,
credential-free offline artifacts, not live receipts.

Proposed only, after fresh owner approval bound to repaired CI-verified source and
`stop_on_tool_error=True`, credential presence check, fresh project API/MCP processes
and existing local-only identity preflight:

```powershell
.\.venv\Scripts\python.exe scripts\verify_live.py --provider openai --model gpt-5.4-mini-2026-03-17 --case-count 1 --max-tool-calls 12 --max-provider-turns 12 --max-spend-usd 2 --timeout-seconds 300 --provider-timeout-seconds 90 --diagnostic-timeout-seconds 15 --total-timeout-seconds 330 --input-price-ceiling 0.75 --output-price-ceiling 4.50 --experiment-id 7d557a47-f018-4f8c-bcd1-be0a24a5f9eb --stage first --execute-paid
```

**LIVE RETRY NOT RUN — REVISED SOURCE REQUIRES OWNER APPROVAL.**

## Investigation control and outcome integrity repair

This is a new offline repair of the action loop and its future outcome records.
The earlier sections describe historical preparation; their unused-attempt and
approval statements do not describe current readiness. Both allocated experiments
are now STOPPED. No paid request, model change, deployment or replacement attempt
occurred in this pass, and previous approvals do not authorize this repaired source.

Root causes: the provider always received the full `AdaptiveDecision` request union,
even when the catalog could exclude an action; strict duplicate/no-progress/limit
branches broke into deterministic fallback; and deterministic assessment wording
denied earlier decision calls. The repair is limited to those boundaries:

- Successful topology retrieval removes that singleton from subsequent catalogs
  within the same frozen investigation. Its evidence remains available. Failed
  topology and genuinely different parameterized queries retain their existing
  recovery/filter behavior; runtime duplicate and scope guards remain enforced.
- `available_decision_type` narrows the actual SDK `text_format` to the catalog's
  existing typed request contracts. The root remains a closed object with a nested
  union, documented enums and nullable fields. Descriptions are locally authored.
  The model still cannot set session, incident, cutoff, limits or strict policy.
- Strict control guards publish a sanitized reason and rejected parsed action,
  when one exists, then raise before any further decision, diagnostic, assessment
  or deterministic fallback. Partial status is failed, runner/ledger STOPPED,
  assessment/proposal/source absent, and validation explicitly not requested.
  Earlier decision success cannot overwrite assessment absence. Persistence and
  cleanup failures remain fatal. Default normal recovery/fallback stays available.
- Deterministic wording now identifies assessment generation only; decision calls
  retain their separate provider receipts. Old receipt text is not rewritten.

RED regressions reproduced topology acceptance in the outgoing SDK schema after
catalog omission, strict guard fallthrough into a complete fallback, and misleading
provenance. GREEN tests capture actual OpenAI and Anthropic SDK requests using
external-network-free transports; topology is absent from schema and catalog after
removal, while the other eight tool types and different filters remain accepted.
Real local MCP/runner tests prove duplicate rejection with two scripted decisions,
zero assessments and two actual dispatches; STOPPED partial receipts, reservations,
unknown usage, retained evidence and teardown. A separate real-MCP path preserves
literal OR/no-match semantics and permits a broader log query. These are scripted
integration tests, not live-model quality results.

Final local `pnpm test`: 267 Python passed (no skips, 102.35 s), 13 frontend tests
and two dependency checks. Local lint/types/build, audits and Bandit passed;
Linux lifecycle skips on Windows. Independent code review found no blockers.
[Normal CI](https://github.com/farhan-shafee/creditops-ai/actions/runs/38008591726)
passed on application source `94bc0258c4eabed50eec5f783d27e7c07b534684`: all four
jobs, 267 Python tests (no skips, 70.95 s), 13 frontend tests, two dependency checks,
19 Chromium browser tests and one Linux lifecycle test, plus lint/types/build,
audits, Bandit and full Git-history secret scanning. Local and CI evaluation remain
baseline 12/15 and pipeline 11/15, zero invalid citations; developer-authored
robustness remains 13/13 with four abstentions. Labels, diagnosis thresholds and
archived outputs are unchanged. This later CI receipt changes documentation only.

Before/after checks cover 19 files: the original protected history, both stopped
receipts/ledgers, approval notes/addendum, latest live pointer and `.env`. Retained
reservations are USD 0.12633525 + USD 0.10088100 = USD 0.22721625; no reset, reopen
or refund. Manifests stay local under
`artifacts/test-results/investigation-control-preservation-{before,after}.json`;
credential fingerprints are not published. `.env` remains ignored and untracked.
Cross-ledger aggregation still requires local review. Offline schema captures are
local at `artifacts/test-results/investigation-control-sdk-schemas.json`: initial
raw/wire sizes 6,989/6,858 bytes, after topology 6,737/6,606. The unchanged byte
ceiling formula gives 147,527 input tokens, USD 0.13314525/call and USD 1.597743
for twelve calls, excluding retained reservations. Calculation is local at
`artifacts/test-results/investigation-control-reservations.json`; these are bounds,
not usage/billing or execution approval. No prices, spend/time/call/context/output
limits or retry policy were raised.

**LIVE RETRY NOT RUN IN THIS PASS — REPAIRED SOURCE REQUIRES FRESH OWNER APPROVAL.
LIVE-MODEL QUALITY REMAINS UNVERIFIED.**
