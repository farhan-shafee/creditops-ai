# Premium Incident Workspace Implementation Plan

> **Historical deployment context** - This record retains its original milestone, source revisions, measured results and approval boundaries. Earlier hosting/source-visibility/pending-release statements are dated history. Use [the current production documentation](../../DEPLOYMENT.md) for the October 24-25 Railway topology, release state and remaining closeout.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the three packaged synthetic recordings readable, inspectable and useful for a human-review handoff without changing investigation behavior or recorded results.

**Architecture:** Compose a recording-specific workspace inside the existing `IncidentView`. Pure adapters consume only the matching investigation; Console retains API, replay, selection, cancellation and drawer ownership. Local React state, bounded `sessionStorage`, deterministic templates and browser clipboard/print provide the approved interactions.

**Tech Stack:** Existing Next.js 16.4, React 19.3, TypeScript, CSS/SVG, lucide-react, `node:test` through `tsx`, and Playwright. No new dependencies or framework.

**Spec:** [Approved design](../specs/2026-10-11-premium-incident-workspace-design.md).

**Status:** Planning only, 2026-10-11. Design approved; implementation, publication and deployment pending. This plan and the specification remain local/uncommitted. Inspected `main`: `324dd57317baab22063d43b5f6356342df370c07`; origin: private `farhan-shafee/creditops-ai`. No tests or CI were run during planning.

## Global Constraints

- Only a matching `REPLAY` investigation with showcase provenance gets the workspace. Preserve existing routes and other modes.
- Use active `Investigation.evidence` only. No live metrics, current incident timeline, business API, other session, or fixture answer substitutes.
- Preserve prompts, models, orchestration, MCP, sampling, validation, scores, packaged recordings, fixtures, labels, history, database and hosting configuration.
- Keep **Synthetic · Recorded · Human review required**; distinguish original outcome from playback status. Scores remain uncalibrated; reference validity does not establish prose accuracy.
- Plot discrete observations at actual timestamps; no connecting lines, area, interpolation, continuous-health bands or diagnosis-specific defaults.
- Notes: plain text, maximum 4,000 characters; maximum 20 returned-source pins; tab-local and unverified. No model/backend/evidence mutation or inclusion in exports.
- Handoffs cover the full recording regardless of display filters. Both carry **Synthetic · Recorded · Draft · Human review required**, material limitations and resolvable source IDs.
- Desktop body text 14–16px, line-height at least 1.5; stacked layout at 768px and below; 390/320px without document overflow. Preserve keyboard, drawer and reduced-motion behavior.
- No paid calls, new scenarios, uploads, integrations, collaboration backend or autonomous remediation. Public paid-action denial and disabled embeddings remain intact.
- No worktree/branch creation, dependency installation, product edits, tests, commit, push or deployment in this planning pass. Every checkbox below belongs to a later explicitly approved implementation.

## Review Focus

1. Reused `TOPOLOGY-001`, nested context references, duplicate IDs and incident mismatch: never inspect another recording or turn context into returned evidence. Pin in Slice 1 identity tests and Slice 5 delayed-response tests.
2. Sparse, tied, constant, negative or invalid samples and fractional count units: preserve separate observations and explain unplottable rows. Pin in Slice 1 coordinate tests and Slice 2 marker/table tests.
3. Record changes and reset while async work is pending: clear selection safely, retain failed-reset notes, and clear only the captured successful-reset scope. Pin in Slice 3 and Slice 5 browser tests.
4. Denied/full/malformed storage and changed source version: retain safe memory state, explain refresh loss, never leak another key's notes. Pin in Slice 3 storage tests.
5. Filtered/pinned views, missing assessments and hostile metadata at export: full-record scope, faithful unknowns, one timestamp, no personal/session/configuration data. Pin in Slice 4 composer and browser tests.

## File responsibilities

All paths below are repository-relative; “new” names and interfaces are proposed, not existing APIs.

| Files | Later responsibility |
|---|---|
| New `apps/web/src/lib/recorded-evidence.ts` | Identity gate, source index, typed sample/event projections, filters, exact relationships and decimal formatting. |
| New `apps/web/src/lib/recorded-review.ts` | Original/final field values, recorded changes, unique path counts, separate project/playback review. |
| New `apps/web/src/lib/incident-handoff.ts` | Shared draft types in Slice 1; allowlisted deterministic composition/Markdown in Slice 4. |
| New `apps/web/src/lib/workspace-notes.ts` | Versioned scope keys, validated bounds and explicit storage outcomes. |
| New `apps/web/src/components/recorded-incident-workspace.tsx` | Header, local tabs, filters/selection, personal state and section composition. |
| New `apps/web/src/components/recorded-evidence-timeline.tsx` | Discrete SVG lanes, overlap chooser, accessible source table and journey selection. |
| New `apps/web/src/components/recorded-assessment-review.tsx` | Readable comparison, recorded reasons, project findings and secondary JSON. |
| New `apps/web/src/components/incident-handoff.tsx` | Prepared draft preview, copy fallback and print region. |
| Modify `apps/web/src/views/incidents.tsx`, `apps/web/src/components/console.tsx` | Existing composition/lifecycle seam; recording and session binding, optional drawer controls, successful scoped reset. |
| Modify `apps/web/src/components/investigator.tsx`, `apps/web/src/components/business-impact.tsx` | Small presentation/helper extractions; retain legacy controls, attribution, live business behavior and rules. |
| Modify `apps/web/src/components/evidence-drawer.tsx`, `apps/web/src/app/globals.css` | Optional pin/reveal controls; scoped readable, responsive and print styles. |
| New `apps/web/tests/recorded-fixtures.ts` | Test-only clones of committed packaged records and small malformed variants. |
| New `apps/web/tests/recorded-evidence.test.tsx`, `recorded-review.test.tsx`, `recorded-workspace.test.tsx`, `workspace-notes.test.tsx`, `incident-handoff.test.tsx` | Existing Node/static-render harness; no DOM library. All five paths are under `apps/web/tests/`. |
| Modify `apps/web/e2e/showcase.spec.ts`; existing relevant web tests | Actual effects, events, keyboard, storage, clipboard, print and preserved lifecycle assertions. |
| Modify `docs/DEMO_SCRIPT.md`, `docs/INTERVIEW_WALKTHROUGH.md` | Walkthrough after working UI; honest recording/model/rule attribution and local-only personal tools. |

Do not change API types/routes, Playwright configuration, workflows or package/lockfiles. Put new browser coverage in the existing `showcase.spec.ts`: the base configuration excludes that file and the showcase configuration matches it explicitly.

## Later isolated execution setup

1. After implementation approval and execution-method selection, reread both documents and applicable instructions. Recheck status, HEAD, remote, worktrees and attached artifacts. Stop on unexpected source changes; preserve unrelated work.
2. Use the native managed worktree facility, not the primary checkout. Reuse only an attached workspace dedicated to this approved task at the approved base; otherwise call `mcp__codex_app__create_worktree` with `{allowAsync: true, name: "premium-incident-workspace-v2", ref: "324dd57317baab22063d43b5f6356342df370c07"}`. Use its returned workspace directory; await completion and attachment. Do not invent a fixed managed path.
3. In that returned directory, verify the base and unused branch name, then create local branch `codex/premium-incident-workspace-v2` with `git switch -c codex/premium-incident-workspace-v2`. Do not switch original `main`. If isolation is unavailable, stop; do not fall back to production's checkout.
4. Copy only the two approved planning documents into the worktree. Do not copy `.env`, `.vercel`, local databases, original receipts/approvals, dependency directories or cloud credentials. Preserve the originals in this checkout.
5. Read `apps/web/AGENTS.md` and relevant installed guides under `apps/web/node_modules/next/dist/docs/` before component changes. Check local Node/pnpm/Python/Chromium availability; later setup uses the existing lockfiles and local `.venv`, never system-wide changes. CI uses Node 24, pnpm 11.25.0 and Python 3.12.
6. Record baseline status and private before hashes for `data/showcase`, `data/replay`, `data/evaluations`, archived evaluation/robustness artifacts and frozen backend/configuration files. Original local receipt/ledger/approval hashes remain in their existing local preservation process. Verify `.env` ignored/untracked without displaying or copying contents; preserve it untouched. No changes to the live latest pointer.
7. Run an isolated baseline web test/typecheck pass. Record pre-existing failures rather than weakening assertions. Use the keyless local environment described under verification; never use hosted URLs or the owner's database.

Local implementation/testing ends with reviewable changes and local commits only when covered by the next implementation approval. Remote publication is a later owner gate: inspect actual Vercel Git/preview and Railway branch/path/deployment triggers before any push. Obtain publication approval specifying the branch/SHA and allowed host effects. A branch name does not guarantee isolation from deployment. Production deployment is another separately approved operation; passing remote CI does not itself authorize it.

## Slice 1 — Recording-owned data helpers

**Depends on:** isolated baseline. **Files:** new `recorded-evidence.ts`, `recorded-review.ts`, draft types in `lib/incident-handoff.ts`, `tests/recorded-fixtures.ts`, `recorded-evidence.test.tsx`, `recorded-review.test.tsx`; modify decimal/helper imports in `business-impact.tsx` only. Reuse public `Investigation`, `Evidence`, `Assessment`; extract the existing private `par(value: string)` unchanged as `formatRecordedDecimal(value: string): string`.

**Interfaces to establish:**

```ts
type RecordingIdentity = { incidentId: string; sourceSha256: string; exportedAt: string };
type Coverage = { startMs: number; endMs: number };
type TimedSource = { source: Evidence; timestampMs: number };
type MetricSample = TimedSource & { metric: string; unit: string; value: number };
type MetricGroup = { key: string; service: string; metric: string; unit: string;
  samples: readonly MetricSample[] };
type RequestSelection = { rfqId: string; economicOrderId: string | null };
type RequestJourney = { rfqId: string | null; events: readonly Evidence[] };
type WorkspaceFilters = { service: string | null; metricGroupKey: string | null;
  request: RequestSelection | null; window: Coverage | null };
type RecordedRecording = { investigation: Readonly<Investigation>; incident: Evidence;
  identity: RecordingIdentity | null; sources: ReadonlyMap<string, Evidence>;
  metrics: readonly MetricGroup[]; logs: readonly TimedSource[];
  journeys: readonly RequestJourney[]; coverage: Coverage | null;
  warnings: readonly string[]; contextReferences: readonly string[] };
type RecordedProjection = { kind: 'legacy' } | { kind: 'blocked'; reason: string }
  | { kind: 'ready'; recording: RecordedRecording };
type TimelineView = { valid: boolean; error: string | null;
  metrics: readonly MetricGroup[]; logs: readonly TimedSource[];
  business: readonly TimedSource[]; relatedSourceIds: ReadonlySet<string> };
projectRecording(investigation: Investigation, selectedIncidentId: string): RecordedProjection;
defaultWorkspaceFilters(recording: RecordedRecording): WorkspaceFilters;
filterRecordedEvidence(recording: RecordedRecording, filters: WorkspaceFilters): TimelineView;
revealRecordedSource(recording: RecordedRecording, filters: WorkspaceFilters, id: string): WorkspaceFilters;
samplePosition(timestampMs: number, coverage: Coverage): number | null; // normalized 0..1
metricDomain(samples: readonly MetricSample[]): readonly [number, number] | null;
formatRecordedDecimal(value: string): string;
```

`RecordedRecording` retains every returned source, including unplottable rows; typed lanes omit invalid values with warnings. Business journeys retain even invalid-time events for inspection/observed counts without inventing chronology. Use copied timestamp/ID ordering. RFQ/order/trace joins compare nonempty literal returned fields only; preserve economic-order identity for retransmission. Never enrich from nested IDs or topology. Missing durable identity disables persistence, not source inspection. `defaultWorkspaceFilters` uses full coverage/all services/all requests and the lexically first service/metric/unit group; resetting restores those values.

In `recorded-review.ts`, define `RecordedValue = {kind:'missing'} | {kind:'null'} | {kind:'value'; value:unknown}`, `RecordedChange = {field:string; stage:string|null; reason:string|null; kind:'changed'|'rejected'}`, and `ReviewRow = {path:string; original:RecordedValue; advisory:RecordedValue; changes:readonly RecordedChange[]}`. `RecordedReview` has `rows:readonly ReviewRow[]`, `otherChanges:readonly RecordedChange[]`, `uniqueChangedPathCount:number`, `proposalAvailability`, `validationAvailability` and `advisoryAvailability` (each `'available'|'unavailable'`), `projectNotes` (existing showcase review-notes type or `null`) and `playbackValidation` (existing provenance playback-validation type or `null`). Export `projectRecordedReview(investigation: Investigation): RecordedReview`.

Declare shared handoff types now: `HandoffTemplate = 'technical'|'stakeholder'`; `HandoffSection = {heading:string; paragraphs:readonly string[]; evidenceIds:readonly string[]}`; `HandoffSource = {id:string; kind:string; service:string; timestamp:string; detail:string}`; `HandoffDraft = {template:HandoffTemplate; incidentId:string; preparedAt:string; labels:readonly string[]; sections:readonly HandoffSection[]; sources:readonly HandoffSource[]; pinnedSourceIds:readonly string[]; unavailableSourceIds:readonly string[]}`. Composition comes in Slice 4.

- [ ] Write tests using read-only JSON/manifest oracles. `loadRecordedFixture(id: 'INC-DEMO-001'|'INC-DEMO-002'|'INC-DEMO-003'): Investigation` is a **test-only** clone adapted to the existing replay presentation; do not alter packaged bytes or add a loader.
- [ ] Pin these assertions before implementation:

  | Test name | Required assertion |
  |---|---|
  | `recording_identity_is_scoped_and_ambiguous_ids_block` | Different recordings' `TOPOLOGY-001` resolve to their own object; mismatch, missing recorded incident and duplicate top-level ID block; no nested context source enters the index. |
  | `discrete_samples_preserve_time_value_unit_and_ties` | Irregular timestamps give proportional positions; same-time conflicting and identical rows remain separate; negative/constant domain contains all values; fractional counts unchanged; invalid timestamps/nonfinite values warned and still inspectable; empty lane is not healthy. |
  | `request_relationships_require_exact_returned_fields` | Prefix/time/service/topology similarity creates no join; literal RFQ/order/trace matches do; retransmission retains one economic order; unlinked metrics remain service-level. |
  | `filters_are_display_only_and_do_not_mutate_sources` | Service affects metrics/logs, metric only metrics, request only business selection/explicit highlights; invalid ranges rejected; cutoff does not stretch coverage; deep equality of entire input before/after. |
  | `review_preserves_values_reasons_and_absence` | Verbatim ordered original/final collections, missing/null/empty distinct; recorded `field`, `stage`, `reason` retained; repeated paths counted once; generic reason not promoted to a specific error; unknown paths/project notes/playback result separate. |

  Include direct assertions such as `assert.equal(samplePosition(60_000, {startMs:0,endMs:300_000}), 0.2)` and `assert.equal(formatRecordedDecimal('9007199254740993.25'), '9,007,199,254,740,993.25')`. A single-time coverage places its observation at the center, never divides by zero.
- [ ] Run red: `pnpm --filter @creditops/web exec tsx --test tests/recorded-evidence.test.tsx tests/recorded-review.test.tsx`. Missing exports initially fail; once typed seams exist, confirm the behavioral assertions fail against placeholders rather than accepting compilation as proof.
- [ ] Implement `projectRecording` and the scoped source/typed lane projections.
- [ ] Implement filter/coordinate/domain/relationship helpers without changing source objects or adding inferred observations.
- [ ] Extract exact decimal formatting and returned-event grouping/count logic; keep live `BusinessImpactContent` rules unchanged. Unknown request identity is labeled unknown, never counted as an identified RFQ.
- [ ] Implement the fixed review field list: summary/domain/condition, observations/supporting IDs, cause/triggers, unknowns/limitations, alternatives, recommendations, runbooks/history, review requirement, score and all RCA fields. Preserve unfamiliar change paths in `otherChanges`.
- [ ] Declare shared draft types, then run green with the red command plus `pnpm --filter @creditops/web exec tsx --test tests/business-impact.test.tsx tests/assessment.test.tsx` and `pnpm typecheck`.

**Acceptance:** all three projections match returned values/IDs; no input mutation, cross-record lookup, new diagnosis or floating-point money arithmetic. Review reasons remain recorded statements, not new factuality judgments.

## Slice 2 — Workspace shell and linked evidence timeline

**Depends on:** Slice 1. **Files:** new workspace/timeline components and `recorded-workspace.test.tsx`; modify `incidents.tsx`, `console.tsx`, `investigator.tsx`, `business-impact.tsx`, `evidence-drawer.tsx`, `globals.css`, existing `e2e/showcase.spec.ts`. Reuse `Panel`, `Badge`, `Citation`, `Empty`, `time`, Console's `onEvidence`, existing modal protections and recorded business presentation. Leave `TelemetryChart` unchanged.

**Interfaces:** `RecordedIncidentWorkspace({recording:RecordedRecording, sessionId:string|null, onEvidence:(id:string)=>void, onSourceControls:(controls:RecordedSourceControls|null)=>void})`; `RecordedEvidenceTimeline({recording:RecordedRecording, filters:WorkspaceFilters, selectedSourceId:string|null, onFilters:(value:WorkspaceFilters)=>void, onSelect:(id:string)=>void})`.

Define `RecordedSourceControls` in the workspace module with `investigationId`, `incidentId`, `sourceId`, `hiddenByFilters`, `pinned`, `onReveal():void`, `onTogglePin():void`. Console accepts controls only for its current investigation/incident/drawer ID and clears them with existing generation/selection cleanup. Add optional `recordedControls` to `EvidenceDrawer`; absence preserves legacy behavior. Session context arrives through optional `workspaceSessionId`/source-controls callback in the existing `incidentProps` bundle. Obtain existing `sessionId()` after client initialization, never in pure helpers or SSR.

Export small read-only blocks from `investigator.tsx`: existing `AssessmentResult` and extracted `RecordedInvestigationActivity({investigation,onEvidence})`/`RecordedInvestigationProvenance({investigation})`; export existing `RecordedBusinessImpact({investigation,onEvidence})`. Keep legacy `Investigator`, `AssessmentComparison`, `selectionLabel`, `assessmentOrigin` and `isValidationStep` behavior. Shared extraction must preserve rendering in both consumers; do not mount run/mode controls inside the recorded workspace.

- [ ] Add static tests named `only_matching_showcase_replay_uses_workspace`, `workspace_absence_is_explicit`, `timeline_table_equals_discrete_sources`, `overlap_retains_all_sources`, `legacy_attribution_survives_extraction`. Assert four named tabs, source/UTC/unit equality, no data-connecting SVG paths/filled areas (axis/grid lines are allowed), accurate original versus playback labels, absent assessment without fixture answer, and legacy controls still present.
- [ ] Add browser cases prefixed `workspace shell:` in existing `showcase.spec.ts`: Arrow/Home/End moves tab focus, Enter/Space activates; marker/table opens exact drawer; overlap chooser lists every tied source; filter hides but retains selection; explicit Reveal adjusts filters; closing drawer preserves highlight and restores trigger focus. Missing context token cannot trigger current-evidence lookup.
- [ ] Run red: `pnpm --filter @creditops/web exec tsx --test tests/recorded-workspace.test.tsx`; then `pnpm --filter @creditops/web exec playwright test --config=playwright.showcase.config.ts --grep "workspace shell:" --retries=0`. Expect missing shell/roles/selection behaviors, not a provider request.
- [ ] Extract the read-only investigator/business blocks with existing attribution tests unchanged.
- [ ] Gate `IncidentView` with `projectRecording`; render an explicit blocked state for ambiguous/mismatched showcase data. Keep current legacy branches and all routes.
- [ ] Implement local header and manual-activation ARIA tabs; reset section/filters/selection on recording changes. Show coverage separately from cutoff, condition separately from unconfirmed cause, and technical provenance/scores secondarily.
- [ ] Implement discrete SVG metric/log/business lanes and accessible table from `TimelineView`. Use actual time distance, separate units, overlap chooser, out-of-coverage context list, bounded UTC start/end inputs, visible range errors and empty/unplottable messages. Selecting an instant highlights its actual matching observations across lanes without implying causality; assert this in the linked timeline browser test.
- [ ] Wire selections to Console's existing source callback; keep selected-source highlight separate from modal visibility. Guard optional drawer pin/reveal callbacks against stale recording identities.
- [ ] Add scoped responsive styles, then run green with both red commands, `pnpm --filter @creditops/web exec tsx --test tests/showcase.test.tsx tests/evidence-first-provenance.test.tsx`, `pnpm --filter @creditops/web lint`, `pnpm typecheck`.

**Acceptance:** source fidelity and drawer focus hold across filtering/record changes; filters do not rerun assessments; legacy views retain behavior. Pins may remain disabled with a clear pending state until Slice 3 supplies personal-state controls.

## Slice 3 — Readable review and personal workspace state

**Depends on:** Slices 1–2. **Files:** new review component, `workspace-notes.ts`, `workspace-notes.test.tsx`; extend review/workspace tests; modify workspace, Console/reset, drawer controls, CSS and showcase E2E. Reuse recorded review projection, legacy raw comparison, current session identifier and reset endpoint. Do not reuse `lib/storage.ts` for notes: it uses `localStorage` and silently swallows errors.

**Interfaces:** `RecordedAssessmentReview({review:RecordedReview, sources:ReadonlyMap<string,Evidence>, onEvidence:(id:string)=>void})`; notes live in a distinct labeled workspace panel. In `workspace-notes.ts`, export:

```ts
type PersonalState = { note:string; pinnedIds:readonly string[] };
type NotesScope = RecordingIdentity & { sessionId:string };
type NotesStorage = Pick<Storage, 'getItem'|'setItem'|'removeItem'|'key'|'length'>;
type NotesResult = { state:PersonalState;
  status:'stored'|'empty'|'memory-only'|'invalid'; message:string|null };
notesKey(scope:NotesScope): string;
loadNotes(storage:NotesStorage|null, scope:NotesScope, sources:ReadonlyMap<string,Evidence>): NotesResult;
saveNotes(storage:NotesStorage|null, scope:NotesScope, state:PersonalState,
  sources:ReadonlyMap<string,Evidence>): NotesResult;
clearNotes(storage:NotesStorage|null, scope:NotesScope): boolean;
clearIncidentNotes(storage:NotesStorage|null, sessionId:string, incidentId:string): boolean;
```

Use a versioned namespace `creditops-workspace:v1:` plus safely encoded scope parts. Missing source identity means no durable key. `clearIncidentNotes` validates namespace/key scope and removes only this session/incident's versions; `clearNotes` affects one record. Validate shape, 4,000/20 bounds, unique pins and exact returned membership; do not truncate malformed stored records silently. Storage failures preserve current memory state and explicit refresh-loss warning; malformed entries expose a current-entry reset.

- [ ] Write `notes_scope_bounds_and_storage_failure`, `notes_reset_is_captured_and_success_only`, `review_is_readable_verbatim_and_inert` tests. Assert distinct version/session/incident keys; refresh restores own state; no other recording's pins; boundary lengths accepted and overbounds rejected; throwing/null storage remains memory-only; malformed values invalid; hostile note/proposal/log text escaped. Verify original/final values and recorded reasons with `renderToStaticMarkup`.
- [ ] Extend browser cases prefixed `workspace notes:`: refresh restores note/pins but Overview/full filters; record switches restore only its own entry; separate tabs do not synchronize edits; denied/full storage warning; malformed-entry clear option; reset filters keeps state; successful scenario reset clears captured incident only; failed reset and late selection changes retain correct notes. No investigation POST on refresh or personal edits.
- [ ] Run red: `pnpm --filter @creditops/web exec tsx --test tests/workspace-notes.test.tsx tests/recorded-review.test.tsx tests/recorded-workspace.test.tsx`; run matching showcase browser tests with `--grep "workspace notes:" --retries=0`.
- [ ] Implement bounded storage helpers with injected storage; access `sessionStorage` only at browser lifecycle/events and catch denial at acquisition too.
- [ ] Implement readable Field / Original model proposal / Recorded advisory rows and mobile cards. Preserve collection order, generic recorded reasons and unique normalization counts; retain unknown paths, project review categories and playback validation in separate labeled sections. Membership-check citations; missing sources remain unavailable text. Keep raw JSON secondary.
- [ ] Add note/pin state and accurate storage feedback, plain-text rendering, 20-pin cap, current-record clear action and drawer pin controls. Never include notes in investigation objects.
- [ ] Capture reset session/incident scope before `stopInvestigation`; clear matching notes only after successful existing reset POST. Add the stated reset effect beside the existing control; preserve abort/generation/selection guards and failed-reset data.
- [ ] Run green with the red commands plus existing showcase/provenance tests, web lint and typecheck.

**Acceptance:** readable comparison is faithful, not a newly graded response; tab-local persistence survives only its intended scope. Record switch, failed reset, malformed storage and disabled persistence cannot overwrite another record or claim durable/team approval.

## Slice 4 — Handoff composition and export

**Depends on:** Slices 1–3. **Files:** implement existing new `lib/incident-handoff.ts` types, create handoff component/tests, modify workspace/CSS/showcase E2E. Reuse full `RecordedRecording`, `RecordedReview`, exact business/decimal helpers and existing citations. No browser API in the pure composer.

**Interfaces:** `prepareHandoff(recording:RecordedRecording, review:RecordedReview, options:{template:HandoffTemplate; preparedAt:string; pinnedIds:readonly string[]; includePinnedAppendix:boolean}): HandoffDraft`; `handoffMarkdown(draft:HandoffDraft): string`; component `IncidentHandoff({recording:RecordedRecording, review:RecordedReview, pinnedIds:readonly string[], onEvidence:(id:string)=>void})`. One explicit Prepare action captures an ISO timestamp; preview/copy/print consume the same draft. Reprepare is local only.

- [ ] Write `handoff_full_scope_survives_filters_and_pins`, `handoff_sources_and_material_unknowns_survive_both_templates`, `handoff_allowlist_excludes_personal_and_private_data`, `handoff_missing_assessment_does_not_invent_answer`. Assert all material unknowns/limitations/project cautions present in both drafts; every source appendix ID is returned; unavailable references labeled; null initiating cause remains unconfirmed; economic-order retransmission/ACK uncertainty preserved; no inferred fill/loss/recovery. Composer has no notes/filter/clock parameter.
- [ ] Add metadata/config/session/usage/machine-path canaries in **unknown fields** and verify they cannot enter either export; deep-compare input before/after. Assert `draft.preparedAt` appears identically in Markdown/static preview/print markup, separately from observation/generation/export timestamps. Export only explicit source fields: ID/kind/service/timestamp plus metric/value/unit, log message/severity or business event/explicit request identifiers and exact decimal strings. Never serialize arbitrary `data` or raw JSON.
- [ ] Add browser tests prefixed `workspace handoff:`: prepare technical and stakeholder drafts, Clipboard success feedback, rejected Clipboard produces selectable identical Markdown, print media excludes navigation/controls/notes/raw panels while retaining full sources/limitations. Verify draft preparation/export adds no fetch/investigation request.
- [ ] Run red: `pnpm --filter @creditops/web exec tsx --test tests/incident-handoff.test.tsx`; run showcase tests with `--grep "workspace handoff:" --retries=0`.
- [ ] Implement deterministic full-record technical/stakeholder sections using recorded advisory/event fields and qualified condition/cause wording. Use fixed connective copy, not generated paraphrases. Recommendations remain proposed checks. Include all material limitations and review cautions in a labeled appendix, even in the short stakeholder view.
- [ ] Implement source appendix and optional labeled pinned highlights without narrowing overall scope; reject unsafe identity before composition. Unknown IDs remain unavailable, never silently repaired.
- [ ] Implement prepared-draft state, preview and Markdown; add guarded clipboard success/failure and browser print. Render all strings inertly and keep notes outside the draft tree.
- [ ] Add white print styles with intact headings/sources, sensible breaks and wrapping IDs; run green with red commands, web lint/typecheck and `pnpm build`.

**Acceptance:** technical and stakeholder drafts derive from one full-record representation, with complete uncertainty/source context; copy/print agree, never send or approve anything, and never include personal/private fields.

## Slice 5 — Integration, visual QA and release preparation

**Depends on:** Slices 1–4. **Files:** existing `showcase.spec.ts`, relevant existing web tests, the new test files in the responsibility map as needed, `globals.css` for bounded corrections, `docs/DEMO_SCRIPT.md`, `docs/INTERVIEW_WALKTHROUGH.md`. No broad refactor or frozen backend changes. Reuse current startup/lifecycle tests, public-denial checks, local showcase launcher and normal CI.

- [ ] Add failing integration cases prefixed `workspace acceptance:` for all three recordings: Overview → Evidence → Review → Handoff, exact selected source/timestamp, returned business identity, note/pin isolation, original/final separation, refresh without new investigation, reset and malformed recording. Preserve previous assertions while navigating their new section locations; never drop safety assertions because selectors moved.
- [ ] Add delayed-response/switch tests for reused topology IDs and reset races; assert no stale drawer, source controls or personal state. Assert application-selected diagnostics/model decisions/validator steps remain distinct and playback adds no model/MCP calls.
- [ ] Pin actual keyboard/focus, reduced-motion, 1440/768/390/320px layouts and print tests. Only the accessible sample table may scroll horizontally; compare `scrollWidth` with viewport width for every section. Existing drawer Escape/trap/return-focus remains tested.
- [ ] Run red: showcase browser command with `--grep "workspace acceptance:" --retries=0`. Correct only newly exposed UI/integration defects inside this scope, then run green.
- [ ] Update walkthrough with actual tab flow, sample-versus-cutoff times, rule support versus original model support, personal notes' limits and full-record drafts. Retain: “The model selects diagnostic actions and proposes an assessment. MCP provides controlled access to evidence. A separate conservative rule layer checks and may normalize the output. I evaluate the model proposal and the final system output separately.” Clarify these selected recordings used four application-selected initial checks and immediate model assessment, with no model-selected diagnostic follow-ups; one developed synthetic set is not generalization or MTTR proof.
- [ ] Run the final verification matrix once on the candidate source; repeat only checks affected by subsequent changes/failures. Capture sanitized logs and report unavailable platform checks honestly.
- [ ] Capture genuine local screenshots after tests pass, under ignored `artifacts/local-validation/workspace-v2/`: `desktop-overview.png`, `evidence-source-drawer.png`, `review-recorded-reason.png`, `technical-handoff.png`, `stakeholder-handoff.png`, `mobile-evidence.png`, `mobile-review.png`, `print-sources-limitations.png`. Record viewport, incident, source IDs and candidate SHA. Do not run paid investigations or alter recordings for screenshots. Use browser print preview for manual page-break inspection; no new PDF dependency.
- [ ] Compare protected hashes and frozen-source diffs before/after; inspect only intended file changes. Owner reviews UI, screenshots, export text, preservation proof and test limitations before any publication request.

**Acceptance:** all three recordings work locally with existing safety/lifecycle behavior; no workspace-triggered provider/MCP calls or source edits; usable desktop/mobile/print presentation. No remote CI or deployment result is claimed until that separately authorized stage actually runs.

## Verification execution and preservation

The following are **future commands**, not results. Run from the isolated worktree root. New focused `.test.tsx` names are collected by the existing `tsx --test tests/*.test.tsx` harness. Static rendering checks text/escaping; actual effects and events belong to Playwright.

Use the existing `createShowcaseEnvironment(parent)` from `scripts/showcase.mjs` for a credential-free child environment, with `CREDITOPS_ENV_FILE` explicitly present as `''`, `PUBLIC_DEMO=true`, embeddings disabled, persisted telemetry and loopback endpoints. Strip provider/admin keys and inherited `CREDITOPS_TEST_DATABASE_URL`; do not print environment values. Keep `E2E_EXTERNAL_SERVER` and remote base-URL overrides absent. Do not rely on a PowerShell empty assignment that may remove the dotenv key.

For local legacy E2E/evaluation only, override that child environment to a fresh absolute SQLite database under `artifacts/local-validation/workspace-v2/` and `REPLAY_DIR=<worktree>/data/replay`; use `CI=1` to avoid stale-server reuse and explicitly disable browser retries. An ignored one-off child launcher may use Node's `spawnSync` with this environment and the repository commands below; it is verification plumbing, not a new product runner/framework. Reserve loopback ports 8000/3000 after checking ownership; do not terminate unrelated processes. The showcase launcher already provides a dedicated keyless local database. Production URLs and databases are excluded.

| Final command | Required evidence |
|---|---|
| `pnpm test` | Full offline Python/API/MCP suite, dependency/startup checks, all web units. Root `conftest.py` disables owner dotenv during collection and blocks external HTTP transports. |
| `pnpm lint` | Existing Ruff and web ESLint pass. |
| `pnpm typecheck` | Existing Next type generation/TypeScript pass. |
| `pnpm build` | Production frontend build pass; no deployment. |
| `pnpm test:lifecycle` | Owned launcher teardown; Linux-only cases must be completed in normal CI if skipped on Windows. |
| `pnpm --filter @creditops/web exec playwright test --retries=0` | Legacy local browser suite; isolated child environment above, no external server. Equivalent existing root entry: `pnpm e2e`. |
| `pnpm --filter @creditops/web exec playwright test --config=playwright.showcase.config.ts --retries=0` | All keyless showcase browser checks. Equivalent root entry: `pnpm e2e:showcase`. |
| `pnpm audit --audit-level high` | Existing dependency policy; read-only vulnerability-service access may be needed. |
| `node scripts/python.mjs -m pip_audit` | Python dependency audit; report unavailable network honestly. |
| `node scripts/python.mjs -m bandit -r apps/api/creditops apps/mcp/creditops_mcp -ll` | Existing static security checks unchanged. |

Verify browser collection with `pnpm --filter @creditops/web exec playwright test --config=playwright.showcase.config.ts --list` before the first integration pass. Root `pnpm test` does not include browser or lifecycle checks. Real local MCP tests are in the Python suite; their isolated/scripted results are integration evidence, not new live-model quality.

**Evaluator preservation:** do not run default `scripts/evaluate.py` in the implementation checkout: it rewrites `artifacts/eval/latest.*` and `data/replay`. `scripts/robustness.py` likewise rewrites its default latest outputs; neither provides safe redirect CLI flags. Reuse existing APIs in an ignored one-off local validation file, with the isolated environment set before imports and a fresh explicit Store URL:

```python
store = Store(fresh_local_sqlite_url)
await store.initialize()
try:
    await run_evaluations(store, provider_name="deterministic",
                         output_dir=validation_dir / "eval", generate_replay=False)
finally:
    await store.close()
report = evaluate_robustness(validation_dir / "robustness")
if report["failed"]:
    raise SystemExit(1)
```

Imports are existing `creditops.store.Store`, `creditops.evaluation.run_evaluations`, `creditops.robustness.evaluate_robustness`; run via `node scripts/python.mjs artifacts/local-validation/workspace-v2/evaluate-preserved.py`. `fresh_local_sqlite_url` and `validation_dir` refer only to that worktree's fresh ignored validation paths. Seeding this disposable test database is allowed during later local testing, never against original/hosted resources. Preserve original labels/outcomes and evaluator caveats.

Secret scanning uses the pinned Gitleaks image/digest and `.gitleaks.toml` from `.github/workflows/ci.yml`, with redaction and nonzero enforcement. Verify installed scanner help before selecting current-tree versus Git-history mode; scan uncommitted candidate source too, not only history. If Docker/scanner/audit access is unavailable locally, record the gap and require the existing CI `secrets`/audit checks before release; do not install system-wide tooling or treat a skipped scan as passing.

Before/after hash comparison must include protected source recordings, replay/benchmark artifacts and historical local receipt/ledger/approval files through their current local preservation manifest. `git diff --exit-code -- apps/api apps/mcp data artifacts/eval artifacts/robustness scripts infra .github package.json pnpm-lock.yaml requirements.lock pyproject.toml` must show no frozen tracked changes. Also check `.env` ignored/untracked and untouched; never include it or ignored diagnostics in a commit. Workspace interactions add no API fetch: retain existing browser diagnostics counters plus offline provider/MCP replay tests, not merely the claim that the key is absent.

## Owner gates and completion evidence

1. **Before implementation:** owner reviews this plan and selects native execution or subagent-driven execution. No implementation has begun.
2. **Before publication:** inspect actual local behavior/screenshots/print, exact diff, faithful proposal/advisory reasons, source hashes and checks. Read-only review of actual Vercel/Railway triggers must precede explicit branch/SHA publication approval. Do not push to discover trigger behavior.
3. **After approved publication:** normal `.github/workflows/ci.yml` runs Python/PostgreSQL/MCP/evaluation/security, web lint/type/unit/build/audit, Linux lifecycle and both browser profiles in disposable CI checkouts. Record actual source SHA, run link and job results; generated CI outputs do not replace archived repository data. Any host deployment caused by publication must already be within that publication approval.
4. **Before production deployment:** owner reviews verified candidate SHA and actual allowed deployment effects. Deployment is separate from local commits and remote CI; preserve the current deployed demo until authorized. No cloud/architecture change follows automatically from this plan.

No conflict with the approved design was found. Source constraints determine the implementation: [telemetry-chart.tsx](../../../apps/web/src/components/telemetry-chart.tsx) lines 28–38 uses index-based filled lines, so the recorded timeline is a separate component; [storage.ts](../../../apps/web/src/lib/storage.ts) lines 1–20 uses silent `localStorage`, so explicit injected `sessionStorage` helpers are required; [evaluate.py](../../../scripts/evaluate.py) line 15 and [robustness.py](../../../scripts/robustness.py) line 8 call generators with default history-writing destinations, so final local evaluation uses existing redirected APIs. [console.tsx](../../../apps/web/src/components/console.tsx) line 139 derives `showcaseProfile` from the listing, which does not prove a selected recording's identity; the new projection gate remains necessary. These are implementation seams, not reasons to reopen settled features.

Stop after plan review. Product implementation, branch creation, publication and deployment remain unstarted and require their stated owner gates.
