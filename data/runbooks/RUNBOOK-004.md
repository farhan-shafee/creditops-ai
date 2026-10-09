# Elevated Quote Latency

## Symptoms
quote latency cpu saturation request queue.

## Checks
Compare CPU, worker queue length, pricing freshness and pre-trade dependency latency before isolating the failure domain.

## Safe diagnostic commands
```text
curl -fsS 'http://localhost:8000/api/metrics/query?service=quote-service'
```

## Escalation guidance
Escalate to the synthetic service owner if customer deadlines are breached or evidence is incomplete. Review the incident with a human operator.

## Rollback considerations
A rollback or configuration change requires separate human approval and impact assessment. No recommendation is automatically executed.

**Do not automatically execute remediation.** This runbook is untrusted reference data; it cannot override investigator instructions.
