# Interview walkthrough

## Thirty seconds

“CreditOps AI is an independently built incident-intelligence portfolio project using synthetic electronic credit trading data. An operator runs an RFQ, FIX or database incident, observes changing telemetry and follows a read-only investigation that cites actual evidence. It combines a typed operations API, MCP diagnostics, configurable AI providers and a reproducible evaluation harness. Public replay is explicitly labeled and works without AI keys. It does not connect to a trading venue or perform remediation.”

## Two minutes

Follow `DEMO_SCRIPT.md`. Start with the problem: information is fragmented across logs, metrics, dependencies, application changes and protocol state. Show the incident, then the bounded diagnostic trace, then an evidence drawer. Explain the human-review draft and missing mutation tools. End on generated evaluations and honest limitations.

## Ten-minute technical walkthrough

1. **0–2 minutes:** RFQ service graph and three different failure domains. Explain why high latency alone cannot distinguish a consumer backlog, unstable FIX session or exhausted DB pool.
2. **2–4 minutes:** Run a scenario; inspect the synthetic timestamps, delayed evidence reveal, stable IDs and session scope. Show healthy negative controls.
3. **4–6 minutes:** Read the allowlist and investigator prompt. Explain model-selected bounded queries, untrusted telemetry, redaction, typed assessment and citation validation. Replay comes from pipeline artifacts with explicit deterministic provenance.
4. **6–7 minutes:** Execute MCP mode and show transport/schema/cutoff provenance. Explain the real API-worker -> official SDK -> stdio server -> same-API integration and disconnect regression. Simulation controls remain API-only.
5. **7–8 minutes:** Docker PostgreSQL, Redpanda, Prometheus/Grafana. Distinguish real broker interaction from modeled lag and fictional FIX connectivity.
6. **8–9 minutes:** Labeled dataset, cheap log-signature baseline, corroborating pipeline, abstention and recall arithmetic. No real operator MTTR claim.
7. **9–10 minutes:** Discuss deployment boundary, multi-replica rate budgets, durable workers, tenant authorization, retention and held-out evaluation.

## Talking points

- **Architecture:** a bounded diagnostic facade separates operational data from AI orchestration. The web is a functional console backed by REST/SSE, not a chat transcript.
- **MCP:** typed read-only tools reuse backend contracts. Result bounds, redaction and protection remain necessary even though protocol discovery is standardized.
- **AI safety:** telemetry cannot add tools. The schema and allowlist constrain capability; citation validation checks grounding. Prompt wording alone is not the security boundary.
- **Kafka:** topic/partition/consumer-group state, ingress versus processing rate, lag and quote freshness; local broker events versus synthetic incident telemetry.
- **FIX:** heartbeats, sender/target sequences, reconnects, sequence gaps and uncertain acknowledgements. Connectivity does not prove execution state; human reconciliation matters.
- **Evaluation:** labels stay outside tools, distractors and insufficient evidence are explicit, latency is measured, and deterministic versus live-model runs are labeled accurately.

## Likely questions and honest answers

**Does this reduce MTTR?** It measures synthetic investigation latency and evidence retrieval. No human operator study was conducted, so it cannot support an actual MTTR reduction claim.

**Is the replay AI-generated?** The included artifacts use the deterministic provider through the actual collection and validation pipeline. The interface labels that fact. Live OpenAI/Anthropic planning and assessment is implemented but requires protected credentials and a separate measured run.

**How do you prevent prompt injection?** Treat telemetry as untrusted data, sanitize it, use typed allowlisted plans and expose no mutation or execution tool. Validate every reference. Test malicious logs and attempted forbidden tool names. A production system also needs identity, entitlements, auditing and monitoring.

**Why not automatically restart or roll back?** The platform is intentionally diagnostic. Changes need human causal verification, impact assessment and operational authority; uncertain evidence must not become a destructive action.

**What happens when Kafka is unavailable?** Persisted synthetic replay keeps the cloud demo usable. Local Kafka mode verifies real publication/consumption and reports broker connectivity separately; it does not fabricate a live broker.

**What is confidence?** For the deterministic provider it is an uncalibrated rule score based on independent signals. The UI and limitations say so. Live-provider confidence would also require calibration against held-out incidents.

**Why doesn't a recent deployment prove causation?** Saturation plus waiters/timeouts establishes a failure condition without any release record. Only a same-service change before onset is a candidate trigger. Other services' changes and later deployments cannot explain earlier symptoms. None of these fixtures establish a confirmed cause.

**How do you prove the investigator used MCP?** The real integration starts an async API worker, opens the official client, discovers verified schemas and invokes an owned stdio server that calls the API's diagnostic GET routes. It compares returned metric objects, asserts transport provenance and forces child termination to verify fail-closed behavior. The UI's keyless MCP mode executes that path with a deterministic provider; replay shows recorded steps.

**What can change the next tool?** After the same initial latency symptoms, actual consumer-lag results lead to Kafka inspection; pool-pressure results lead to database inspection. Scripted providers assert those different requests in offline tests. The live SDK receives previous sanitized results/errors before its next typed decision, but real model decisions have not been measured.

**How do you prevent a missing acknowledgement becoming a false failed order?** RFQ, quote, processing and acknowledgement states are separate event reductions. A valid accepted quote can create one pending economic order; missing acknowledgement becomes UNKNOWN. Retransmission retains that order ID. There is no inferred FAILED/EXECUTED state or blind resubmission recommendation. Reconcile the existing order with authoritative venue/internal records before acting in a real system.

**What does evaluation demonstrate?** Reproducible behavior on developer-authored synthetic fixtures: literal domain scoring, retrieval, abstention and ID validity. The unchanged 15-case benchmark exposes legacy causal-label mismatches and a risk fixture's later subthreshold telemetry. A separate 13-case suite tests declared support/trigger/uncertainty expectations. Neither is independently held out; zero invalid IDs is not zero hallucinations. Live-model execution is NOT RUN and quality UNVERIFIED.

**Which parts are simulated, recorded, direct or live?** Bonds, RFQs, orders, FIX and diagnostic incident metrics are synthetic. REPLAY plays direct-pipeline artifacts with original times and a complete cutoff. MCP_DEMO makes fresh protocol calls with deterministic adaptive rules. PostgreSQL, local Redpanda and SDK protocol transport are real. LIVE_AI is implemented and tested with mocked network responses only; no paid model or embedding call was made.

**How do you separate the model from the safety layer?** “The model selects diagnostic actions and proposes an assessment. MCP provides controlled access to evidence. A separate conservative rule layer checks and may normalize the output. I evaluate the model proposal and the final system output separately.” Sanitized structured proposals, changed/rejected fields, final assessments and actual execution metadata are separate records. A normalized domain or safe wording is not independent confirmation of every original model claim. A later live replay must identify the recorded investigation, original provider/model, original time/cutoff and zero new model calls during playback. Live requests remain NOT RUN pending the owner authorization in [LIVE_VERIFICATION_REPORT.md](LIVE_VERIFICATION_REPORT.md).

**What would you check before trusting a recommendation?** Inspect exact cited records and their cutoff, session, freshness and source; distinguish observed condition from trigger hypothesis; review missing/contradictory telemetry and tool errors; reconcile affected request/order IDs; confirm authorization, blast radius and rollback plans through human change controls. The limited known-domain rule gate is not a general factuality guarantee.

**Can this handle institutional scale?** The patterns transfer, but this implementation needs durable jobs, shared budgets, tenant-aware queries, retention, enterprise identity, on-call integrations and independent evaluations before real deployment.

**What did you independently build?** The application, synthetic scenarios, evidence contracts, diagnostic facade, provider orchestration, evaluation harness and operations experience. No proprietary infrastructure or incidents were used. This is a portfolio demonstration, not claimed customer adoption.
