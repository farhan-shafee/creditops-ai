# Interview walkthrough

## Thirty seconds

“CreditOps AI is an independently built incident-intelligence portfolio project using synthetic electronic credit trading data. An operator runs an RFQ, FIX or database incident, observes changing telemetry and follows a read-only investigation that cites actual evidence. It combines a typed operations API, MCP diagnostics, configurable AI providers and a reproducible evaluation harness. Public replay is explicitly labeled and works without AI keys. It does not connect to a trading venue or perform remediation.”

## Two minutes

Follow `DEMO_SCRIPT.md`. Start with the problem: information is fragmented across logs, metrics, dependencies, application changes and protocol state. Show the incident, then the bounded diagnostic trace, then an evidence drawer. Explain the human-review draft and missing mutation tools. End on generated evaluations and honest limitations.

## Ten-minute technical walkthrough

1. **0–2 minutes:** RFQ service graph and three different failure domains. Explain why high latency alone cannot distinguish a consumer backlog, unstable FIX session or exhausted DB pool.
2. **2–4 minutes:** Run a scenario; inspect the synthetic timestamps, delayed evidence reveal, stable IDs and session scope. Show healthy negative controls.
3. **4–6 minutes:** Read the allowlist and investigator prompt. Explain model-selected bounded queries, untrusted telemetry, redaction, typed assessment and citation validation. Replay comes from pipeline artifacts with explicit deterministic provenance.
4. **6–7 minutes:** MCP stdio client configuration, schemas and registration test. Explain why simulation controls are API-only and never agent tools.
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

**How is a recent deployment handled?** It is supporting temporal evidence, not proof of causality. The investigation correlates pool pressure, waits and timeout logs, and the draft asks the operator to validate the change.

**Can this handle institutional scale?** The patterns transfer, but this implementation needs durable jobs, shared budgets, tenant-aware queries, retention, enterprise identity, on-call integrations and independent evaluations before real deployment.

**What did you independently build?** The application, synthetic scenarios, evidence contracts, diagnostic facade, provider orchestration, evaluation harness and operations experience. No proprietary infrastructure or incidents were used. This is a portfolio demonstration, not claimed customer adoption.
