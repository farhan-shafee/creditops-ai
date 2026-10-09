import { ArrowRight, RotateCcw, Play, Clock3 } from 'lucide-react';
import type {
  Incident,
  Investigation,
  InvestigationMode,
  MetricSeries,
  Scenario,
  Topology,
} from '@/lib/types';
import { Badge, Citation, Empty, Panel, Status, time } from '@/components/primitives';
import { TelemetryChart } from '@/components/telemetry-chart';
import { ServiceMap } from '@/components/service-map';
import { Investigator } from '@/components/investigator';
import { BusinessImpactPanel } from '@/components/business-impact';

export function ScenarioControls({
  scenarios,
  selectedScenario,
  onScenario,
  onRun,
  onReset,
  busy,
  running,
  hasIncident,
}: {
  scenarios: Scenario[];
  selectedScenario: string;
  onScenario: (value: string) => void;
  onRun: () => void;
  onReset: () => void;
  busy: boolean;
  running: boolean;
  hasIncident: boolean;
}) {
  return (
    <div className="scenario-controls">
      <div>
        <label htmlFor="scenario-select">Incident scenario</label>
        <select
          id="scenario-select"
          value={selectedScenario}
          disabled={running}
          onChange={(event) => onScenario(event.target.value)}
        >
          {scenarios.map((scenario) => (
            <option key={scenario.id} value={scenario.id}>
              {scenario.title}
            </option>
          ))}
        </select>
      </div>
      <button className="button primary" onClick={onRun} disabled={busy || !scenarios.length}>
        <Play size={14} />
        Run Incident
      </button>
      <button className="button secondary" onClick={onReset} disabled={busy || !hasIncident}>
        <RotateCcw size={14} />
        Reset Scenario
      </button>
      <span className="clock-caption">
        <Clock3 size={13} />
        Simulated clock · 12×
      </span>
    </div>
  );
}

export function IncidentView({
  incident,
  incidents,
  metrics,
  topology,
  investigation,
  investigating,
  investigationMode,
  onInvestigationMode,
  running,
  onInvestigate,
  onEvidence,
  onIncident,
  onlyInvestigator = false,
}: {
  incident: Incident | null;
  incidents: Incident[];
  metrics: MetricSeries[];
  topology: Topology | null;
  investigation: Investigation | null;
  investigating: boolean;
  investigationMode: InvestigationMode;
  onInvestigationMode: (mode: InvestigationMode) => void;
  running: boolean;
  onInvestigate: () => void;
  onEvidence: (id: string) => void;
  onIncident: (incident: Incident) => void;
  onlyInvestigator?: boolean;
}) {
  if (!incident)
    return (
      <Panel title="Incident queue" eyebrow="Synthetic operations">
        <Empty title="Your investigation starts with a signal">
          Select a scenario and run an incident. This creates isolated telemetry and incident state
          for your browser session.
        </Empty>
      </Panel>
    );
  return (
    <div data-testid="incident-detail">
      {incidents.length > 1 && (
        <div className="incident-tabs">
          {incidents.map((item) => (
            <button
              key={item.id}
              className={incident.id === item.id ? 'active' : ''}
              onClick={() => onIncident(item)}
              disabled={running}
            >
              {item.id}
              <ArrowRight size={12} />
            </button>
          ))}
        </div>
      )}
      <div className="incident-banner">
        <div>
          <span className="eyebrow mono">
            {incident.id} / {incident.scenario}
          </span>
          <h2>{incident.title}</h2>
          <p>{incident.summary}</p>
        </div>
        <div>
          <Status value={incident.severity} />
          <Status value={incident.status} />
        </div>
      </div>
      {!onlyInvestigator && (
        <>
          <div className="incident-metadata">
            <div>
              <span>Start time</span>
              <strong>{time(incident.started_at)} UTC</strong>
            </div>
            <div>
              <span>Synthetic client impact</span>
              <strong>{incident.client_impact}</strong>
            </div>
            <div>
              <span>Affected services</span>
              <strong>{incident.affected_services.join(', ')}</strong>
            </div>
            <div>
              <span>Simulated elapsed</span>
              <strong>{Math.floor(incident.simulated_elapsed_seconds)} seconds</strong>
            </div>
          </div>
          <BusinessImpactPanel incidentId={incident.id} onEvidence={onEvidence} />
          <Panel
            title="Incident telemetry"
            eyebrow="Observe the signal"
            action={<Badge tone="amber">Simulated clock / 12×</Badge>}
          >
            <div className="grid-two">
              {metrics.length ? (
                metrics
                  .slice(0, 4)
                  .map((series, index) => (
                    <TelemetryChart
                      key={`${series.service}-${series.metric}`}
                      series={series}
                      color={index % 2 ? 'amber' : 'teal'}
                      onEvidence={onEvidence}
                    />
                  ))
              ) : (
                <p className="padded muted">Waiting for the first persisted telemetry samples…</p>
              )}
            </div>
          </Panel>
          <div className="grid-two">
            <Panel title="Incident timeline" eyebrow="Alerts & observations">
              <ol className="incident-timeline">
                {incident.timeline.map((event, index) => (
                  <li key={`${event.timestamp}-${index}`}>
                    <time>
                      {time(event.timestamp)}
                      <span>UTC</span>
                    </time>
                    <div>
                      <strong>{event.label}</strong>
                      <div className="citations">
                        {event.evidence_ids.map((id) => (
                          <Citation key={id} id={id} onEvidence={onEvidence} />
                        ))}
                      </div>
                    </div>
                  </li>
                ))}
                {!incident.timeline.length && (
                  <li>
                    <p>Telemetry is accumulating as the simulated clock advances.</p>
                  </li>
                )}
              </ol>
            </Panel>
            <Panel title="Dependency impact" eyebrow="Follow the trading path">
              <ServiceMap topology={topology} incident={incident} compact />
            </Panel>
          </div>
        </>
      )}
      <Investigator
        incident={incident}
        investigation={investigation}
        investigating={investigating}
        mode={investigationMode}
        onMode={onInvestigationMode}
        disabled={running}
        onInvestigate={onInvestigate}
        onEvidence={onEvidence}
      />
    </div>
  );
}
