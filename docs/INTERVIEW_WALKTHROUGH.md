# Interview walkthrough

## Thirty seconds

“CreditOps AI is an independent incident-intelligence portfolio using entirely synthetic credit-trading data. Its keyless showcase plays three completed model-assisted runs. The application selected four initial read-only checks through MCP; a real model chose assessment and proposed an outcome; separate local validation produced the conservative advisory draft. You can inspect affected RFQs/orders, recorded evidence and the original wording. These selected development examples require human review and do not prove autonomous investigation, general accuracy or production time saved.”

## Two minutes

Run `pnpm showcase` from the repository root and follow [DEMO_SCRIPT.md](DEMO_SCRIPT.md). Choose **View recorded investigation**, explain the trading problem and affected requests, inspect the attributed trace, click recorded evidence, compare **Original model proposal and review notes** with the advisory outcome, then open **Selected recorded synthetic examples** in Evaluations. Use UTC consistently. The complete recorded snapshot may contain later evidence than the visitor's current simulated animation.

## Five-minute technical walkthrough

1. **0–1 minute:** Start with the business problem. Pricing has stale/unavailable quotes and RFQ expiry; FIX has pending/uncertain ACKs and retransmission of the same economic order; DB has waits, processing timeouts and RFQ expiry. No evidence establishes fills, financial loss or revenue impact.
2. **1–2 minutes:** Inspect `evidence_first_v1`: application-selected `get_incident`, `get_service_topology`, `query_metrics`, `search_logs`; one model decision selecting assessment; one model assessment; local validation. All three recordings contain zero model-selected diagnostic follow-ups.
3. **2–3 minutes:** Open a recorded evidence ID and source provenance. Original generation time, export time, playback time and observation time have different meanings. Returned samples end at 2026-10-09 14:02:24 UTC, before the 15:00 UTC cutoff.
4. **3–4 minutes:** Compare original structured prose, validation outcome and final assessment. Model scores are 0.63/0.78/0.87; the final rule score is 0.84 for each. Both are uncalibrated. Validation normalized 19/17/19 distinct fields and accepted each known synthetic domain; neither fact independently verifies every original claim.
5. **4–5 minutes:** Open the three-example summary and [verification history](LIVE_VERIFICATION_REPORT.md). Earlier stopped attempts and model abstention remain preserved. The unchanged 15-case benchmark and separate 13-case robustness suite are developer-authored fixtures. Finish with the public paid-action boundary and [deployment handoff](DEPLOYMENT.md): dedicated API, database and frontend, with hosting plans/resources still requiring owner approval.

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
