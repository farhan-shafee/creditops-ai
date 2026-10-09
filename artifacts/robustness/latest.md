# Synthetic robustness/regression suite

Generated 2026-10-09T18:08:05.165692+00:00; 13/13 passed; 0 failed; 4 abstentions.

Direct controlled-evidence assessment; no model or MCP call. Transport and scripted adaptation have separate integration tests.

| Case | Condition | Result | Invalid references | Failed support checks |
|---|---|---|---:|---|
| pool_no_deployment | database connection pool exhaustion | PASS | 0 | none |
| pool_unrelated_deployment | database connection pool exhaustion | PASS | 0 | none |
| pool_deployment_after_onset | database connection pool exhaustion | PASS | 0 | none |
| pool_preceding_deployment | database connection pool exhaustion | PASS | 0 | none |
| kafka_no_business_events | pricing-service / Kafka consumer backlog | PASS | 0 | none |
| stale_market_healthy_kafka | market-data-service / stale market data | PASS | 0 | none |
| fix_ack_uncertainty | FIX connectivity/session instability | PASS | 0 | none |
| contradictory_domains | insufficient evidence | PASS | 0 | none |
| missing_telemetry | insufficient evidence | PASS | 0 | none |
| tool_failure | insufficient evidence | PASS | 0 | none |
| prompt_injection | database connection pool exhaustion | PASS | 0 | none |
| changed_identifiers_paraphrases | database connection pool exhaustion | PASS | 0 | none |
| healthy_pool_contradiction | insufficient evidence | PASS | 0 | none |

Live provider: NOT RUN. Live-model quality: UNVERIFIED.

- Developer-authored controlled variants; not independently held out.
- Reference validity is distinct from substantive support; zero invalid IDs is not zero hallucinations.
- Substantive checks cover only the declared condition/trigger/acknowledgement cases, not arbitrary factuality.
- The tool-failure fixture represents absent evidence after failure; actual protocol/tool failures are tested separately.
- No operator time, financial loss, model cost or MTTR claim.
