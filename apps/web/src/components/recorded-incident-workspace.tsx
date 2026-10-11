import { useEffect, useRef, useState } from 'react';
import type { RecordedRecording, WorkspaceFilters } from '@/lib/recorded-evidence';
import {
  defaultWorkspaceFilters,
  filterRecordedEvidence,
  revealRecordedSource,
} from '@/lib/recorded-evidence';
import {
  AssessmentResult,
  AssessmentComparison,
  RecordedInvestigationActivity,
  RecordedInvestigationProvenance,
} from './investigator';
import { RecordedBusinessImpact } from './business-impact';
import { RecordedEvidenceTimeline, timelineSourceIds } from './recorded-evidence-timeline';
import { Badge, Empty, Panel } from './primitives';

export type RecordedSourceControls = {
  investigationId: string;
  incidentId: string;
  sourceId: string;
  hiddenByFilters: boolean;
  pinned: boolean;
  onReveal: () => void;
  onTogglePin: () => void;
};
type Props = {
  recording: RecordedRecording;
  sessionId: string | null;
  onEvidence: (id: string) => void;
  onSourceControls: (controls: RecordedSourceControls | null) => void;
};
const sections = ['Overview', 'Evidence', 'Review', 'Handoff'] as const;
function initialFilters(recording: RecordedRecording): WorkspaceFilters {
  return defaultWorkspaceFilters(recording);
}
export function RecordedIncidentWorkspace(props: Props) {
  const { recording } = props;
  const identity = recording.identity;
  return (
    <WorkspaceBody
      key={JSON.stringify([recording.investigation.id, identity, recording.investigation.evidence])}
      {...props}
    />
  );
}
function WorkspaceBody({ recording, sessionId, onEvidence, onSourceControls }: Props) {
  const [section, setSection] = useState(0),
    [focus, setFocus] = useState(0);
  const [filters, setFilters] = useState(() => initialFilters(recording));
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const tabs = useRef<Array<HTMLButtonElement | null>>([]);
  const current = useRef<RecordedRecording | null>(recording);
  useEffect(() => {
    current.current = recording;
    return () => {
      current.current = null;
    };
  }, [recording]);
  const view = filterRecordedEvidence(recording, filters);
  const visible = timelineSourceIds(view);
  const source = selectedSourceId ? recording.sources.get(selectedSourceId) : undefined;
  const allObservations = timelineSourceIds(
    filterRecordedEvidence(recording, {
      service: null,
      metricGroupKey: null,
      request: null,
      window: null,
    }),
  );
  const hidden = Boolean(source && allObservations.has(source.id) && !visible.has(source.id));
  useEffect(() => {
    if (!selectedSourceId || !recording.sources.has(selectedSourceId)) {
      onSourceControls(null);
      return;
    }
    onSourceControls({
      investigationId: recording.investigation.id,
      incidentId: recording.incident.id,
      sourceId: selectedSourceId,
      hiddenByFilters: hidden,
      pinned: false,
      onReveal: () => {
        if (current.current === recording) {
          setFilters((value) => revealRecordedSource(recording, value, selectedSourceId));
        }
      },
      onTogglePin: () => {},
    });
    return () => onSourceControls(null);
  }, [recording, selectedSourceId, hidden, onSourceControls]);
  const select = (id: string) => {
    if (recording.sources.has(id)) setSelectedSourceId(id);
    onEvidence(id);
  };
  const investigation = recording.investigation;
  const metadata = investigation.provenance?.showcase;
  const coverage = recording.coverage;
  return (
    <section
      className="recorded-workspace"
      data-testid="recorded-workspace"
      aria-label="Recorded incident workspace"
      data-session-ready={Boolean(sessionId)}
    >
      <header className="recorded-workspace-header">
        <Badge tone="amber">Synthetic · Recorded · Human review required</Badge>
        <p className="mono">{recording.incident.id}</p>
        <h2>{metadata?.title ?? recording.incident.summary}</h2>
        <p>{recording.incident.summary}</p>
        <dl className="recorded-facts">
          <div>
            <dt>Original outcome</dt>
            <dd>{metadata?.recorded_execution_outcome ?? 'Not recorded'}</dd>
          </div>
          <div>
            <dt>Playback status</dt>
            <dd>{investigation.status}</dd>
          </div>
          <div>
            <dt>Returned-sample coverage</dt>
            <dd>
              {coverage
                ? new Date(coverage.startMs).toISOString() +
                  ' — ' +
                  new Date(coverage.endMs).toISOString() +
                  ' UTC'
                : 'No plottable returned samples'}
            </dd>
          </div>
          <div>
            <dt>Evidence cutoff</dt>
            <dd>{investigation.provenance?.snapshot_cutoff ?? 'Not recorded'} UTC</dd>
          </div>
        </dl>
        <p>
          Discrete observations do not establish continuous health, ordering between tied rows, or
          causality. The initiating cause remains unconfirmed unless supported by recorded evidence.
        </p>
      </header>
      <div className="recorded-tabs" role="tablist" aria-label="Recorded workspace sections">
        {sections.map((name, index) => (
          <button
            key={name}
            ref={(element) => {
              tabs.current[index] = element;
            }}
            id={'recorded-tab-' + index}
            role="tab"
            aria-selected={section === index}
            aria-controls={'recorded-panel-' + index}
            tabIndex={focus === index ? 0 : -1}
            onFocus={() => setFocus(index)}
            onClick={() => {
              setFocus(index);
              setSection(index);
            }}
            onKeyDown={(event) => {
              let target: number | null = null;
              if (event.key === 'ArrowRight') target = (index + 1) % sections.length;
              if (event.key === 'ArrowLeft')
                target = (index + sections.length - 1) % sections.length;
              if (event.key === 'Home') target = 0;
              if (event.key === 'End') target = sections.length - 1;
              if (target !== null) {
                event.preventDefault();
                setFocus(target);
                tabs.current[target]?.focus();
              }
            }}
          >
            {name}
          </button>
        ))}
      </div>
      <div
        id="recorded-panel-0"
        role="tabpanel"
        aria-labelledby="recorded-tab-0"
        hidden={section !== 0}
        tabIndex={0}
      >
        {investigation.assessment ? (
          <AssessmentResult
            assessment={investigation.assessment}
            investigation={investigation}
            onEvidence={select}
          />
        ) : (
          <Empty title="No assessment produced">
            No advisory assessment was returned in this recording.
          </Empty>
        )}
        <RecordedBusinessImpact investigation={investigation} onEvidence={select} />
        {(investigation.provider_proposal || investigation.validation_outcome) && (
          <AssessmentComparison investigation={investigation} />
        )}
        <details className="recorded-technical">
          <summary>Technical provenance and diagnostic activity</summary>
          <RecordedInvestigationProvenance investigation={investigation} />
          <RecordedInvestigationActivity investigation={investigation} onEvidence={select} />
        </details>
      </div>
      <div
        id="recorded-panel-1"
        role="tabpanel"
        aria-labelledby="recorded-tab-1"
        hidden={section !== 1}
        tabIndex={0}
      >
        {source && (
          <div className="recorded-selection" data-testid="selected-source-state">
            <strong>{source.id}</strong>
            <span>{hidden ? 'Hidden by filters' : 'Selected source retained'}</span>
            <button className="button secondary" onClick={() => select(source.id)}>
              Open selected source
            </button>
            {hidden && (
              <button
                className="button secondary"
                onClick={() =>
                  setFilters((value) => revealRecordedSource(recording, value, source.id))
                }
              >
                Reveal source
              </button>
            )}
          </div>
        )}
        <RecordedEvidenceTimeline
          recording={recording}
          filters={filters}
          selectedSourceId={selectedSourceId}
          onFilters={setFilters}
          onSelect={select}
        />
      </div>
      <div
        id="recorded-panel-2"
        role="tabpanel"
        aria-labelledby="recorded-tab-2"
        hidden={section !== 2}
        tabIndex={0}
      >
        <Panel title="Recorded review" eyebrow="Read-only review">
          <p className="padded">
            Field-by-field review is pending. The original proposal and recorded review notes remain
            available in Overview.
          </p>
        </Panel>
      </div>
      <div
        id="recorded-panel-3"
        role="tabpanel"
        aria-labelledby="recorded-tab-3"
        hidden={section !== 3}
        tabIndex={0}
      >
        <Panel title="Draft handoff" eyebrow="Human review required">
          <p className="padded">
            Personal notes, source pins and draft handoffs are pending. No handoff has been
            generated.
          </p>
        </Panel>
      </div>
    </section>
  );
}
