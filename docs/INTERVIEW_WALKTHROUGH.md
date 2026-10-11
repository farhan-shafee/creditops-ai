# Interview walkthrough

## Thirty seconds

“CreditOps AI is an independent incident-intelligence portfolio using entirely synthetic credit-trading data. Its keyless showcase plays three completed model-assisted runs. The application selected four initial read-only checks through MCP; a real model chose assessment and proposed an outcome; separate local validation produced the conservative advisory draft. You can inspect affected RFQs/orders, recorded evidence and the original wording. These selected development examples require human review and do not prove autonomous investigation, general accuracy or production time saved.”

## Two minutes

Run `pnpm showcase` from the repository root and follow [DEMO_SCRIPT.md](DEMO_SCRIPT.md). Choose **View recorded investigation**, then use **Overview → Evidence → Review → Handoff**. All times are UTC. These selected recordings used four application-selected initial read-only checks and immediate model assessment, with no model-selected diagnostic follow-ups. Playback makes no new model, embedding or MCP diagnostic calls.

## Five-minute technical walkthrough

1. **0–1 minute — Overview:** Explain stale/unavailable quotes and RFQ expiry for pricing; pending/uncertain ACKs and same-order retransmission for FIX; waits, processing timeouts and RFQ expiry for DB. No event establishes fills, financial loss or revenue impact. The shared header retains the event-derived counts, recorded advisory condition and actual initiating-cause status across every tab. Original execution outcome is separate from playback status. Expand **Technical provenance and diagnostic activity** to inspect application checks, model decision/assessment and local validation.
2. **1–2 minutes — Evidence:** Choose service/metric, returned RFQ or economic-order filters, then inspect the exact source object. A shared plotted location opens its exact-source chooser; service metrics/logs visibly disclose non-attribution unless returned identities match. Discrete points retain their timestamps and units; the table supports keyboard inspection. Returned sample coverage ends at 2026-10-09 14:02:24 UTC; the 15:00 UTC collection cutoff is later metadata. Lane gaps mean no returned observations, not continuous health. Context annotations retain their recorded timestamps, labels and reference membership; context-only source tokens remain unavailable.
3. **2–3 minutes — Review:** Read the original proposal beside recorded advisory fields and recorded reasons. Model support 0.63/0.78/0.87 and rule support 0.84 are separate uncalibrated scores. Generic normalization is not proof of a specific prose error. The 19/17/19 unique normalized paths, project narrative cautions and current playback validation have different meanings. Valid source IDs do not establish prose accuracy.
4. **3–4 minutes — Personal notes and Handoff:** Pin a returned source and enter a personal, unverified plain-text note: 4,000 characters/20 pins maximum, this tab only, scoped to demo session/incident/source hash/export version. Display-filter reset retains them. Refresh restores that entry but returns view state to Overview/default filters; unavailable storage warns of refresh loss. Clear removes memory-only notes/pins locally while disclosing any stored entry that could not be removed and may reappear. Scenario reset cleans only its captured scope after backend success, disclosing cleanup failure and retry. **Prepare draft** creates a technical or short stakeholder draft with complete limitations and source appendices from the full recording, independent of filters. Notes are excluded; optional pin highlights do not narrow scope. Preview/Markdown/print share one preparation time. Inspect the draft before copy or browser Save as PDF.
5. **4–5 minutes — Limits:** Open the selected examples in Evaluations and [verification history](LIVE_VERIFICATION_REPORT.md). One developed synthetic set is not evidence of generalization or MTTR reduction. Earlier stopped attempts and abstention remain documented; the separate legacy 15-case benchmark and 13-case robustness suite retain their scope. Finish with public paid-action denial and the [deployment handoff](DEPLOYMENT.md).

“The model selects diagnostic actions and proposes an assessment. MCP provides controlled access to evidence. A separate conservative rule layer checks and may normalize the output. I evaluate the model proposal and the final system output separately.”

The adaptive architecture supports model-selected follow-ups, but these selected recordings do not demonstrate them: after four application-selected checks, each model immediately selected assessment. Do not substitute supported/tested capability for observed behavior.

For a longer architecture discussion, show REST/SSE session isolation, the typed read-only diagnostic facade, official MCP client/owned stdio server/fixed API callback, synthetic event reduction, local PostgreSQL/Redpanda and observability. Real local infrastructure and synthetic FIX/incident metrics are labeled separately.

## Likely questions and honest answers

**Is the replay AI-generated?** These three showcase copies preserve actual OpenAI `gpt-5.4-mini-2026-03-17` assessments and the separately recorded validation/final outputs. Playback calls no model, embeddings or MCP diagnostics. The historical `data/replay` artifacts and **MCP · adaptive deterministic** mode remain separate deterministic demonstrations.

**Why is initial triage application-controlled?** The fixed four checks provide bounded incident context, service topology, metrics and logs before the model chooses what to do. The application owns session/incident/cutoff scope, argument bounds and allowed capabilities. This makes the evidence floor and cost/security boundary reviewable instead of delegating those controls to untrusted model output.

**Did the model choose follow-up diagnostics?** No. In each selected recording it received the four application-selected checks and immediately chose assessment. The adaptive loop supports model-selected follow-ups and offline scripted tests exercise it, but these recordings do not demonstrate that behavior. No Kafka/FIX inspection, database inspection, runbook retrieval or historical-incident search should be invented in their traces.

**What does the model get right?** It proposes the supported pricing-backlog, FIX-instability and DB-pool failure domains and cites returned IDs. The original narrative also overstates some causes, trends, exclusions and time coverage. The expandable project review notes identify specific limitations. They are not an independent human audit or automatically proven factuality assessment.

**Why don't valid citations guarantee truthful prose?** A returned evidence ID proves which object is referenced and allows type/eligibility checks. It does not establish that the object supports every sentence, that correlation proves causation, that sampled values are monotonic or that sparse observations cover the full window. A model can cite a real metric and still describe its timing or implication incorrectly.

**Why are the scores different?** The model supplied 0.63, 0.78 and 0.87 in its proposals. The unchanged local rule layer generated 0.84 for each final known-domain assessment. Both are uncalibrated support scores, not probabilities, accuracy percentages or measured trust. Rule support is not “AI confidence”; the scores belong in technical details.

**Did validation detect 19/17/19 errors?** Those are distinct changed-field counts from conservative rule normalization. They do not establish that every changed field was an independently detected error. The domain-support gate and reference checks are narrower than general factuality verification, so original and normalized outputs remain separately inspectable.

**What is still unknown?** The initiating cause in every example. For pricing, backlog and staleness correlate without proving the cause of slowing consumption. FIX session instability does not identify a network/peer fault or establish final execution state. DB pool saturation does not establish why connections were exhausted or prove a release caused it. The 15:00 UTC cutoff does not fill the gap after returned samples end at 14:02:24 UTC.

**Does this reduce MTTR?** Recorded durations of 25.191, 19.019 and 16.138 seconds measure these executions. Playback duration is different, and no human operator study measured time saved or production MTTR reduction.

**What does evaluation demonstrate?** Reproducible behavior on developer-authored synthetic fixtures. The selected three completed recordings are development examples, not a held-out accuracy benchmark or three independent tests. Earlier failures and abstention remain in the project history. The separate legacy 15-case labels/results and 13-case robustness suite retain their original scope; zero invalid IDs does not mean zero hallucinations.

**What did the model cost?** The three selected receipts report usage-based estimates of USD 0.03333825, 0.03325425 and 0.03275025, totaling USD 0.09934275. Confirmed billing is unknown. Historical retained reservations across all attempts total USD 1.03060200 and remain unchanged. Neither figure is total hosting cost. This packaging milestone makes no new paid call.

**How do you prevent prompt injection and paid public calls?** Treat logs/model text as untrusted data, keep rendering safe, sanitize results, accept only typed allowlisted actions, bound inputs/results/deadlines and validate references. `PUBLIC_DEMO=true` rejects paid `LIVE_AI` and query embeddings at the API boundary even with an accidental fake-key canary. The local showcase also strips credentials and bypasses the owner's dotenv file. Session UUIDs isolate synthetic views but are not institutional authentication.

**How do you prove MCP was used?** The source recordings preserve actual `mcp_stdio` provenance, verified schemas, four dispatched initial diagnostics and their returned evidence. Integration tests exercise the official client, owned stdio server and fixed diagnostic callback. Playback replays those recorded steps without opening a new MCP connection. Deterministic MCP mode is a separate fresh protocol demonstration.

**What can change the next tool?** The adaptive implementation can use returned observations to choose bounded diagnostics, and scripted offline tests exercise alternate tool requests. These selected real-model recordings made no such follow-up selection. Do not substitute that tested capability for observed behavior in the demo.

**Why no restart, rollback or blind order resubmission?** This project is diagnostic and advisory. Unknown acknowledgements keep the original economic order identity; retransmission does not create another order or establish a fill. A real operator must reconcile authoritative venue/internal state and review impact, authorization and change controls before remediation.

**What would need to change before institutional use?** Enterprise identity/entitlements, tenant-aware evidence access, durable jobs, shared rate and spend budgets, retention, audit monitoring, freshness guarantees, independently held-out incident evaluation and operator usability studies. Model uncertainty would need calibration. Remediation would need separate operational authority and change controls. The current hosting handoff is a synthetic portfolio demo, not production readiness.

**Can a recruiter inspect this without GitHub access?** Yes: the local keyless console contains the recorded evidence, original proposal, validation, review notes and results. The eventual hosted demo would do the same after an owner-approved deployment. The repository is private; any source link requires authorized access and is labeled accordingly. No public URL is claimed now.

**What did you independently build?** The application, synthetic scenarios, evidence contracts, diagnostic facade, provider orchestration, separate validation, replay packaging, evaluation harness and operations experience. No proprietary infrastructure, customer incidents or institutional adoption are claimed.
