import { useState } from 'react';
import {
  ArrowRight,
  Check,
  ChevronDown,
  Circle,
  FileText,
  ScanLine,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import type { Assessment, Incident, Investigation } from '@/lib/types';
import { Citation, Panel, percent, Spinner, time } from './primitives';
import { EvidenceText } from './evidence-text';

export function Investigator({
  incident,
  investigation,
  investigating,
  disabled = false,
  onInvestigate,
  onEvidence,
}: {
  incident: Incident;
  investigation: Investigation | null;
  investigating: boolean;
  disabled?: boolean;
  onInvestigate: () => void;
  onEvidence: (id: string) => void;
}) {
  const provider = investigation?.provider;
  const provenance = !provider
    ? 'Replay · persisted artifact'
    : /deterministic|rules/i.test(provider)
      ? 'Replay · deterministic provider'
      : `Replay · ${provider} artifact`;
  return (
    <section className="investigator" aria-label="AI investigation">
      <div className="investigator-heading">
        <div>
          <span className="eyebrow">
            <ScanLine size={14} /> Investigation workspace
          </span>
          <h2>From signal to supported assessment.</h2>
          <p>Read-only diagnostics. Every finding returns to its source.</p>
        </div>
        <button
          className="button primary"
          onClick={onInvestigate}
          disabled={investigating || disabled}
        >
          <Sparkles size={16} />
          {investigating ? (
            <>
              <Spinner /> Investigating…
            </>
          ) : (
            'Investigate with AI'
          )}
          {!investigating && <ArrowRight size={16} />}
        </button>
      </div>
      <div className="investigator-mode">
        <span className="mode-pill">{provenance}</span>
        <span>Persisted pipeline artifact · no live model call</span>
        <span className="mode-safety">
          <ShieldCheck size={14} /> Diagnostic tools only
        </span>
      </div>
      {!investigation ? (
        <div className="investigation-ready">
          <div className="trace-preview">
            <div>
              <span>01</span> Collect incident context
            </div>
            <div>
              <span>02</span> Correlate diagnostic evidence
            </div>
            <div>
              <span>03</span> Validate citations & draft RCA
            </div>
          </div>
          <p>
            Start an investigation for <code>{incident.id}</code>. Public replay loads a persisted
            collection and validation pipeline artifact. Its provider metadata appears when loaded.
            Protected LIVE_AI is available through the API.
          </p>
        </div>
      ) : (
        <>
          <div className="trace-heading">
            <h3>Diagnostic activity</h3>
            <span className="mono">
              {investigation.steps.length} actions · {investigation.status}
            </span>
          </div>
          <ol className="investigation-trace" aria-live="polite">
            {investigation.steps.map((step, index) => (
              <li key={step.id} data-testid="investigation-step">
                <div className="trace-icon">
                  {step.status === 'completed' || step.status === 'success' ? (
                    <Check size={13} />
                  ) : (
                    <Circle size={10} />
                  )}
                </div>
                <div className="trace-content">
                  <div>
                    <strong>{step.action}</strong>
                    <time>{time(step.timestamp)} UTC</time>
                  </div>
                  <p>
                    <code>{step.tool}</code>
                    <span>{step.duration_ms} ms</span>
                  </p>
                  {step.evidence_ids.length > 0 && (
                    <div className="citations">
                      {step.evidence_ids.slice(0, 8).map((id) => (
                        <Citation key={id} id={id} onEvidence={onEvidence} />
                      ))}
                      {step.evidence_ids.length > 8 && (
                        <span className="muted">+{step.evidence_ids.length - 8} records</span>
                      )}
                    </div>
                  )}
                </div>
                <span className="trace-number">{String(index + 1).padStart(2, '0')}</span>
              </li>
            ))}
          </ol>
          {investigating && (
            <div className="loading-row">
              <Spinner /> Receiving diagnostic activity…
            </div>
          )}
          {investigation.error && <p className="error-banner">{investigation.error}</p>}
          {investigation.assessment && (
            <AssessmentResult assessment={investigation.assessment} onEvidence={onEvidence} />
          )}
        </>
      )}
    </section>
  );
}

function AssessmentResult({
  assessment: a,
  onEvidence,
}: {
  assessment: Assessment;
  onEvidence: (id: string) => void;
}) {
  const [rcaOpen, setRcaOpen] = useState(true);
  const text = (value: string) => <EvidenceText text={value} onEvidence={onEvidence} />;
  const lines = (values: string[]) => (
    <ul className="prose-list">
      {values.map((value, index) => (
        <li key={index}>{text(value)}</li>
      ))}
    </ul>
  );
  return (
    <div className="assessment" data-testid="assessment">
      <div className="assessment-main">
        <span className="eyebrow">
          <Check size={14} /> Evidence-backed assessment
        </span>
        <div className="assessment-title">
          <div>
            <span className="muted">Probable failure domain</span>
            <h3 data-testid="failure-domain">{a.probable_failure_domain}</h3>
          </div>
          <div className="confidence">
            <strong>{percent(a.confidence)}</strong>
            <span>confidence</span>
          </div>
        </div>
        <p>{text(a.incident_summary)}</p>
        <div className="confidence-bar">
          <span style={{ width: percent(a.confidence) }} />
        </div>
        <div className="review-note">
          <ShieldCheck size={16} />
          <span>
            {a.requires_human_review
              ? 'Human escalation required'
              : 'Human verification recommended'}{' '}
            · recommendations are advisory
          </span>
        </div>
        <div className="citations" data-testid="supporting-evidence">
          {a.supporting_evidence_ids.map((id) => (
            <Citation key={id} id={id} onEvidence={onEvidence} />
          ))}
        </div>
      </div>
      <div className="grid-two assessment-secondary">
        <Panel title="Next diagnostic steps" eyebrow="Operational guidance">
          {lines(a.recommended_next_steps)}
        </Panel>
        <Panel title="Alternative hypotheses" eyebrow="Considered & compared">
          <div className="alternatives">
            {a.alternative_hypotheses.map((alternative, index) => (
              <div key={index}>
                <h4>{alternative.domain}</h4>
                <p>{text(alternative.reason)}</p>
                <div className="citations">
                  {alternative.evidence_ids.map((id) => (
                    <Citation key={id} id={id} onEvidence={onEvidence} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <div className="related-records">
        <div>
          <h4>Relevant runbooks</h4>
          <div className="citations">
            {a.relevant_runbooks.map((id) => (
              <Citation key={id} id={id} onEvidence={onEvidence} />
            ))}
          </div>
        </div>
        <div>
          <h4>Similar historical incidents</h4>
          <div className="citations">
            {a.similar_incidents.map((id) => (
              <Citation key={id} id={id} onEvidence={onEvidence} />
            ))}
          </div>
        </div>
      </div>
      <div className="rca-draft">
        <button
          className="rca-heading"
          onClick={() => setRcaOpen(!rcaOpen)}
          aria-expanded={rcaOpen}
        >
          <span>
            <FileText size={18} />
            <strong>Root cause analysis</strong>
            <span className="draft-label">Draft — human review required</span>
          </span>
          <ChevronDown size={18} className={rcaOpen ? 'rotate' : ''} />
        </button>
        {rcaOpen && (
          <div className="rca-body">
            <h4>Executive summary</h4>
            <p>{text(a.rca.executive_summary)}</p>
            <h4>Synthetic impact</h4>
            <p>{text(a.rca.impact)}</p>
            <h4>Timeline</h4>
            {lines(a.rca.timeline)}
            <h4>Observed evidence</h4>
            {lines(a.rca.observed_evidence)}
            <h4>Probable root cause</h4>
            <p>{text(a.rca.probable_root_cause)}</p>
            <h4>Contributing factors</h4>
            {lines(a.rca.contributing_factors)}
            <h4>Immediate next steps</h4>
            {lines(a.rca.immediate_next_steps)}
            <h4>Follow-up work</h4>
            {lines(a.rca.follow_up_work)}
            <h4>Limitations</h4>
            {lines(a.limitations)}
          </div>
        )}
      </div>
    </div>
  );
}
