import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Box,
  Cable,
  Layers3,
  Play,
  Radio,
  ShieldCheck,
} from 'lucide-react';
import Link from 'next/link';
import type { Evaluation, Incident, MetricSeries, Overview, Scenario, Topology } from '@/lib/types';
import { Badge, Empty, Panel, Status, time } from '@/components/primitives';
import { TelemetryChart } from '@/components/telemetry-chart';
import { ServiceMap } from '@/components/service-map';

export function OverviewView({
  overview,
  scenarios,
  selectedScenario,
  onScenario,
  onRun,
  busy,
  metrics,
  topology,
  onEvidence,
  onIncident,
  evaluation,
}: {
  overview: Overview | null;
  scenarios: Scenario[];
  selectedScenario: string;
  onScenario: (id: string) => void;
  onRun: () => void;
  busy: boolean;
  metrics: MetricSeries[];
  topology: Topology | null;
  onEvidence: (id: string) => void;
  onIncident: (incident: Incident) => void;
  evaluation: Evaluation | null;
}) {
  const services = overview?.services ?? [];
  const incidents = overview?.active_incidents ?? [];
  const healthy = services.filter((service) => service.status === 'healthy').length;
  const showcase = Boolean(evaluation?.selected_recordings?.length);
  return (
    <>
      <section className="hero" data-testid={showcase ? 'recorded-entry' : undefined}>
        <div className="hero-top">
          <span className="eyebrow">
            <span className="live-dot" /> Independent portfolio / synthetic environment
          </span>
          <span className="hero-id mono">ENV-DEMO-001</span>
        </div>
        <p className="hero-product">CreditOps AI</p>
        <h1>
          AI-assisted incident intelligence
          <br className="desktop-break" /> for electronic trading systems.
        </h1>
        <p className="hero-description">
          {showcase
            ? 'Inspect three completed development examples: application-selected MCP evidence collection, a real model proposal, separate local validation, and a conservative advisory outcome.'
            : 'Correlate synthetic telemetry through read-only diagnostics and inspect an advisory failure-domain assessment.'}
        </p>
        <div className="hero-actions">
          <button
            className="button primary"
            onClick={onRun}
            disabled={busy || scenarios.length === 0}
            data-testid={showcase ? 'view-recorded-investigation' : undefined}
          >
            <Play size={15} fill="currentColor" />{' '}
            {showcase ? 'View recorded investigation' : 'Run Incident Demo'}{' '}
            <ArrowRight size={16} />
          </button>
          <span className="hero-note">
            <ShieldCheck size={14} /> Entirely synthetic data · no API key required
          </span>
        </div>
        {showcase && (
          <div className="showcase-labels">
            <Badge>Recorded model-assisted run</Badge>
            <Badge>No new model calls during playback</Badge>
            <Badge tone="amber">Human review required</Badge>
          </div>
        )}
        <div className="hero-grid-decoration" aria-hidden>
          <div />
          <div />
          <div />
          <span>
            OBSERVE
            <br />
            CORRELATE
            <br />
            VERIFY
          </span>
        </div>
      </section>
      {!showcase && (
        <div className="stats-grid">
          <Stat
            icon={<Activity size={17} />}
            label="Environment"
            value={overview ? (incidents.length ? 'Degraded' : 'Operational') : 'Connecting'}
            detail="Synthetic trading environment"
            tone={incidents.length ? 'amber' : 'teal'}
          />
          <Stat
            icon={<Radio size={17} />}
            label="Active incidents"
            value={String(incidents.length)}
            detail={incidents.length ? 'Investigation available' : 'Awaiting scenario trigger'}
            tone={incidents.length ? 'amber' : 'neutral'}
          />
          <Stat
            icon={<Box size={17} />}
            label="Service health"
            value={services.length ? `${healthy}/${services.length}` : '—'}
            detail="Services reporting healthy"
            tone="teal"
          />
          <Stat
            icon={<ScanIcon />}
            label="Investigations"
            value={overview ? String(overview.investigation_count) : '—'}
            detail="Session-scoped assessments"
            tone="neutral"
          />
        </div>
      )}
      <div className="overview-main">
        <Panel
          title={showcase ? 'Choose a recorded example' : 'Incident simulation'}
          eyebrow={
            showcase ? 'Selected recorded synthetic examples' : 'Start the five-minute walkthrough'
          }
          action={<Badge tone="amber">3 scenarios</Badge>}
        >
          <div className="scenario-cards">
            {scenarios.map((scenario, index) => (
              <button
                key={scenario.id}
                onClick={() => onScenario(scenario.id)}
                className={`scenario-card ${selectedScenario === scenario.id ? 'selected' : ''}`}
                aria-pressed={selectedScenario === scenario.id}
                disabled={busy}
                data-testid={showcase ? 'recorded-example' : undefined}
                data-scenario={scenario.id}
              >
                <div>
                  <span className="scenario-number">0{index + 1}</span>
                  {index === 0 ? (
                    <Layers3 size={18} />
                  ) : index === 1 ? (
                    <Cable size={18} />
                  ) : (
                    <Box size={18} />
                  )}
                </div>
                <h3>
                  {showcase
                    ? (evaluation?.selected_recordings?.find(
                        (row) => row.scenario_id === scenario.id,
                      )?.title ?? scenario.title)
                    : scenario.title}
                </h3>
                <p>{showcase ? recordingDescription(scenario.id) : scenario.description}</p>
                <span className="scenario-bottom">
                  {showcase ? 'Recorded model-assisted run' : 'Synthetic incident'}{' '}
                  <ArrowUpRight size={13} />
                </span>
              </button>
            ))}
          </div>
          <div className="panel-foot">
            <span>
              {showcase
                ? 'Complete recorded snapshots · all times UTC'
                : `Simulated clock · ${overview?.clock.label ?? '60 seconds represent 12 minutes'}`}
            </span>
            <button className="text-button" onClick={onRun} disabled={busy || !scenarios.length}>
              {showcase ? 'Open selected recording' : 'Run selected incident'}{' '}
              <ArrowRight size={14} />
            </button>
          </div>
        </Panel>
        <Panel
          title={showcase ? 'What to inspect in five minutes' : 'Diagnostic coverage'}
          eyebrow="Evidence, never assumption"
        >
          {showcase ? (
            <div className="showcase-intro">
              <ol>
                <li>Trading problem and affected RFQs or orders.</li>
                <li>Four initial MCP checks selected by the application.</li>
                <li>One model decision to assess; one model assessment.</li>
                <li>Local validation, advisory outcome, and unresolved cause.</li>
              </ol>
              <p>
                These recordings contain no model-selected follow-up diagnostics. Original proposals
                and project review notes remain inspectable.
              </p>
              <Link className="text-button" href="/evaluations">
                Inspect the three-example results <ArrowRight size={14} />
              </Link>
            </div>
          ) : (
            <>
              <div className="coverage-list">
                <HealthRow name="Kafka consumer telemetry" value={health(overview?.kafka)} />
                <HealthRow name="FIX session connectivity" value={health(overview?.fix)} />
                <HealthRow name="Database connection pools" value={health(overview?.database)} />
                <HealthRow name="Diagnostic agent tools" value="read-only" />
              </div>
              <div className="benchmark-mini">
                <span className="eyebrow">Reproducible evaluations</span>
                {evaluation?.algorithms?.length ? (
                  <>
                    <strong>{evaluation.algorithms[0].cases} labeled synthetic cases</strong>
                    <p>
                      Generated results available. Deterministic provider comparison; live model
                      results require a separate run.
                    </p>
                  </>
                ) : (
                  <>
                    <strong>Benchmark not yet generated.</strong>
                    <p>Only measured harness artifacts appear here.</p>
                  </>
                )}
              </div>
            </>
          )}
        </Panel>
      </div>
      {!showcase && (
        <div className="grid-two">
          <Panel
            title="Incident watch"
            eyebrow="Session activity"
            action={<span className="tiny-label">POLLING / 2 SEC</span>}
          >
            {incidents.length ? (
              <div className="incident-watch">
                {incidents.map((incident) => (
                  <button key={incident.id} onClick={() => onIncident(incident)} disabled={busy}>
                    <div>
                      <span className="mono">{incident.id}</span>
                      <Status value={incident.severity} />
                    </div>
                    <h3>{incident.title}</h3>
                    <p>{incident.client_impact}</p>
                    <span className="muted">
                      Detected {time(incident.started_at)} UTC <ArrowRight size={14} />
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <Empty title="No active incidents">
                Run a scenario to watch telemetry change, detect an incident, and open an
                evidence-backed investigation.
              </Empty>
            )}
          </Panel>
          <Panel title="Service dependency map" eyebrow="Synthetic trading path">
            <ServiceMap topology={topology} incident={incidents[0]} compact />
          </Panel>
        </div>
      )}
      {!showcase && metrics.length > 0 && (
        <Panel title="Live telemetry window" eyebrow="Persisted synthetic samples">
          <div className="grid-two">
            {metrics.slice(0, 2).map((series, index) => (
              <TelemetryChart
                key={`${series.service}-${series.metric}`}
                series={series}
                color={index ? 'amber' : 'teal'}
                onEvidence={onEvidence}
              />
            ))}
          </div>
        </Panel>
      )}
    </>
  );
}
function recordingDescription(scenario: string): string {
  if (scenario === 'kafka-pricing-lag')
    return 'Stale or unavailable quotes and RFQ expiry; backlog symptoms with an unresolved trigger.';
  if (scenario === 'fix-connectivity')
    return 'Pending and uncertain acknowledgement; retransmission retains the same economic order identity.';
  return 'Database waits, processing timeouts, and RFQ expiry; the causal trigger remains unconfirmed.';
}
function Stat({
  icon,
  label,
  value,
  detail,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  detail: string;
  tone: string;
}) {
  return (
    <div className={`stat stat-${tone}`}>
      <div>
        <span>{label}</span>
        {icon}
      </div>
      <strong>{value}</strong>
      <p>
        <span className="status-dot" />
        {detail}
      </p>
    </div>
  );
}
function ScanIcon() {
  return <ShieldCheck size={17} />;
}
export function health(record?: Record<string, unknown>): string {
  if (!record) return 'connecting';
  if (typeof record.status === 'string') return record.status;
  if (typeof record.connected === 'boolean') return record.connected ? 'connected' : 'disconnected';
  return 'available';
}
function HealthRow({ name, value }: { name: string; value: string }) {
  return (
    <div className="health-row">
      <span>{name}</span>
      <Status value={value} />
    </div>
  );
}
