# Two-minute interview demo

Start the local API and console. No provider key is needed. Reset the prior scenario and select **MCP · adaptive deterministic** for newly executed protocol calls. Replay is a separate recorded mode.

| Time | Click | Say |
|---|---|---|
| 0:00 | Overview, Run Incident Demo, Kafka pricing lag | “This independent portfolio uses only fictional securities, clients and operations. The synthetic clock runs at twelve times wall time.” |
| 0:20 | Open incident, Business impact / affected requests | “Two RFQs reference Demo Aster Manufacturing's fictional bond. These exact USD par amounts are requested face value, not lost revenue.” |
| 0:35 | Expand the first request timeline | “The quote becomes stale, then expires at its own deadline. RFQ expiry is a later observed event. The second request has no available quote. These counts come from the events.” |
| 0:50 | Run MCP investigation | “This makes fresh read-only calls through the official MCP client and server. Tool selection is deterministic here. It can inspect Kafka after seeing consumer-lag evidence, or inspect the DB after seeing pool pressure.” |
| 1:10 | Show provenance and tool evidence | “The trace identifies stdio, provider, schema verification and frozen cutoff. These returned objects support backlog; they do not establish why consumption slowed. There is no mutation tool.” |
| 1:30 | Show assessment and unknowns | “The score is uncalibrated support, every draft needs review, and the initiating cause is unconfirmed. A valid evidence ID alone cannot establish a claim.” |
| 1:45 | Evaluations | “The original 15 labels and old results are preserved. Corrected attribution and mandatory review create explicit legacy mismatches. A separate 13-case developer-authored regression suite checks uncertainty; neither proves real-model quality or MTTR reduction.” |

For follow-ups, show FIX's two UNKNOWN orders: quote acceptance and message retransmission do not prove execution or justify a new order. Reconcile existing IDs before acting. Show DB pool saturation plus waiters: exhaustion holds without a deployment; a relevant earlier change is only a candidate trigger. The real protocol integration also tests a lost connection failing visibly.

To demonstrate replay, switch modes and explain that it uses a complete recorded snapshot with original timestamps, even if the current scenario is early. Never describe those recorded steps as new calls. Live provider execution remains NOT RUN; no paid calls or cloud deployment were authorized in this pass.
