# Live verification and offline investigation repairs

**Current status: three selected completed synthetic live-model recordings are packaged for keyless replay. No new model experiment, embedding request or cloud mutation is part of this milestone.**

The sections below preserve the chronological development record, including earlier failures, abstention and then-pending approvals. Their historical “not run” statements describe those earlier passes. The current completed 001/002/003 results and showcase scope appear in the final section. Domain acceptance is not general accuracy, autonomous investigation or independent verification of the model's narrative.

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

## Evidence-first correction after completed model abstention

Historical attempt `af672e5c-1720-40ff-9b0f-688580254ba0` completed in 20.681 s
with model-authored abstention. It retrieved context, topology, no quote-service
deployments, and one healthy `DB-001-CPU` sample at 14:00:48Z. No logs/metrics,
Kafka/FIX diagnostics or business events were fetched before assessment. Earlier
results were supplied, but that database sample does not establish whole-incident
or 15:00 health. This remains completed execution with abstention; older retry and
unused-attempt statements above are historical.

Fresh adaptive runs use `evidence_first_v1`: `get_incident {}` →
`get_service_topology {}` → `query_metrics {}` → `search_logs {}` before the first
provider decision. One generic policy uses the existing real-MCP execution helper,
fixed session/incident/cutoff and bounds for all three demos. No guessed filters,
known evidence IDs, generator tags or evaluation answers select these calls.
Their `selected_by=application_runbook`, `provider_turn=0` records distinguish them
from model/deterministic/scripted follow-ups and validator-authored checks. Four
calls consume the existing 12-call budget, leaving eight; all 12 provider turns
remain available, including assessment. No limits or diagnosis rules changed.

Actual isolated MCP retrieval at `2026-10-09T15:00:00Z`:

| Case | Context / topology IDs | Metrics returned / available | Logs / business | First SDK rows / input bytes |
|---|---|---|---|---|
| 001 | `INC-DEMO-001`, `TOPOLOGY-001` | 50 / 198 | 4 / 11 | 67 / 40,343 |
| 002 | `INC-DEMO-002`, `TOPOLOGY-001` | 50 / 154 | 3 / 16 | 71 / 43,717 |
| 003 | `INC-DEMO-003`, `TOPOLOGY-001` | 50 / 154 | 3 / 10 | 65 / 38,642 |

Full IDs/timestamps and actual offline SDK requests are local under
`artifacts/test-results/evidence-first-initial-packet-summary.json`,
`evidence-first-mcp-INC-DEMO-{001,002,003}.json` and
`evidence-first-sdk-INC-DEMO-{001,002,003}.json`. Case 001 includes
`METRIC-001-LAG` (18,923), `METRIC-001-AGE` (8,120 ms), logs `LOG-001-001/002/003/INJECTION`
and `BUSINESS-001-001` through `BUSINESS-001-011`. Fixture existence, cutoff-visible
availability, retrieval and claim support are separate; input delivery is not
independent support for every narrative claim.

Sampling stays bounded: metrics return non-series rows then newest series rows,
50 maximum, omitting 148/104/104 available rows; logs/business share a 50-row limit
ordered oldest first. Returned metric timestamps span 13:59:00–14:02:24Z, not
continuous coverage or current health at 15:00. All demo rows fit and exactly match
actual SDK input with no further sanitizer truncation. Sanitizer protections remain;
packets above its 100-row evidence limit now stop before requesting instead of
silently dropping rows. Existing 90 KB/250-row collection and 120 KB model-data
limits remain. Overflow retains partial state.

The first request supplies actual evidence, four completed signatures/returned IDs,
locally owned catalog/schema, cutoff, reported incident interval and explicit lack
of an initial lower time filter. Coverage is `returned_samples_only`; older samples
may predate that interval. Shared instructions distinguish reports/measurements,
direct/transitive topology, point/interval/current/historical evidence, unqueried
versus unavailable evidence, and observed conditions versus initiating causes.
They suggest useful gap checks without requiring follow-ups or diagnosis. Completed
topology disappears from the actual SDK schema/catalog while its evidence remains;
different parameterized queries remain available and exact duplicates stay guarded.

Successful initial empties allow later abstention; unrelated/conflicting packets
can also abstain. Strict initial errors stop with zero provider calls; normal
recovery remains. A distinct query returning only already-retrieved IDs can still
hit the unchanged no-progress guard. Existing UI details separate selections,
original proposal, validator changes, final advisory output, completion and
abstention. Replay preserves recorded origin/workflow; missing historical selectors
remain unknown. No archived run is relabeled.

RED reproduced only `get_incident` before the old collector's actual SDK boundary
and 10/11 initial unit failures; replay-origin/display regressions also failed first.
GREEN real-MCP scripts choose different Kafka/FIX/database follow-ups from returned
metrics and supply actual results to the next decision: five dispatches, two
scripted decisions and one scripted abstention per case. Strict initial metric
failure stops after three dispatch attempts, zero provider calls, a STOPPED partial
receipt and clean MCP/provider/Store/lock teardown. These tests establish offline
orchestration, not live-model instruction following. Independent review found no
remaining material blockers.

Final local verification: 295 Python tests passed with no skips (137.88 s;
`artifacts/test-results/evidence-first-python-final.xml`), 20 frontend tests, two
dependency checks and 19 Chromium regressions (45.96 s). Lint/types/build,
pip/pnpm audits, Bandit and redacted Git-history/staged-source Gitleaks passed.
Linux lifecycle skips locally on Windows. [Normal CI](https://github.com/farhan-shafee/creditops-ai/actions/runs/38015266511)
passed all four jobs on source `00d777b63aa052769bf8189ab688f865ed9f66e8`:
295 Python tests (no skips, 104.55 s), 20 frontend tests, two dependency checks,
19 Chromium tests (3.4 min) and one Linux lifecycle test, plus lint/types/build,
PostgreSQL migrations, original evaluation/robustness, audits, Bandit and full
Git-history secret scanning. This later CI receipt changes documentation only.
The credential-free dry-run records the four-call workflow and strict policy,
with no Store, experiment ID, ledger or provider request.

Future bound at unchanged recorded USD 0.75/4.50 rates: 148,937 input tokens by
byte ceiling, USD 0.13420275/call, USD 1.610433/12 calls, including the larger
full-catalog schema, 16,384 protocol bytes and 5,000 output tokens. A proposed USD 2
allocation fits. With USD 0.47059650 retained, the calculated combined bound is
USD 2.08102950; retained reserve plus allocation is USD 2.47059650 < USD 5.
Prior active time plus 330 s is 370.842 s < 900 s. These are prospective bounds,
not billing or approval; `artifacts/test-results/evidence-first-reservations.json`.

All 34 protected history/data/approval/replay files and `.env` match before/after
checks. Three receipts/ledgers remain STOPPED, STOPPED, and completed with model
abstention, totaling USD 0.47059650 reserved; live latest is unchanged. `.env`
remains ignored/untracked. No new real attempt ID, approval note, ledger,
reservation or provider request exists. Manifests stay local; no hashes are
published in this report. Separate evaluation outputs retain legacy 12/15 baseline,
11/15 initial-plan pipeline and developer-authored 13/13 robustness with four
abstentions; those scores are not rebranded as new-workflow or held-out accuracy.

Fresh paid execution needs owner approval bound to the repaired CI source, unused
attempt identity, strict policy, cumulative local ledger review and credential,
resource identity/current-pricing checks. Cross-ledger spend/time aggregation remains
manual. Proposed scope stays one case, same pinned OpenAI model, USD 2 additional,
12 tool/provider calls, 5,000 output tokens, 300/90/15/330 s deadlines, zero retries
and no paid extras. No earlier approval authorizes the revised workflow.

**EVIDENCE-FIRST WORKFLOW VERIFIED OFFLINE — LIVE QUALITY NOT YET MEASURED.**


## Offline assessment-citation contract repair

The latest historical attempt `5b4313bd-b492-4738-935b-aca9a0c9dac2` remains
STOPPED; `run-333a8570-5558-4d55-acc2-138d67ca8410.json` is unchanged. Four
application-selected MCP checks returned 67 evidence rows; one model decision
selected assessment and one assessment request followed. The proposal named a
pricing/Kafka backlog condition but placed absence explanations in
`relevant_runbooks` and `similar_incidents` despite retrieving no eligible rows.
Diagnostic reference validation rejected both; no final assessment exists.
Its narrative also requires review: correlated backlog/staleness does not prove
the initiating cause, sampled lag fluctuated, and isolated earlier health samples
do not establish continuous or later health. RFQ expiry/quote unavailability does
not establish fills or financial losses. This repair does not rewrite that result.

Root cause: `models.Assessment` preserves public/historical `list[str]` reference
fields, while `validation.validate_assessment` requires returned IDs of the correct
kind. The static schema sent by `providers.assess` permitted both exact prose
values before that semantic boundary. New `assessment_schema.assessment_type`
builds fresh, deterministic Pydantic types from the exact bounded, sanitized JSON
packet supplied to the assessment request. Shared enums contain only top-level
returned IDs; runbook/history collections use their eligible kinds. Nested mentions,
other sessions, database inventory and expected answers confer no eligibility.
All seven top-level/nested citation collections use this contract. Empty collections
remain optional choices; absent eligible IDs permit only `[]`, never an empty enum,
placeholder or explanatory prose. Public Assessment serialization, four initial
checks, abstention, runtime validation and diagnostic thresholds remain unchanged.

[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
supports the closed, required object/definition schemas and `maxItems: 0` used here.
The installed Anthropic parser strips that empty-array constraint; its public
raw-schema SDK route now preserves `const: []`, using the generally documented
[const support](https://platform.claude.com/docs/en/build-with-claude/structured-outputs#json-schema-limitations).
Local Pydantic parsing retains numeric/reference validation. Actual offline SDK
requests verify serialization, not remote API acceptance. No provider/model changed.
Targeted assessment instructions keep absence explanations in limitations/unknowns,
distinguish not retrieved from nonexistent, and constrain temporal/causal/business
wording. Reference eligibility does not guarantee narrative truth or claim support.

Two exact-prose regressions failed against the old actual SDK wire schemas before
implementation; both now pass. Offline transports inspect both installed official
SDKs, including all seven collections, empty/nonempty/null values, wrong kinds,
unreturned/nested IDs, zero/ordinary/100-row packets, 96-character Unicode IDs,
closure/enum/size limits and session isolation. Invalid offline output preserves its
sanitized public candidate separately with `assessment_structured_output` rejection,
provider metadata/usage/reservations and no semantic validation or substitute final
assessment. Malformed envelopes retain finished partial receipts. Real local MCP
runner tests cover four application-selected calls, one offline decision and one
offline assessment: rejected citations stop with partial receipts and clean teardown;
valid empty references allow abstention. Valid citations with misleading prose still
undergo the unchanged rule layer, with original proposal and normalization separate.
These are offline integration tests, not successful live-model assessments.

Final local verification: normal `pnpm test` passed 336 Python tests with no skips
(124.92 s), two dependency checks and 20 frontend tests; 19 isolated Chromium
regressions passed (45.09 s). Lint/types/build, isolated PostgreSQL migrations,
pip/pnpm audits, Bandit and redacted Git-history/source Gitleaks passed. Linux
lifecycle skips locally on Windows. [Normal source CI](https://github.com/farhan-shafee/creditops-ai/actions/runs/38020329064)
passed all four jobs on `22ffd4d77245a7f12f177fa9bdd20f43a33088b9`: 336 Python tests
with no skips (112.74 s), 20 frontend tests, two dependency checks, 19 Chromium
tests (3.2 min), one Linux lifecycle test, lint/types/build, PostgreSQL migrations,
evaluation/robustness, audits, Bandit and Git-history secret scanning. This later
CI receipt changes documentation only. Local results remain under
`artifacts/test-results/citation-contract-*`. Unchanged legacy evaluation outputs are separate from archived history: 12/15
baseline, 11/15 initial-plan pipeline, zero invalid citations; developer-authored
robustness 13/13 with four abstentions, not an independent held-out evaluation.

One recalculation at the unchanged recorded USD 0.75/4.50 rates includes actual
SDK schema overhead, 120,000 data bytes plus 96 prefix bytes, 16,384 protocol bytes
and 5,000 output tokens. Decision bound: USD 0.13420275. The latest 67-row schema
is 8,079 bytes on the wire; assessment bound USD 0.135. Maximum 100-row ASCII
schema: 25,248 bytes, assessment USD 0.14787675. A deliberately looser 100 ×
96-character non-BMP bound is 236,448 schema bytes and USD 0.30627675; that packet
itself exceeds the unchanged collector limit, so this safely overestimates.
At most 11 decisions plus one assessment under 12 total turns reserve at most
USD 1.782507, fitting the unchanged proposed USD 2 allocation. No limits increased.
Details: `artifacts/test-results/citation-contract-reservations.json`. These are
prospective reservation bounds, not reported usage, confirmed billing or approval.

All 37 protected history/data/approval/replay files, including `.env`, match local
before/after hashes; the live artifact set is unchanged. Four ledger outcomes remain
STOPPED, STOPPED, completed with model abstention, and STOPPED on invalid references.
Retained reservations total USD 0.60731325. Retained plus the calculated maximum
is USD 2.38982025; retained plus a proposed USD 2 allocation is USD 2.60731325
within the original USD 5 envelope. Cross-ledger accounting remains manual.
No new real attempt ID, approval note, execution ledger, reservation or paid request
was created. `.env` stays unchanged, ignored and untracked; private manifests remain
local and no secret/hash values are published.

**LIVE RETRY NOT RUN — REPAIRED SOURCE REQUIRES SEPARATE OWNER APPROVAL.**
Live-model quality and remote acceptance of these new schemas remain unverified.
Any future attempt requires an explicit source-bound owner decision and existing
credential/resource/pricing/cumulative-history checks; no previous approval applies.

## Accepted case-001 result and remaining-case preparation

The separately approved attempt `38ec45c9-71aa-4323-91cb-c5a0360d11ce` completed
on 2026-10-10 in 25.191 s, using application source
`22ffd4d77245a7f12f177fa9bdd20f43a33088b9` at documentation-only HEAD
`bb7aa0ae9805d07be39cf043a1d9dafc5992eb9e`. Original sanitized receipt:
`artifacts/live-verification/run-3f4d7391-f31c-47b9-93cb-da7d02354782.json`.
OpenAI accepted the revised assessment schema remotely. Four application-selected
MCP diagnostics (`get_incident`, `get_service_topology`, `query_metrics`,
`search_logs`) returned 67 evidence rows, including the bounded 50 metric rows.
One model decision selected assessment immediately; one assessment request followed.
There were no model-selected diagnostic follow-ups or rejected actions.

The original model proposed the supported pricing-service/Kafka consumer backlog
condition with support score 0.63 and valid returned reference IDs. Validation
accepted the domain and normalized 19 distinct fields; that count is not evidence
of 19 separately detected errors. Final 0.84 is rule-generated support, not model
confidence or accuracy; both scores are uncalibrated. The original narrative still
overgeneralized causality, fluctuating sampled trends and the timing of CPU/database
health observations. Returned samples ended at 14:02:24Z, before the 15:00Z cutoff.
Final initiating cause remains unconfirmed. RFQ expiry and quote unavailability
are supported; fills or financial losses are not established. This repeatedly
developed synthetic case is not independent held-out evidence. The two remaining
cases are also developer-authored fixtures. One accepted condition demonstrates
neither production MTTR reduction, general accuracy nor autonomous investigation.

Reported usage was 28,119 input and 2,722 output tokens, with usage-based estimate
USD 0.03333825 and separate conservative reservation USD 0.14025975. Confirmed
billing is unknown. Original proposal, receipt, ledger and approval remain unchanged.
Five historical outcomes remain STOPPED, STOPPED, completed with model abstention,
STOPPED on invalid references, and completed with an accepted normalized domain.
Their retained reservations total **USD 0.74757300**; none was reset or refunded.

This preparation changes only `scripts/verify_live.py`, offline runner tests and
this report. `--case-id` accepts exactly the three existing demo IDs and is mutually
exclusive with `--case-count`. Single-case mode executes only the selected case,
using a fresh standalone ledger under stage `first`; that stage does not select
case 001 in this mode. It cannot use `--stage remaining` or `--continue-reviewed`.
Invalid/ambiguous selections fail in argument parsing, before ledger/provider/Store
creation. Dry-run, immutable configuration, identity marker, MCP scope, persisted
investigation and receipt bind the same selected ID. Legacy prefix/staged behavior
and its first-case review requirements remain intact.

The investigation implementation is frozen: evidence_first_v1 initial checks,
adaptive loop, model/settings/prompts, citation schemas, retrieval/sampling,
thresholds, validation/support scores, fixture labels, frontend/replay and deployment
configuration are unchanged. Local before/after checks use the existing SHA-256
preservation approach: 131 frozen implementation/configuration files and 40
protected history files, including all five ledgers/receipts/approvals, benchmark/
replay artifacts, live latest pointer and `.env`. Hash manifests stay private under
`artifacts/test-results/remaining-cases-preservation-*`; no secret hashes are published.

Prospective commands from `D:\Dev\Repos\creditops-ai` follow. UUIDs are placeholders,
not allocated attempt identities. Each requires fresh explicit owner approval bound
to the tested runner commit and reviewed cumulative history. No approval, real
attempt ID, execution ledger or paid request is created by this offline preparation.

INC-DEMO-002 (FIX connectivity):

```powershell
.\.venv\Scripts\python.exe scripts\verify_live.py --provider openai --model gpt-5.4-mini-2026-03-17 --case-id INC-DEMO-002 --max-tool-calls 12 --max-provider-turns 12 --max-spend-usd 2 --timeout-seconds 300 --provider-timeout-seconds 90 --diagnostic-timeout-seconds 15 --total-timeout-seconds 330 --input-price-ceiling 0.75 --output-price-ceiling 4.50 --experiment-id <CASE_002_ATTEMPT_UUID> --stage first --execute-paid
```

INC-DEMO-003 (database connection pool):

```powershell
.\.venv\Scripts\python.exe scripts\verify_live.py --provider openai --model gpt-5.4-mini-2026-03-17 --case-id INC-DEMO-003 --max-tool-calls 12 --max-provider-turns 12 --max-spend-usd 2 --timeout-seconds 300 --provider-timeout-seconds 90 --diagnostic-timeout-seconds 15 --total-timeout-seconds 330 --input-price-ceiling 0.75 --output-price-ceiling 4.50 --experiment-id <CASE_003_ATTEMPT_UUID> --stage first --execute-paid
```

These are separate prospective attempts, not continuation or re-execution of case
001. Standard endpoint/default tier, frozen completed synthetic snapshot, real MCP,
application-controlled scope, strict stopping, 12 diagnostic calls including four
initial checks, 12 provider turns including assessment, 5,000 output tokens, existing
bounded context, 300/90/15/330 s deadlines and zero retries remain unchanged. There
are no paid extras. Future execution must recheck clean reviewed source, credentials
without exposure, dedicated process/resource identity and retained history.

The unchanged [official model rates](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
were checked on 2026-10-10: USD 0.75 input / 4.50 output per million tokens for the
pinned snapshot. The existing actual-SDK-schema reservation calculation remains
applicable because prompts, schemas and context/output allowances are frozen:
USD 0.13420275 per decision, conservative assessment bound USD 0.30627675,
at most 11 decisions plus one assessment = **USD 1.78250700 per case**, below USD 2.
Details remain in `artifacts/test-results/citation-contract-reservations.json`.
Two maximum reservation bounds plus history equal USD 4.31258700. Proposed ceilings
are USD 2 per case / USD 4 additional combined, giving **USD 4.74757300** allocated
exposure under the original USD 5 envelope. Prior active time 84.586 s plus two
330 s limits = **744.586 s**, within 900 s. Cross-ledger spend/time accounting is
manual, not automatically enforced; reservations, proposed allocations, reported
usage estimates and confirmed billing are distinct. Unused allocation grants no
extra execution, and missing usage must remain unknown.

Offline verification: three new selector dry-run tests and four real-runner/MCP
paths failed against the original parser before implementation. Afterward, ten
CLI/dry-run checks and five real local MCP checks pass. Each selected 002/003
success activated only that case and made four diagnostics, one scripted decision
and one scripted assessment. Each induced failure retained the selected case,
partial receipt and fixture reservation, STOPPED after one decision/five diagnostics,
and made no assessment or retry. Legacy first/remaining still runs 001 then 002/003
without repeating 001. Scripted results verify integration, not live-model quality.
Normal local `pnpm test` passed 351 Python tests without skips (190.05 s), two
dependency checks and 20 frontend tests. Nineteen isolated Chromium regressions
passed without retries/flakiness (46.079 s), with owned processes cleaned up.
Lint/types/build, disposable local PostgreSQL migrations, pip/pnpm audits, Bandit
and redacted Git-history Gitleaks passed. Linux lifecycle is skipped locally on
Windows and will run in normal CI. Unchanged legacy evaluation remains 12/15
baseline and 11/15 initial-plan pipeline; developer-authored robustness remains
13/13 with four abstentions, not held-out evaluation. New outputs are separate under
`artifacts/test-results/remaining-*`. All 40 protected and 131 frozen file hashes
match afterward; live file set/latest pointer and `.env` remain unchanged, ignored
and untracked. No remaining-case paid execution has occurred.

[Normal source CI](https://github.com/farhan-shafee/creditops-ai/actions/runs/38050419447)
passed all four jobs on tested runner commit
`18c50ea2c10a7aef69d0e2ea08caf0ec6bb44d8b`: 351 Python tests with no skips
(138.99 s), 20 frontend tests, two dependency checks, 19 Chromium tests (3.3 min),
the Linux lifecycle check, lint/types/build, PostgreSQL migrations, unchanged
evaluation/robustness, audits, Bandit and Git-history secret scanning. This later
CI receipt changes documentation only; future approval must bind that tested
runner source and the unchanged investigation implementation.

**REMAINING LIVE CASES NOT RUN — FRESH SOURCE-BOUND OWNER APPROVAL REQUIRED.**

## Selected recorded synthetic examples — completed 001/002/003 and keyless packaging

The remaining separately authorized source recordings completed on 2026-10-10 without changing the frozen `evidence_first_v1` investigation implementation. The reviewed runner is `18c50ea2c10a7aef69d0e2ea08caf0ec6bb44d8b`; the 002/003 receipt source commit is documentation-only `7e08ab2aa0e942d9596156bdc1191f0bd5c053d8`. Case 001 retains its original `bb7aa0ae9805d07be39cf043a1d9dafc5992eb9e` receipt source commit and the implementation provenance described in its earlier section. All use OpenAI `gpt-5.4-mini-2026-03-17`.

These are **selected recorded synthetic examples**, developed alongside the application and diagnostic rules. They are not independent held-out tests, an autonomous-investigation demonstration or a general-accuracy benchmark. Earlier STOPPED attempts and model abstention remain preserved. The original selected receipts and approvals remain private local records, and the live latest pointer is unchanged by packaging.

| Case and recorded generation (UTC) | Private local source receipt / experiment | Original duration / evidence | Model proposal → recorded validation |
|---|---|---|---|
| 001 pricing backlog; 10:34:52–10:35:17 | `run-3f4d7391-f31c-47b9-93cb-da7d02354782.json`; `38ec45c9-71aa-4323-91cb-c5a0360d11ce` | 25.191 s; 67 rows | Pricing-service / Kafka consumer backlog; model score 0.63; domain accepted; 19 distinct fields normalized; final rule support 0.84 |
| 002 FIX session instability; 16:20:04–16:20:23 | `run-75c7bf12-0bb1-4ca8-b386-721d886f50ad.json`; `77ad110d-913d-4002-b81b-a5648e068d4f` | 19.019 s; 71 rows | FIX connectivity/session instability; model score 0.78; domain accepted; 17 distinct fields normalized; final rule support 0.84 |
| 003 database pool exhaustion; 16:23:26–16:23:42 | `run-b36007b2-4680-44d5-b67c-69a3d255242e.json`; `d731255e-15db-4a97-a331-c74bdaac5327` | 16.138 s; 65 rows | Database connection pool exhaustion; model score 0.87; domain accepted; 19 distinct fields normalized; final rule support 0.84 |

Every selected run dispatched exactly four **application-selected** MCP checks: `get_incident`, `get_service_topology`, `query_metrics` and `search_logs`, with bounded 50-row metric samples. Each then made one model decision choosing assessment and one model assessment. There were **zero model-selected diagnostic follow-ups**, zero rejected actions and no dedicated Kafka/FIX/database inspection, runbook retrieval or historical-incident search in these traces. Discovery of an available tool is not evidence that it was called. The existing deterministic/MCP demonstrations remain separate.

All three preserve valid returned reference IDs and `accepted_normalized` domain-support outcomes. The final 0.84 scores are rule-generated support, not model confidence or accuracy. Both original model and rule scores are uncalibrated. Counts of 19/17/19 distinct rewritten fields do not mean that many independently detected errors; the known-domain rule layer authors conservative wording and is not a general factuality verifier.

### Project review notes and unresolved claims

These are project review notes based on the recorded evidence, not an independent human audit or an automatically proven factuality assessment. Original erroneous prose remains inspectable.

- **001:** The model identifies pricing backlog and stale/unavailable quotes, but overstates causal chains and describes fluctuating lag as growing/rising. Some CPU/DB health wording says “at the cutoff” although the cited observations are earlier. The advisory output keeps the supported condition while leaving the initiating cause unconfirmed. RFQ expiry and unavailable quotes are supported; no fills, financial losses or revenue impact are established.
- **002:** The model identifies FIX instability, delayed ACKs, retransmission and uncertainty. Its executive wording says acknowledgements were delayed “because” of the pathway condition, stronger than the correlation establishes. A CPU alternative cites DB/stale-price objects rather than CPU samples; valid IDs alone do not prove that explanation. Absence of a sampled recovery does not establish failure through the full cutoff. The advisory output requires reconciliation of the same economic order identity; execution/fill state and the initiating network/peer/session cause remain unknown.
- **003:** The model identifies pool saturation, acquisition timeout/DB waits and RFQ processing timeout/expiry. Its incident summary extends the degradation through 15:00 UTC and its causal prose is stronger than the sparse sample coverage supports. A change mentioned in context is not a returned deployment object. The recorded advisory output preserves the pool-exhaustion condition without confirming a release or other initiating cause. No fill, loss or revenue conclusion follows from these events.

The complete recorded snapshots have a frozen cutoff of **2026-10-09 15:00:00 UTC**, but returned samples end at **14:02:24 UTC**. That cutoff is an upper bound, not evidence of continuous or later health/failure. Earlier/negative observations do not exclude missing upstream faults. The UI labels complete-snapshot evidence separately from the visitor's simulated animation, which may be earlier. Original generation time, export time, playback time and original observation timestamps remain distinct.

### Usage estimates and retained history

| Selected receipt | Reported input / output tokens | Usage-based estimate (USD) | Conservative retained reservation (USD) |
|---|---:|---:|---:|
| 001 | 28,119 / 2,722 | 0.03333825 | 0.14025975 |
| 002 | 30,389 / 2,325 | 0.03325425 | 0.14532075 |
| 003 | 26,891 / 2,796 | 0.03275025 | 0.13770825 |
| Selected total | 85,399 / 7,843 | 0.09934275 | 0.42328875 |

These values are recorded usage estimates/reservations, not confirmed billing or total hosting cost. The three original execution durations total 60.348 s and do not measure human time saved. Playback duration is separate. The seven historical outcomes remain three STOPPED attempts, one completed model abstention and these three completed accepted-domain examples. Earlier retained reservations of USD 0.60731325 plus these USD 0.42328875 equal **USD 1.03060200**; the historical ledgers remain unchanged, with no new paid attempt, approval, reservation or refund from packaging.

### Sanitized replay package and public profile

The committed derivatives live in `data/showcase/INC-DEMO-001.json` through `003.json`, with `data/showcase/manifest.json`. `scripts/export_showcase.py` uses the explicit three-receipt filename/experiment allowlist and existing replay format/integrity contract. The manifest records original receipt source/hash/commit, export version/time and redactions; source hashes are provenance values, not credential fingerprints. Local paths, account/device/session details, provider request identifiers, authorization/approval/environment data and unnecessary operational metadata are removed. The packaged evidence, original structured proposal, original validation outcome and original final assessment retain the original identities/content/times needed for inspection.

Replay checks structural/reference/integrity validity and keeps recorded output intact. Any separate present-day validation check remains distinct from the historical result. Missing, malformed or mismatched artifacts fail visibly, without substituting a deterministic recording. Playback opens evidence from its recorded snapshot rather than current session/database rows. The API uses the configured `REPLAY_DIR`, preserving ordinary `data/replay` compatibility.

The exact local command is **`pnpm showcase`**. It reuses the existing launcher, sets `REPLAY_DIR` to the absolute showcase directory, uses only `artifacts/runtime/showcase.db`, strips inherited provider/admin keys, sets `PUBLIC_DEMO=true` and `EMBEDDINGS_ENABLED=false`, and disables dotenv using `CREDITOPS_ENV_FILE=''`. It leaves the owner's `.env` untouched. Public paid investigations and query embeddings are denied at the API boundary even with offline fake-key canaries. Replay constructs no model client and makes no new model/embedding/MCP diagnostic calls.

Focused configuration verification: two subprocess regressions failed before the dotenv opt-out and all three now pass, including a guard forbidding every dotenv read for empty mode, an explicitly isolated fake-only dotenv and unchanged ordinary default-path configuration. The Node launcher regression failed before implementation and now passes with inherited fake OpenAI/Anthropic/admin keys, a private-receipt replay path and an owner database path: the child profile drops keys and selects only isolated showcase storage. Focused Ruff and Node syntax checks passed. Normal repository acceptance, browser screenshots and actual source CI are recorded below when completed; these focused checks alone do not claim whole-suite or cloud success.

The existing [demo script](DEMO_SCRIPT.md), [interview walkthrough](INTERVIEW_WALKTHROUGH.md), README and [deployment handoff](DEPLOYMENT.md) now describe the selected recordings accurately. The intended hosted topology remains dedicated frontend/API/database resources, with `/app/data/showcase` packaged in the API image and no provider/admin credentials. Hosting account/resource/plan approval and current cost verification remain owner decisions. No public URL, cloud resource or new provider execution was created by this milestone.

Offline packaging acceptance on 2026-10-10: normal `pnpm test` passed **375 Python tests without skips** (181.46 s; one local pytest-cache warning), **27 frontend tests** and three startup/dependency checks. The Python suite includes real local MCP, strict stopping, session/cutoff isolation, receipt/proposal preservation and disposable PostgreSQL checks. All three packaged recordings also load without access to the private receipt directory, with provider and diagnostic constructors forbidden. Missing/malformed artifacts and mismatched manifest claims fail honestly. Replay retains recorded output; any current copy-based validation changes are displayed separately. A validator step remains local validation even when replay transport is recorded.

Lint, types and production build passed. Pip/pnpm audits found no known dependency vulnerabilities (the local project itself is not a PyPI package); Bandit found no issues; redacted Gitleaks scans passed for staged files and Git history. The unchanged isolated evaluations reproduce 12/15 baseline and 11/15 deterministic-investigator exact labels, plus 13/13 developer-authored robustness cases, without overwriting archived outputs. Nineteen legacy Chromium regressions passed in 59.6 s and four keyless showcase regressions passed in 23.9 s without retries, including all recordings, recorded evidence click-through, refresh/reset, independent sessions, public paid-action denial and desktop/mobile widths down to 320 px. An earlier local browser pass hit a cold Next.js JSON-cache error; clearing only ignored dev cache and restarting the owned server resolved it. Playwright's Windows-managed launcher shutdown required explicit owned-tree cleanup; the existing Unix process-group lifecycle check is skipped on Windows and runs in normal Linux CI. No assertions were weakened.

Genuine local [entry](screenshots/showcase-entry.png), [business events](screenshots/showcase-business-impact.png), [evidence drawer](screenshots/showcase-impact-evidence.png), [original proposal/validation](screenshots/showcase-proposal-validation.png), [advisory output](screenshots/showcase-final-advisory.png), [results](screenshots/showcase-results.png) and [mobile](screenshots/showcase-mobile.png) captures accompany the short [playback recording](screenshots/showcase-playback.webm). A local API image build and inspection of an unstarted, network-disabled container verified exact showcase/replay/evaluation hashes and the absence of dotenv, private receipts, runtime files and provider/admin environment keys. It was not deployed.

The post-test preservation check confirms all **32 protected files**, **23 frozen-core files** and both collector AST hashes unchanged. The original 22 live-history files/latest pointer, seven ledgers, retained **USD 1.03060200**, historical replay/benchmarks and ignored/untracked `.env` are preserved. All three derivatives match their source hashes and original sanitized proposal/validation/final/evidence objects. Changes are confined to replay, presentation, public-profile packaging, documentation and tests; investigation logic, prompts, citation schemas, sampling, fixtures and diagnostic rules remain frozen. Actual source CI is recorded in the following publication receipt; no new live request or approval was created.
