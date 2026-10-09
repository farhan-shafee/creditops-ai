# CreditOps AI synthetic evaluation

Generated: 2026-10-09T18:08:04.473327+00:00. Dataset: 15 cases; seed 42.

15 labeled synthetic cases: 12 diagnosable incidents and 3 insufficient-evidence cases. Labels are available only to the scorer. Complete case telemetry is activated in an isolated evaluation session. Latency measures the synthetic diagnostic pipeline, not human MTTR. The baseline uses first matching log signatures; the investigator requires corroborating independent signals. Deterministic rules are designed for these fixtures; this is an in-distribution functional benchmark, not a generalization study.

| Algorithm | Top-1 correct/cases | Mismatches | Top-3 | Required evidence recall | Invalid references | Total abstentions | Correct expected abstentions | Mean pipeline ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Deterministic Baseline | 12/15 | 3 | 80.0% | 50.0% | 0 | 3 | 3/3 | 21.25 |
| Orchestrated Investigator (deterministic provider) | 11/15 | 4 | 73.3% | 80.0% | 0 | 4 | 3/3 | 113.34 |

Live AI: not_run

## Limitations
- No real operator study or production MTTR measurement.
- Small synthetic in-distribution dataset; no held-out institutional traffic.
- Deterministic confidence scores are not calibrated probabilities.
- No live model result is claimed unless provider is openai or anthropic.
- A failure stops artifact generation; existing artifact remains from its recorded timestamp.
- Original cases and labels remain unchanged. Legacy database labels include unproven change attribution; corrected condition-only output is scored as a mismatch instead of relabeling the cases.
- Every current draft requires human review; legacy cases expecting no escalation can therefore fail the original escalation metric.
- INC-EVAL-011 retains its original 1840ms risk sample and later 1450ms sample. Current-evidence rules abstain at the complete cutoff because the later value is below the 1500ms threshold; this original-fixture mismatch is preserved.
- Citation existence is not substantive claim support. A separate developer-authored robustness suite tests declared causal/uncertainty checks.
