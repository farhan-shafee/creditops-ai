# CreditOps AI synthetic evaluation

Generated: 2026-10-09T16:17:43.187174+00:00. Dataset: 15 cases; seed 42.

15 labeled synthetic cases: 12 diagnosable incidents and 3 insufficient-evidence cases. Labels are available only to the scorer. Complete case telemetry is activated in an isolated evaluation session. Latency measures the synthetic diagnostic pipeline, not human MTTR. The baseline uses first matching log signatures; the investigator requires corroborating independent signals. Deterministic rules are designed for these fixtures; this is an in-distribution functional benchmark, not a generalization study.

| Algorithm | Top-1 | Top-3 | Required evidence recall | Invalid citations | Abstention | Mean pipeline ms |
|---|---:|---:|---:|---:|---:|---:|
| Deterministic Baseline | 100.0% | 100.0% | 50.0% | 0 | 100.0% | 10.62 |
| Orchestrated Investigator (deterministic provider) | 100.0% | 100.0% | 100.0% | 0 | 100.0% | 58.48 |

Live AI: not_run

## Limitations
- No real operator study or production MTTR measurement.
- Small synthetic in-distribution dataset; no held-out institutional traffic.
- Deterministic confidence scores are not calibrated probabilities.
- No live model result is claimed unless provider is openai or anthropic.
- A failure stops artifact generation; existing artifact remains from its recorded timestamp.
