import { Download, FlaskConical, Info } from 'lucide-react';
import type { Evaluation } from '@/lib/types';
import { Badge, Empty, Panel, percent } from '@/components/primitives';

export function EvaluationsView({ evaluation }: { evaluation: Evaluation | null }) {
  const algorithms = evaluation?.algorithms ?? [];
  const download = () => {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(evaluation, null, 2)], { type: 'application/json' }),
    );
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'creditops-evaluation.json';
    anchor.click();
    URL.revokeObjectURL(url);
  };
  return (
    <>
      <div className="evaluation-intro">
        <FlaskConical size={30} strokeWidth={1.4} />
        <div>
          <h2>Measure the investigator. Keep the claims bounded.</h2>
          <p>
            Reproducible labeled synthetic incidents measure failure-domain identification, evidence
            retrieval, safe abstention, and tool integrity.
          </p>
        </div>
        {algorithms.length > 0 && (
          <button className="button secondary" onClick={download}>
            <Download size={14} />
            Download artifact
          </button>
        )}
      </div>
      {evaluation?.selected_recordings?.length ? (
        <div data-testid="selected-recordings">
          <Panel
            title="Selected recorded synthetic examples"
            eyebrow="Completed development examples / preserved results"
          >
            <div className="showcase-results-intro">
              <p>
                Execution success, a supported domain, and truthful prose are separate questions.
                These selected examples are not a general-accuracy benchmark or held-out tests.
                Earlier attempts failed or abstained and remain preserved in project history.
              </p>
              <p>
                Original generation duration is neither playback duration nor measured human time
                saved. Estimated API cost, where recorded, is not confirmed billing or total hosting
                cost.
              </p>
            </div>
            <div className="recording-results">
              {evaluation.selected_recordings.map((row) => (
                <article key={row.incident_id} data-testid="selected-recording-row">
                  <div>
                    <span className="eyebrow mono">{row.incident_id}</span>
                    <h3>{row.title}</h3>
                    <Badge>Execution {row.execution_outcome}</Badge>
                  </div>
                  <dl>
                    <div>
                      <dt>Model-proposed domain</dt>
                      <dd>{row.proposed_domain}</dd>
                    </div>
                    <div>
                      <dt>Validation</dt>
                      <dd>
                        {row.validation_status} · final advisory domain: {row.final_domain}
                      </dd>
                    </div>
                    <div>
                      <dt>Action attribution</dt>
                      <dd>
                        {row.application_selected_diagnostic_count} application-selected diagnostics
                        · {row.model_selected_diagnostic_count} model-selected diagnostics
                        <br />
                        {row.model_decision_count} model decision · {row.model_assessment_count}{' '}
                        model assessment · local validation
                      </dd>
                    </div>
                    <div>
                      <dt>Original generation duration</dt>
                      <dd>{row.original_duration_seconds.toFixed(2)} seconds</dd>
                    </div>
                  </dl>
                  <details className="recording-review-notes">
                    <summary>Project review notes</summary>
                    <h4>Major narrative limitations</h4>
                    <ul>
                      {row.major_limitations.map((note) => (
                        <li key={note}>{note}</li>
                      ))}
                    </ul>
                  </details>
                </article>
              ))}
            </div>
          </Panel>
          <p className="reference-note">
            Legacy 15-case benchmark and robustness suite remain separate from these selected
            recordings.
          </p>
        </div>
      ) : null}
      {!algorithms.length ? (
        <Panel title="Generated benchmark">
          <Empty title="Benchmark not yet generated.">
            This page reads artifacts/eval/latest.json. No scores appear until the evaluation
            harness has produced a real artifact.
          </Empty>
        </Panel>
      ) : (
        <>
          <div className="evaluation-provenance">
            <strong>Legacy synthetic benchmark</strong>
            <Badge tone="teal">Generated artifact</Badge>
            <code>artifacts/eval/latest.json</code>
            <span>
              {evaluation?.generated_at
                ? new Date(evaluation.generated_at).toLocaleString('en-US', { timeZone: 'UTC' }) +
                  ' UTC'
                : 'Timestamp available in raw artifact'}
            </span>
          </div>
          <div className="grid-two">
            {algorithms.map((algorithm) => (
              <Panel
                key={algorithm.name}
                title={algorithm.name}
                eyebrow={`${algorithm.cases} labeled cases / ${algorithm.provider}`}
              >
                <div className="eval-score">
                  <strong>{percent(algorithm.top1_accuracy)}</strong>
                  <span>Failure-domain top-1 accuracy</span>
                </div>
                <div className="eval-mini-grid">
                  <div>
                    <strong>{percent(algorithm.required_evidence_recall)}</strong>
                    <span>Required-evidence recall</span>
                  </div>
                  <div>
                    <strong>{algorithm.mean_latency_ms.toFixed(1)} ms</strong>
                    <span>Mean synthetic investigation latency</span>
                  </div>
                  <div>
                    <strong>{algorithm.invalid_evidence_citations}</strong>
                    <span>Invalid evidence citations</span>
                  </div>
                  <div>
                    <strong>{algorithm.hallucinated_evidence_count}</strong>
                    <span>Invalid references (legacy metric)</span>
                  </div>
                </div>
              </Panel>
            ))}
          </div>
          <Panel title="Measured comparison" eyebrow="Same labeled dataset / distinct pipelines">
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Metric</th>
                    {algorithms.map((algorithm) => (
                      <th key={algorithm.name}>{algorithm.name}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    [
                      'Failure-domain top-1 accuracy',
                      ...algorithms.map((a) => percent(a.top1_accuracy)),
                    ],
                    [
                      'Failure-domain top-3 accuracy',
                      ...algorithms.map((a) => percent(a.top3_accuracy)),
                    ],
                    [
                      'Required-evidence recall',
                      ...algorithms.map((a) => percent(a.required_evidence_recall)),
                    ],
                    [
                      'Invalid evidence citations',
                      ...algorithms.map((a) => String(a.invalid_evidence_citations)),
                    ],
                    [
                      'Invalid references (legacy metric)',
                      ...algorithms.map((a) => String(a.hallucinated_evidence_count)),
                    ],
                    [
                      'Correct abstention rate',
                      ...algorithms.map((a) => percent(a.correct_abstention_rate)),
                    ],
                    ['Tool error rate', ...algorithms.map((a) => percent(a.tool_error_rate))],
                    [
                      'Mean investigation latency',
                      ...algorithms.map((a) => `${a.mean_latency_ms.toFixed(1)} ms`),
                    ],
                    [
                      'Model tokens',
                      ...algorithms.map((a) =>
                        a.total_tokens == null
                          ? 'Not applicable / unavailable'
                          : String(a.total_tokens),
                      ),
                    ],
                    [
                      'Estimated model cost',
                      ...algorithms.map((a) =>
                        a.estimated_cost_usd == null
                          ? 'Pricing not configured / no model call'
                          : `$${a.estimated_cost_usd.toFixed(6)}`,
                      ),
                    ],
                  ].map(([label, ...values]) => (
                    <tr key={label}>
                      <td>{label}</td>
                      {values.map((value, index) => (
                        <td key={index} className="mono">
                          {value}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          <Panel title="Case-level artifact" eyebrow="Inspect the reproducible result">
            <details className="raw-artifact">
              <summary>
                View all measured case results ({evaluation?.cases?.length ?? algorithms[0]?.cases})
              </summary>
              <pre>{JSON.stringify(evaluation?.cases ?? evaluation, null, 2)}</pre>
            </details>
          </Panel>
        </>
      )}
      <div className="safety-note">
        <Info size={18} />
        <div>
          <strong>What this benchmark does and does not establish</strong>
          <p>
            Deterministic provider results evaluate this pipeline on authored synthetic cases. They
            do not establish live model accuracy, customer usage, or production MTTR reduction.
            Latency is synthetic benchmark investigation latency; no human-operator study has been
            performed. AI-Assisted Investigator comparisons appear only after an actual
            live-provider evaluation. The legacy invalid-reference metric counts nonexistent
            evidence IDs only; it does not measure whether a cited record supports a claim.
          </p>
        </div>
      </div>
      {evaluation?.methodology && (
        <Panel title="Methodology" eyebrow="Saved with the generated artifact">
          <p className="methodology">
            {typeof evaluation.methodology === 'string'
              ? evaluation.methodology
              : JSON.stringify(evaluation.methodology, null, 2)}
          </p>
        </Panel>
      )}
    </>
  );
}
