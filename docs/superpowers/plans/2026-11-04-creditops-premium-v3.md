# CreditOps Premium V3 Implementation Plan

> For agentic workers: implement the bounded tasks with test-first changes and independent review. User explicitly chose direct execution from the supplied Premium V3 brief; do not add another design approval round.

**Goal:** Improve institutional readability and recorded-investigation comprehension without changing diagnostic meaning or backend behavior.
**Architecture:** Preserve Console lifecycle, routes and four manual workspace tabs. Add a scoped visual token layer, pure recording projections and two optional client-only components; reuse exact-source drawer and handoff interfaces.
**Tech stack:** Existing Next16.4.1/React19.3/TypeScript/Lucide/CSS, pnpm11.25.0, Playwright1.64.0. No dependencies added or upgraded.
**Spec:** Owner's November4 PremiumV3 brief, summarized below; baseline eb9943ac9011dc74c3683c2bbd1ece6f34b59428.

## Constraints and recorded decisions

- Existing architecture, backend/API/MCP/models/prompts/validation/scores/migrations and security/hosting configuration remain frozen.
- data/showcase, replay, original proposals/assessments, evidence IDs/timestamps and legacy evaluation values are immutable inputs.
- Local QA is credential-free with isolated SQLite and loopback services. No hosted DB, model call, new poller or telemetry.
- Existing navy/teal/amber identity; neutral system sans stack without network fonts;15–16px reading text,12–14px secondary,28–36px page headings,18–22px sections. Monospace only identifiers/timestamps/technical data.
- Use restrained180ms transitions and explicit reduced-motion/print rules. No decorative fake activity or invented values.
- No new routes. Notes/pins stay tab/session/recording scoped; guided mode resets on recording identity and never starts investigation.
- Explorer distinguishes explicit per-claim references from assessment-wide references. Resolve only returned top-level recording sources. Absent/null/missing references and unconfirmed causes remain explicit.
- Static overview workflow describes recorded application-selected checks, model proposal, separate rule validation and human handoff; no asset generation or model activity.
- Independent implementation ownership: coordinator owns tokens/screen polish/browser QA; bounded contributor owns conclusion projection/explorer/guide/workspace integration and focused units. Avoid shared-file writes.

## Review focus

1. Plain assessment strings have no claim-specific evidence edges: label whole-assessment support separately; test no invented edges.
2. Empty, null, unavailable and hostile proposal/reference data must remain inspectable and inert; no silent normalization.
3. Switching/rerunning the same incident may not retain guide/claim state from another recording; browser test source identity, notes and all six loaded transitions.
4. Async source controls/drawer focus and sticky layout must remain keyboard-accessible without unrelated render focus resets; retain existing tests.
5. Styles may not obscure print citations, offscreen filtered selections, reduced-motion controls or320px content; measure browser boxes/fonts/contrast and print styles.

## Task 1 — Visual system and entry/navigation

Files: app layout/new premium CSS layer; views/overview; Console navigation markup only; new focused presentation test and browser assertions.
- [ ] Observe baseline source, all screens and typography RED before visual changes.
- [ ] Add coherent background/surface/border/text/accent/spacing/radius/state tokens and sensible component font hierarchy; preserve viewport/sticky/focus safeguards.
- [ ] Refine hero/scenario cards and replace decoration with truthful static evidence workflow. Group existing nav links without changing paths.
- [ ] Verify semantic labels, selected/focus states, mobile navigation and reduced motion; compare screenshots.
- [ ] Review and commit intended visual-system files only.

## Task 2 — Recording workspace and reference screens

Files: views/incidents, evaluations, reference; relevant component styles; targeted unit/browser tests.
- [ ] Add and observe a failing scenario-preview test, using only Scenario metadata.
- [ ] Replace oversized unloaded state with selected metadata preview; preserve loading/error/ready checks and explicit run action.
- [ ] Improve Evidence timeline/filters/tooltips, original/validation/advisory reading order, handoff controls/copy/print and selected source readability through existing components.
- [ ] Visually separate selected recordings from legacy benchmark; preserve all values/denominators/qualifications.
- [ ] Improve existing architecture grouping/labels based on current docs. No new integrations or synthetic-real connection claims.
- [ ] Review and commit intended screen-polish files only.

## Task 3 — Recorded conclusion explorer and optional guide

Files: lib/recorded-conclusions.ts; components/evidence-conclusion-explorer.tsx; guided-recording-replay.tsx; minimal recorded-incident-workspace integration; tests/recorded-conclusions.test.tsx.
- [ ] Write focused tests; centrally observe RED for absent modules.
- [ ] Implement pure immutable claim/reference projection, original/final separation, explicit missing support and recorded limitations. Reuse onEvidence; never fetch unavailable sources.
- [ ] Implement optional Next/Previous/Exit guide for Signal→Evidence→Model proposal→Validation→Handoff. Keep manual tabs, no autoplay or requests, focus only explicit navigation.
- [ ] Observe unit GREEN, browser real-keyboard/source/filter/recording reset/network isolation tests.
- [ ] Independent factuality/accessibility review, resolve substantive findings, commit.

## Task 4 — Final local qualification and branch publication

- [ ] Run full relevant frontend units, lint, types, build, dependency/startup and detector/lifecycle checks; run legacy and complete showcase under existing supervisor, zero retries, unchanged configured parallelism.
- [ ] Run targeted V3 browser coverage at320/390/768/1024/1440/1920; inspect actual contrast, focus, bounds, guide/explorer, selection/restoration, copied draft and print. No silent skips/retries.
- [ ] Capture all seven requested screen categories plus mobile nav/workspace before/after in fresh ignored outputs. Measure same-runtime bundle/asset and page timing differences; qualify CWV limits.
- [ ] Verify frozen trees and hashes, original main/env/user work, dependency pins, public restrictions and Git secret checks. Document any unavailable/failed checks honestly.
- [ ] Final independent branch review and concise actual walkthrough/report. No broad backend rerun for frontend-only changes; preserve source binding of existing backend evidence.
- [ ] Re-read hosting suppression/branch triggers and remote feature history; push only feature/creditops-premium-v3 normally to private repo. No PR, merge or deployment.
- [ ] Inspect automatic CI and read-only production records; retain source-bound screenshots/report and READY FOR VISUAL REVIEW or BLOCKED decision.

## Implementation decisions and review

- Owner chose direct execution from the brief and later explicitly authorized feature-branch publication to the existing **public** repository after read-only GitHub inspection found it was not private. No visibility change is authorized or performed.
- Independent review found short-desktop sidebar overflow. Actual Tab navigation reproduced a focused but offscreen last destination; bounded scrollable nav fixes it without removing routes. Production browser regression passes.
- Explorer uses one independently selected full claim per origin, keeping all other claims available in native selectors and the complete comparison. Context/whole-assessment references use labeled native details, avoiding an additional wall of duplicated prose.
- Added10 focused browser cases: citation/state isolation, all5 guide stages with native keyboard input, exact unloaded metadata, short-desktop nav and6 required widths. Existing browser assertions/configuration remain intact.
- Native SVG source titles and discrete sample model remain. Visual marker/focus/selection and surrounding labels improve; no continuous chart or inferred causal edges are added.

- Full showcase exposed a375px sticky header occluding the native-scrolled tab at1024�768. A scoped short-tablet/desktop breakpoint keeps that readable block in normal flow instead of shrinking text or weakening hit-test assertions. Original dark canvas token is retained, preserving the existing print-to-screen restoration check.
