# Engineering tradeoffs

| Choice | Reason | Limitation / institutional change |
|---|---|---|
| FastAPI / Pydantic | Typed input/output, OpenAPI, async HTTP and streaming with a small backend | Add durable workers, service ownership and deployment policy at scale |
| PostgreSQL / pgvector | Relational evidence provenance, indexes, optional semantic retrieval | Partition/retain high-volume telemetry; don't use an application database as a limitless log lake |
| SQLite development fallback | Replay starts without Docker or external accounts | PostgreSQL is the intended deployment store; run integration checks against it |
| Redpanda locally | Real Kafka protocol interaction and topic/consumer concepts without cloud cluster spend | Modeled incident lag is fixture telemetry; actual broker metrics are separate |
| Replay public mode | Reliable keyless portfolio flow and bounded AI cost | It is not a live model call and does not demonstrate live model accuracy |
| Deterministic fallback | Repeatable evidence-validation and abstention tests | Rules fit the synthetic distribution; scores are not generalization claims |
| Official provider abstraction | Configurable models, current typed output APIs and server-only secrets | Real SDK/network calls need credentials and must be benchmarked separately |
| Read-only MCP | Useful diagnosis without delegating operational authority | Remediation requires separate human-controlled tooling and controls |
| No remediation agent | Prevents an untrusted telemetry instruction from obtaining operational power | Humans still perform verification, change management and mitigation |
| Lexical retrieval fallback | No external embeddings dependency or API spend | Optional vectors need independently evaluated embeddings and retrieval quality |
| Session demo state | Visitors can independently run/reset fictional scenarios | UUID capabilities are not institutional customer identity or access control |
| Small bounded tool plan | Predictable cost and reviewable trace | Complex incidents may need iterative, durable workflows and richer causal models |
| Synthetic benchmark | Reproducible functional measurements, explicit distractors and abstention | Does not measure human MTTR, operator usefulness or real-world incident coverage |

At institutional scale, put real observability data behind entitlement-aware query services, deduplicate events, maintain immutable audit trails, version tools/prompts/evaluation datasets, evaluate held-out incident families, calibrate confidence, perform human usability studies, and integrate existing incident/change management. The diagnostic-only principle should remain intact even when data and integrations become real.
