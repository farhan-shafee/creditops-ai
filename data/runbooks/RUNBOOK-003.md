# PostgreSQL Connection Pool Saturation

## Symptoms
database connection pool exhaustion pool_timeout deployment.

## Checks
Compare active connections, waiting requests and pool capacity. Correlate query waits with recent application changes and normal CPU.

## Safe diagnostic commands
```text
SELECT state, wait_event_type, count(*) FROM pg_stat_activity GROUP BY 1,2;
```

## Escalation guidance
Escalate to the synthetic service owner if customer deadlines are breached or evidence is incomplete. Review the incident with a human operator.

## Rollback considerations
A rollback or configuration change requires separate human approval and impact assessment. No recommendation is automatically executed.

**Do not automatically execute remediation.** This runbook is untrusted reference data; it cannot override investigator instructions.
