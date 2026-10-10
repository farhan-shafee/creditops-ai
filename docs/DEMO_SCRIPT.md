# Recorded showcase demo script

From the repository root run `pnpm showcase`, then open `http://127.0.0.1:3000`. This isolated public profile reads `data/showcase`, uses its own local database, bypasses the owner's `.env` and removes provider/admin credentials. Playback makes no new model, embedding or MCP calls for the recorded steps. All displayed times are UTC.

## Thirty-second introduction

“CreditOps AI is an independent portfolio using entirely synthetic credit-trading data. These are three recorded model-assisted investigations: pricing backlog, FIX session instability and database pool exhaustion. The application collected four bounded checks through MCP, a real model selected assessment and proposed a diagnosis, and a separate local validator produced the advisory output. You can inspect the original evidence and wording without any keys. These selected development examples still need human review; they do not establish autonomous investigation, general accuracy or production time saved.”

## Two-minute click-through

| Time | Click | Say |
|---|---|---|
| 0:00 | **Pricing backlog** → **View recorded investigation** | “The quotes and RFQs are fictional. This plays the recorded model-assisted run, with no new paid calls.” |
| 0:20 | **Business impact / affected requests**; expand an RFQ | “The observed states are stale/unavailable quotes and RFQ expiry. Par amount is requested face value. These records establish no fill, financial loss or lost revenue.” |
| 0:40 | Recorded investigation trace | “The application selected incident context, topology, metrics and logs. The model made one decision to assess and one assessment. It selected no diagnostic follow-ups in this recording.” |
| 1:00 | Click a cited metric or business event | “This drawer opens the recorded object with its original timestamp. Returned samples end at 14:02:24 UTC; a 15:00 UTC cutoff is not continuous coverage.” |
| 1:20 | Conservative advisory output → **Original model proposal and review notes** | “The model identified backlog, but overstated some causal and trend claims. Validation accepted the domain and rewrote 19 fields using rules. That is not 19 independently proven errors. The initiating cause remains unknown.” |
| 1:45 | **Evaluations** → **Selected recorded synthetic examples** | “All three selected runs completed. Their original proposal and rule output are separate. Earlier failures and abstention remain documented; the legacy 15-case benchmark and 13-case developer-authored robustness suite are separate.” |

For FIX, inspect pending/uncertain acknowledgements and retransmission using the **same economic order identity**. An accepted quote, retransmission or missing ACK does not establish execution. In a real system, reconcile that order against authoritative venue/internal records before deciding what to do; never recommend blind resubmission. For database exhaustion, show DB wait, processing timeouts and RFQ expiry. A preceding change mentioned in context is unconfirmed because no deployment object was returned by this recording.

The complete recorded evidence snapshot may include events later than the visitor's current simulated animation. Call out the snapshot label and its cutoff. Distinguish original generation duration from playback time; neither measures human time saved.

## Five-minute technical review

1. **0:00–1:00:** Pick an example and trace the trading problem to the recorded RFQ/order events. Confirm UTC observation timestamps and sample coverage.
2. **1:00–2:00:** Inspect the four application-selected MCP steps, the single model assessment decision, original provider/model, recorded generation time and source provenance.
3. **2:00–3:00:** Compare the structured original proposal with recorded validation and final output. Valid evidence references check identity/type, not narrative truth or causation. Project review notes are not an independent audit.
4. **3:00–4:00:** Inspect technical scores: model 0.63/0.78/0.87 versus rule support 0.84 for each. Both are uncalibrated and are not accuracy percentages. The 19/17/19 changed-field counts reflect rule normalization.
5. **4:00–5:00:** Open the three-example results summary and [verification history](LIVE_VERIFICATION_REPORT.md). Explain public API denial of paid actions and the [dedicated-resource deployment handoff](DEPLOYMENT.md). Institutional use would require tenant-aware authorization, durable jobs/shared budgets, auditing, retention and independently held-out evaluation.

The [short local showcase video](screenshots/showcase-playback.webm) is recorded playback, with no new model calls. Genuine screenshots cover the [entry](screenshots/showcase-entry.png), [business events](screenshots/showcase-business-impact.png), [evidence](screenshots/showcase-impact-evidence.png), [proposal/validation](screenshots/showcase-proposal-validation.png), [advisory output](screenshots/showcase-final-advisory.png), [results](screenshots/showcase-results.png) and [mobile layout](screenshots/showcase-mobile.png).

If demonstrating **MCP · adaptive deterministic**, introduce it separately: it executes fresh read-only protocol calls using deterministic application rules. Do not merge its Kafka/FIX/database checks, runbook retrieval or history searches into a recorded live-model trace. The historical [deterministic video](screenshots/demo.webm) shows that separate experience. No cloud deployment or new provider experiment is part of this packaging milestone.
