# Recorded showcase demo script

From the repository root run `pnpm showcase`, then open `http://127.0.0.1:3000`. This isolated public profile reads `data/showcase`, uses its own local database, bypasses the owner's `.env` and removes provider/admin credentials. Playback makes no new model, embedding or MCP calls for the recorded steps. All displayed times are UTC.

## Thirty-second introduction

“CreditOps AI is an independent portfolio using entirely synthetic credit-trading data. These are three recorded model-assisted investigations: pricing backlog, FIX session instability and database pool exhaustion. The application collected four bounded checks through MCP, a real model selected assessment and proposed a diagnosis, and a separate local validator produced the advisory output. You can inspect the original evidence and wording without any keys. These selected development examples still need human review; they do not establish autonomous investigation, general accuracy or production time saved.”

## Two-minute workspace click-through

| Time | Click | Say |
|---|---|---|
| 0:00 | **Pricing backlog** → **View recorded investigation** → **Overview** | “Synthetic · Recorded · Human review required. Original outcome and playback status are separate. These are affected fictional RFQs, not measured fills or revenue.” |
| 0:20 | **Overview** → expand **Technical provenance and diagnostic activity** | “Four initial checks were application-selected; the model immediately selected assessment. This recording has no model-selected diagnostic follow-up. Playback adds no model or MCP calls.” |
| 0:40 | **Evidence** → select service/metric and a returned request → click an exact source ID | “Discrete markers retain actual UTC timestamps; the table is the keyboard equivalent. Returned samples end at 14:02:24 UTC. The later 15:00 UTC cutoff is collection metadata, not another observation or continuous coverage.” |
| 1:00 | Change display filters → **Open selected source** → **Reveal source** | “Recorded assessment unchanged; filters do not rerun investigation. The selected source remains available. Request highlights use literal returned identities, not similarity or timing.” |
| 1:20 | **Review** → compare **Original model proposal** and **Recorded advisory** | “Recorded normalization reasons stay generic. Rule support and original model support are separate, uncalibrated scores. Valid returned IDs do not verify surrounding prose.” |
| 1:40 | Pin a returned source; enter a personal note → **Handoff** → **Prepare draft** | “Personal notes are unverified, this tab only: 4,000 characters and 20 pins maximum. They are excluded from exports. Technical and stakeholder drafts cover the full returned recording, including limitations and source appendices, regardless of filters.” |

Copy Markdown or **Print draft** for browser Save as PDF only after inspecting the draft. Both templates carry **Synthetic · Recorded · Draft · Human review required**. Changing the template or pin option requires **Reprepare draft**; preview, copy and print use one captured preparation timestamp. Clipboard denial exposes the same selectable Markdown for manual copying. No send or operational approval is performed.

For FIX, inspect pending/uncertain acknowledgements and retransmission using the **same economic order identity**. An accepted quote, retransmission or missing ACK does not establish execution. In a real system, reconcile that order against authoritative venue/internal records before deciding what to do; never recommend blind resubmission. For database exhaustion, show DB wait, processing timeouts and RFQ expiry. A preceding change mentioned in context is unconfirmed because no deployment object was returned by this recording.

The complete recorded evidence snapshot may include events later than the visitor's current simulated animation. Call out the snapshot label and its cutoff. Distinguish original generation duration from playback time; neither measures human time saved.

## Five-minute technical review

1. **0:00–1:00 — Overview:** Read event-derived impact, actual sample coverage and cutoff; inspect affected requests. Compare original outcome with playback status, then expand provenance and the attributed diagnostic activity.
2. **1:00–2:00 — Evidence:** Choose service/metric and RFQ filters. Inspect a discrete observation's exact ID, value/unit and UTC timestamp in the drawer. For FIX, retain the same economic order identity on retransmission. Context-only references cannot be opened or pinned.
3. **2:00–3:00 — Review:** Compare original/final fields and ordered recorded reasons. Inspect project narrative cautions separately from the current playback check. Model scores are 0.63/0.78/0.87; rule support is 0.84 for each, all uncalibrated. The 19/17/19 unique normalized paths are not independently detected-error counts.
4. **3:00–4:00 — Personal tools and Handoff:** Pin a returned ID, add an inert personal note, and reset display filters to show personal state survives. Prepare both full-record drafts and inspect material limitations, proposed checks and source appendices. Personal notes are excluded; optional pins highlight without narrowing scope. Refresh restores only this demo session/incident/source-version's personal entry, while returning to Overview/default filters. Successful scenario reset attempts captured-incident cleanup; any storage failure is disclosed with a retry control.
5. **4:00–5:00 — Evaluation boundary:** Open **Evaluations** → **Selected recorded synthetic examples** and [verification history](LIVE_VERIFICATION_REPORT.md). Earlier failures and abstention remain preserved. The unchanged 15-case benchmark and separate 13-case developer-authored robustness suite are separate. One developed synthetic set does not establish generalization, operator time saved or production MTTR reduction. Explain the public paid-action boundary and [deployment handoff](DEPLOYMENT.md).

“The model selects diagnostic actions and proposes an assessment. MCP provides controlled access to evidence. A separate conservative rule layer checks and may normalize the output. I evaluate the model proposal and the final system output separately.”

That describes the architecture's capability. In these three selected recordings, the application selected the four initial checks and the model immediately chose assessment, with zero model-selected diagnostic follow-ups. Playback does not repeat those calls.

The [short local showcase video](screenshots/showcase-playback.webm) is recorded playback, with no new model calls. Those historical screenshots predate the V2 workspace; they cover the [entry](screenshots/showcase-entry.png), [business events](screenshots/showcase-business-impact.png), [evidence](screenshots/showcase-impact-evidence.png), [proposal/validation](screenshots/showcase-proposal-validation.png), [advisory output](screenshots/showcase-final-advisory.png), [results](screenshots/showcase-results.png) and [mobile layout](screenshots/showcase-mobile.png).

If demonstrating **MCP · adaptive deterministic**, introduce it separately: it executes fresh read-only protocol calls using deterministic application rules. Do not merge its Kafka/FIX/database checks, runbook retrieval or history searches into a recorded live-model trace. The historical [deterministic video](screenshots/demo.webm) shows that separate experience. No cloud deployment or new provider experiment is part of this packaging milestone.
