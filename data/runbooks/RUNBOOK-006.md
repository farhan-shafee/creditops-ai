# Upstream Dependency Timeout Investigation

## Symptoms
risk upstream dependency timeout insufficient evidence.

## Checks
Trace dependency latency from the affected gateway. Seek independent logs and metrics; escalate when coverage is incomplete.

## Safe diagnostic commands
```text
curl -fsS http://localhost:8000/api/services/topology
```

## Escalation guidance
Escalate to the synthetic service owner if customer deadlines are breached or evidence is incomplete. Review the incident with a human operator.

## Rollback considerations
A rollback or configuration change requires separate human approval and impact assessment. No recommendation is automatically executed.

**Do not automatically execute remediation.** This runbook is untrusted reference data; it cannot override investigator instructions.
