# Portfolio summary

## GitHub / LinkedIn

CreditOps AI is an independent portfolio project demonstrating incident intelligence for synthetic electronic credit trading operations. A Next.js console and FastAPI backend correlate logs, metrics, Kafka, FIX sessions, database health, service dependencies and application changes into evidence-backed advisory RCA drafts. It includes read-only MCP diagnostics, configurable OpenAI/Anthropic providers, explicit deterministic replay, and a reproducible 15-case synthetic evaluation harness. Local Docker infrastructure uses PostgreSQL/pgvector, Redpanda and provisioned observability. No real trading systems or customer data are connected.

## Resume project section

- Independently built a typed incident-intelligence monorepo with synthetic Kafka backlog, FIX instability and database saturation scenarios, session-scoped simulation, REST/SSE APIs and a responsive operations console.
- Connected an evidence-adaptive investigation to the official MCP client/server, with tested scope, disconnect/cancellation cleanup, sanitized context and human-review drafts; intentionally excluded operational mutation.
- Connected three fictional bonds to event-derived RFQ/quote/order impact, keeping quote expiry, RFQ deadlines and unknown acknowledgements separate.
- Created deterministic replay artifacts and labeled evaluations measuring failure-domain accuracy, evidence recall, abstention and synthetic pipeline latency without claiming production MTTR reduction.

The second pass preserves the original 15-case benchmark and adds a separate 13-case synthetic robustness suite. Three selected OpenAI model-assisted development recordings were subsequently captured and packaged for public playback; they contain no model-selected diagnostic follow-ups and do not establish general model quality. Keyless adaptive MCP uses deterministic rules. The [recording history](LIVE_VERIFICATION_REPORT.md) preserves failures, review limitations and original versus validated proposals. See the [verification report](SECOND_PASS_REPORT.md) for actual outcomes, including preserved legacy-label mismatches.

## Recruiter email excerpt

“I built CreditOps AI to demonstrate how I approach Production Support, SRE and AI Enablement problems: correlate independent telemetry, expose safe diagnostics, make conclusions inspectable and measure investigation quality. The project uses entirely synthetic infrastructure and is not affiliated with any trading venue or employer. Its two-minute demo shows a pricing incident, the diagnostic tool trace and the evidence-backed RCA draft.”

## Current hosting

The [public source](https://github.com/farhan-shafee/creditops-ai) and [live showcase](https://creditops.farhan-shafee.com) are available. Next.js, FastAPI, PostgreSQL and private off-volume backups run on Railway; Cloudflare supplies DNS. A production-backup restore was verified. Public diagnostics remain advisory and synthetic. [Deployment and recovery](DEPLOYMENT.md) documents the actual topology, CI-trigger distinction and retained rollback resources.
