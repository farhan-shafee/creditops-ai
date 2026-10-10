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
import type {
  Assessment,
  EvidenceClaim,
  Incident,
  Investigation,
  InvestigationMode,
  Step,
} from '@/lib/types';
import { Citation, Panel, Spinner, Status, time } from './primitives';
import { EvidenceText } from './evidence-text';

export function Investigator({
  incident,
  investigation,
  investigating,
  disabled = false,
  mode = 'REPLAY',
  onMode,
  onInvestigate,
  onEvidence,
}: {
  incident: Incident;
  investigation: Investigation | null;
  investigating: boolean;
  disabled?: boolean;
  mode?: InvestigationMode;
  onMode?: (mode: InvestigationMode) => void;
  onInvestigate: () => void;
  onEvidence: (id: string) => void;
}) {
  const provider = investigation?.provider;
  const recorded = investigation ? investigation.mode === 'REPLAY' : mode === 'REPLAY';
  const metadata = investigation?.provenance;
  const provenance = !recorded
    ? investigation?.mode === 'MCP_DEMO'
      ? 'MCP · adaptive deterministic'
      : investigation?.mode === 'LIVE_AI'
        ? `AI-assisted · ${provider ?? 'provider not recorded'}`
        : 'Adaptive MCP selected · deterministic provider'
    : !provider
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
        <div className="investigator-actions">
          {onMode && (
            <div className="investigation-path">
              <label htmlFor="investigation-path">Investigation path</label>
              <select
                id="investigation-path"
                value={mode}
                disabled={investigating || disabled}
                onChange={(event) => onMode(event.target.value as InvestigationMode)}
              >
                <option value="REPLAY">Recorded replay · complete snapshot</option>
                <option value="MCP_DEMO">Adaptive MCP · deterministic provider</option>
              </select>
            </div>
          )}
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
            ) : mode === 'MCP_DEMO' ? (
              'Run adaptive MCP investigation'
            ) : (
              'Investigate with AI'
            )}
            {!investigating && <ArrowRight size={16} />}
          </button>
        </div>
      </div>
      <div className="investigator-mode">
        <span className="mode-pill">{provenance}</span>
        <span>
          {recorded
            ? 'Persisted pipeline artifact · no live model call'
            : investigation?.mode === 'LIVE_AI'
              ? metadata?.model_called === true
                ? 'Model call recorded · read-only diagnostic execution'
                : 'Model-call provenance not recorded'
              : 'Fresh diagnostics · deterministic provider · no live model call'}
        </span>
        <span className="mode-safety">
          <ShieldCheck size={14} /> Diagnostic tools only
        </span>
      </div>
      {investigation && (
        <div className="investigation-provenance" data-testid="investigation-provenance">
          <span>
            <strong>{recorded ? 'Recorded tool results' : 'Fresh diagnostic execution'}</strong> ·{' '}
            {metadata?.snapshot_kind === 'complete_scenario'
              ? 'Complete scenario snapshot'
              : metadata?.snapshot_kind === 'frozen_current'
                ? 'Frozen current snapshot'
                : 'Snapshot kind not recorded'}
          </span>
          <span>
            {metadata?.snapshot_cutoff ? (
              <>
                Evidence cutoff{' '}
                <time dateTime={metadata.snapshot_cutoff}>{metadata.snapshot_cutoff}</time>
              </>
            ) : (
              'Cutoff not recorded'
            )}
          </span>
          <span>
            {recorded
              ? `Original transport: ${transportLabel(metadata?.original_transport)}`
              : `Transport: ${transportLabel(metadata?.transport)}`}
          </span>
          <span>
            {metadata?.tool_schema_verified === true
              ? 'Tool schemas verified'
              : metadata?.tool_schema_verified === false
                ? 'Tool schemas not verified'
                : 'Tool schema verification not recorded'}
          </span>
          <span>Workflow: {metadata?.workflow ?? 'not recorded'}</span>
          {recorded && <span>Original workflow: {metadata?.original_workflow ?? 'not recorded'}</span>}
          <span>{assessmentOutcome(investigation)}</span>
          {investigation.assessment && <span>{assessmentOrigin(metadata?.assessment_source)}</span>}
          {recorded && (
            <p>
              Recorded steps retain their original timestamps and durations. Playback does not
              execute those tools again.
            </p>
          )}
        </div>
      )}
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
            Start an investigation for <code>{incident.id}</code>.{' '}
            {mode === 'MCP_DEMO'
              ? 'The offline adaptive path requests real MCP stdio diagnostics at the current evidence cutoff. The deterministic provider can select follow-up checks from returned evidence.'
              : 'Public replay loads a recorded complete-scenario artifact, including evidence beyond the current simulation window.'}{' '}
            No paid model call is made. Protected LIVE_AI remains separate.
          </p>
        </div>
      ) : (
        <>
          <div className="trace-heading">
            <h3>Diagnostic activity</h3>
            <span className="mono">
              {investigation.steps.length} actions · Execution {investigation.status}
            </span>
          </div>
          <ol className="investigation-trace" aria-live="polite">
            {investigation.steps.map((step, index) => (
              <li key={step.id} data-testid="investigation-step">
                <div className="trace-icon">
                  {['complete', 'completed', 'success'].includes(step.status) ? (
                    <Check size={13} />
                  ) : (
                    <Circle size={10} />
                  )}
                </div>
                <div className="trace-content">
                  <div>
                    <strong>{step.action}</strong>
                    <time dateTime={step.timestamp}>{time(step.timestamp)} UTC</time>
                  </div>
                  <p>
                    <code>{step.tool}</code>
                    <span>{step.duration_ms} ms</span>
                    <Status value={step.status} />
                  </p>
                  <p className="trace-provenance">
                    <span>{selectionLabel(step.selected_by)}</span>
                    <span>
                      {recorded || step.recorded
                        ? step.transport === 'local_validation'
                          ? 'Recorded validation action'
                          : 'Recorded tool result'
                        : step.transport === 'mcp_stdio' || step.transport === 'direct'
                          ? 'Executed tool call'
                          : 'Diagnostic workflow action'}
                    </span>
                    <span>{transportLabel(step.transport)}</span>
                    {step.provider &&
                      step.selected_by !== 'application_runbook' &&
                      step.selected_by !== 'validator' && <span>Provider {step.provider}</span>}
                    {Boolean(step.provider_turn) && <span>Provider turn {step.provider_turn}</span>}
                  </p>
                  {step.safe_arguments && Object.keys(step.safe_arguments).length > 0 && (
                    <p className="trace-filters">
                      Safe filters <code>{JSON.stringify(step.safe_arguments)}</code>
                    </p>
                  )}
                  {step.error && <p className="trace-error">Tool error: {step.error}</p>}
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
          {(investigation.provider_proposal || investigation.validation_outcome) && (
            <AssessmentComparison investigation={investigation} />
          )}
          {investigation.assessment && (
            <AssessmentResult assessment={investigation.assessment} onEvidence={onEvidence} />
          )}
        </>
      )}
    </section>
  );
}

function selectionLabel(value: Step['selected_by']): string {
  switch (value) {
    case 'application_runbook':
      return 'Application-runbook initial diagnostic';
    case 'model':
      return 'Model-selected follow-up diagnostic';
    case 'deterministic':
      return 'Deterministic-provider-selected diagnostic';
    case 'scripted_provider':
      return 'Scripted-provider-selected diagnostic';
    case 'validator':
      return 'Validator-authored assessment check';
    default:
      return 'Selection source not recorded';
  }
}

function assessmentOutcome(investigation: Investigation): string {
  if (!investigation.assessment) {
    return ['complete', 'completed', 'failed', 'cancelled'].includes(investigation.status)
      ? 'No assessment produced'
      : 'Assessment pending';
  }
  return investigation.assessment.probable_failure_domain.trim().toLowerCase() ===
    'insufficient evidence'
    ? 'Abstained · no failure domain identified'
    : 'Advisory failure-domain assessment · human review required';
}

function assessmentOrigin(
  source: NonNullable<Investigation['provenance']>['assessment_source'],
): string {
  if (!source) return 'Assessment origin not recorded';
  switch (source.kind) {
    case 'live_provider':
      return `Model-authored proposal · ${source.provider}`;
    case 'deterministic':
      return `Deterministic assessment · ${source.provider}`;
    case 'scripted_provider':
      return `Scripted-provider assessment · ${source.provider}`;
    case 'orchestrator_fallback':
      return `Deterministic fallback assessment · ${source.provider}`;
    default:
      return 'Assessment origin not recorded';
  }
}

function AssessmentComparison({ investigation }: { investigation: Investigation }) {
  const outcome = investigation.validation_outcome;
  return (
    <details className="raw-artifact" data-testid="assessment-comparison">
      <summary>Inspect original proposal and validation outcome</summary>
      {investigation.provider_proposal ? (
        <>
          <h4>{assessmentOrigin(investigation.provenance?.assessment_source)}</h4>
          <p>Sanitized structured proposal · untrusted advisory output before validation.</p>
          <pre>{JSON.stringify(investigation.provider_proposal, null, 2)}</pre>
        </>
      ) : (
        <p>No provider assessment proposal recorded.</p>
      )}
      {outcome && (
        <>
          <h4>Validation outcome: {outcome.status}</h4>
          <p>
            Validator-authored changes and rejections. Normalization does not independently confirm
            the original claims.
          </p>
          <pre>{JSON.stringify(outcome, null, 2)}</pre>
        </>
      )}
    </details>
  );
}

function transportLabel(value?: string): string {
  return value === 'mcp_stdio'
    ? 'MCP stdio'
    : value === 'mcp_http'
      ? 'MCP HTTP'
      : value === 'direct'
        ? 'direct'
        : value === 'recorded_replay'
          ? 'recorded replay'
          : value === 'local_validation'
            ? 'local validation'
            : value && value !== 'unknown'
              ? value
              : 'not recorded';
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
  const structured = a.supported_failure_condition !== undefined;
  const condition = structured
    ? (a.supported_failure_condition ?? 'Insufficient evidence for a supported failure condition')
    : a.probable_failure_domain;
  const claims = (values: EvidenceClaim[]) => (
    <ul className="assessment-claims">
      {values.map((value, index) => (
        <li key={index}>
          <p>{text(value.statement)}</p>
          <div className="citations">
            {value.evidence_ids.map((id) => (
              <Citation key={id} id={id} onEvidence={onEvidence} />
            ))}
          </div>
        </li>
      ))}
    </ul>
  );
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
          <Check size={14} /> Final advisory assessment
        </span>
        <div className="assessment-title">
          <div>
            <span className="muted">
              {structured ? 'Supported failure condition' : 'Recorded failure-domain claim'}
            </span>
            <h3 data-testid="failure-domain">{condition}</h3>
          </div>
          <div className="confidence">
            <strong>{(a.confidence * 100).toFixed(0)} / 100</strong>
            <span>uncalibrated support score</span>
          </div>
        </div>
        <p>{text(a.incident_summary)}</p>
        <p className="score-note">
          A rule or provider support score; this is not a calibrated probability of correctness.
        </p>
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
      <div className="assessment-qualification" data-testid="assessment-qualification">
        <div>
          <h4>Observed symptoms</h4>
          {a.observations?.length ? (
            claims(a.observations)
          ) : (
            <p>Structured observations were not recorded in this artifact.</p>
          )}
        </div>
        <div>
          <h4>Possible triggers</h4>
          {a.possible_triggers?.length ? (
            a.possible_triggers.map((trigger, index) => (
              <div key={index} className="candidate-trigger">
                <span className="draft-label">Candidate · causation unproven</span>
                {claims([trigger])}
                <p className="muted">{text(trigger.reason)}</p>
              </div>
            ))
          ) : (
            <p>
              Not established. Missing change evidence does not rule out a supported failure
              condition.
            </p>
          )}
        </div>
        <div>
          <h4>Confirmed cause</h4>
          {a.confirmed_cause ? (
            claims([a.confirmed_cause])
          ) : (
            <p>
              Not established. A failure condition, recent change or historical match does not
              establish a causal mechanism.
            </p>
          )}
        </div>
        <div>
          <h4>Unknowns and next checks</h4>
          {a.unknowns?.length ? (
            lines(a.unknowns)
          ) : (
            <p>Unknowns were not recorded. Continue human verification before acting.</p>
          )}
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
      <p className="reference-note">
        Runbooks and historical matches guide checks; they do not prove the current cause.
      </p>
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
            <h4>Supported failure condition</h4>
            <p>{text(condition)}</p>
            <h4>Confirmed cause</h4>
            {a.confirmed_cause ? (
              claims([a.confirmed_cause])
            ) : (
              <p>Not established; further causal investigation is required.</p>
            )}
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
