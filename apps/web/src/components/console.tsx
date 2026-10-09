'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  Box,
  Cable,
  ChevronRight,
  FileClock,
  FlaskConical,
  LayoutDashboard,
  Menu,
  Network,
  Radio,
  ScanLine,
  ShieldCheck,
  Workflow,
  X,
} from 'lucide-react';
import { api, streamInvestigation } from '@/lib/api';
import { readStorage, removeStorage, writeStorage } from '@/lib/storage';
import type {
  Evaluation,
  Evidence,
  Incident,
  Investigation,
  InvestigationMode,
  MetricSeries,
  Overview,
  Scenario,
  Topology,
} from '@/lib/types';
import { EvidenceDrawer } from './evidence-drawer';
import { Badge, Panel, Spinner } from './primitives';
import { ServiceMap } from './service-map';
import { OverviewView } from '@/views/overview';
import { IncidentView, ScenarioControls } from '@/views/incidents';
import { ObservabilityView } from '@/views/observability';
import { EvaluationsView } from '@/views/evaluations';
import { AboutView, ArchitectureView, DISCLAIMER, LibraryView, SAFETY } from '@/views/reference';

const navigation = [
  { id: 'overview', href: '/', label: 'Overview', icon: LayoutDashboard },
  { id: 'live-operations', href: '/live-operations', label: 'Live Operations', icon: Activity },
  { id: 'incidents', href: '/incidents', label: 'Incidents', icon: Radio },
  { id: 'investigator', href: '/investigator', label: 'AI Investigator', icon: ScanLine },
  { id: 'observability', href: '/observability', label: 'Observability', icon: GaugeIcon },
  { id: 'service-map', href: '/service-map', label: 'Service Map', icon: Network },
  { id: 'runbooks', href: '/runbooks', label: 'Runbooks', icon: BookOpen },
  { id: 'history', href: '/history', label: 'Incident History', icon: FileClock },
  { id: 'evaluations', href: '/evaluations', label: 'Evaluations', icon: FlaskConical },
  { id: 'architecture', href: '/architecture', label: 'Architecture', icon: Workflow },
  { id: 'about', href: '/about', label: 'About', icon: ShieldCheck },
];
function GaugeIcon(props: React.ComponentProps<typeof Activity>) {
  return <Cable {...props} />;
}
const copy: Record<string, [string, string]> = {
  overview: ['Overview', 'A connected view of your synthetic trading environment.'],
  'live-operations': [
    'Live operations',
    'Follow the signal as persisted telemetry changes with the simulated clock.',
  ],
  incidents: [
    'Incident workspace',
    'Inspect impact, correlate observations, and establish a supported failure domain.',
  ],
  investigator: [
    'AI investigator',
    'A transparent diagnostic workflow with inspectable evidence at every step.',
  ],
  observability: [
    'Observability',
    'Query service metrics, sanitized logs, stream state, and recent changes.',
  ],
  'service-map': [
    'Service dependency map',
    'Follow the electronic trading path and its downstream dependencies.',
  ],
  runbooks: [
    'Operational runbooks',
    'Safe diagnostic guidance for synthetic trading-support scenarios.',
  ],
  history: [
    'Historical incidents',
    'Retrieve comparable symptoms and inspect why a prior incident matches.',
  ],
  evaluations: [
    'Evaluation laboratory',
    'Real generated measurements. Explicit providers. Bounded claims.',
  ],
  architecture: [
    'System architecture',
    'The components and boundaries behind an evidence-grounded diagnostic platform.',
  ],
  about: [
    'About CreditOps AI',
    'An independent demonstration of production support, SRE, and AI engineering.',
  ],
};

export function Console({ view = 'overview', incidentId }: { view?: string; incidentId?: string }) {
  const router = useRouter();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedScenario, setSelectedScenario] = useState('kafka-pricing-lag');
  const [selectedId, setSelectedId] = useState(incidentId ?? '');
  const [topology, setTopology] = useState<Topology | null>(null);
  const [metrics, setMetrics] = useState<MetricSeries[]>([]);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [library, setLibrary] = useState<Evidence[]>([]);
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [investigating, setInvestigating] = useState(false);
  const [investigationMode, setInvestigationMode] = useState<InvestigationMode>('REPLAY');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const investigationGenerationRef = useRef(0);
  const selectionGenerationRef = useRef(0);
  const scenarioOperationRef = useRef(false);
  const navRef = useRef<HTMLElement | null>(null);
  const evidenceRequestRef = useRef(0);
  const active =
    incidents.find((item) => item.id === selectedId) ??
    incidents.find((item) => item.scenario === selectedScenario) ??
    incidents[0] ??
    null;
  const activeId = active?.id;

  const refresh = useCallback(async () => {
    try {
      const [nextOverview, nextIncidents, nextTopology] = await Promise.all([
        api<Overview>('/overview'),
        api<Incident[]>('/incidents'),
        api<Topology>('/services/topology'),
      ]);
      setOverview(nextOverview);
      setIncidents(nextIncidents);
      setTopology(nextTopology);
      setConnected(true);
      const id = activeId ?? nextIncidents.find((item) => item.scenario === selectedScenario)?.id;
      const nextMetrics = await api<MetricSeries[]>(
        `/metrics/query${id ? `?incident_id=${encodeURIComponent(id)}` : ''}`,
      );
      setMetrics(nextMetrics);
    } catch (cause) {
      setConnected(false);
      setError(cause instanceof Error ? cause.message : 'Diagnostic API connection failed');
    }
  }, [activeId, selectedScenario]);

  const monitorInvestigation = useCallback(
    async (value: Investigation, controller: AbortController, generation: number) => {
      const current = () =>
        generation === investigationGenerationRef.current && !controller.signal.aborted;
      if (!current()) return;
      setInvestigation(value);
      setInvestigationMode(value.mode === 'MCP_DEMO' ? 'MCP_DEMO' : 'REPLAY');
      if (!['running', 'pending', 'queued'].includes(value.status)) {
        setInvestigating(false);
        return;
      }
      setInvestigating(true);
      try {
        await streamInvestigation(
          value.id,
          (step) => {
            if (current())
              setInvestigation((previous) =>
                previous?.id === value.id
                  ? {
                      ...previous,
                      steps: [...previous.steps.filter((item) => item.id !== step.id), step],
                    }
                  : previous,
              );
          },
          (completed) => {
            if (!current()) return;
            if (completed.incident_id !== value.incident_id)
              throw new Error('Investigation returned an unexpected incident reference');
            setInvestigation(completed);
            void refresh();
          },
          controller.signal,
        );
      } catch (cause) {
        if (current())
          setError(
            cause instanceof Error ? cause.message : 'Investigation stream unavailable. Retry.',
          );
      } finally {
        if (current()) setInvestigating(false);
      }
    },
    [refresh],
  );

  const stopInvestigation = useCallback(() => {
    investigationGenerationRef.current += 1;
    abortRef.current?.abort();
    setInvestigating(false);
    setInvestigation(null);
  }, []);

  useEffect(() => {
    const initial = setTimeout(() => {
      void refresh();
    }, 0);
    const interval = setInterval(() => {
      void refresh();
    }, 2000);
    return () => {
      clearTimeout(initial);
      clearInterval(interval);
    };
  }, [refresh]);
  useEffect(() => {
    let stopped = false;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      try {
        const [nextScenarios, nextEvaluation] = await Promise.all([
          api<Scenario[]>('/scenarios'),
          api<Evaluation>('/evaluations/latest'),
        ]);
        if (!stopped) {
          setScenarios(nextScenarios);
          setEvaluation(nextEvaluation);
          setError(null);
        }
      } catch (cause) {
        if (!stopped) {
          setError(cause instanceof Error ? cause.message : 'Initial data unavailable');
          retry = setTimeout(() => {
            void load();
          }, 2000);
        }
      }
    };
    void load();
    return () => {
      stopped = true;
      if (retry) clearTimeout(retry);
    };
  }, []);
  useEffect(() => {
    if (view !== 'runbooks' && view !== 'history') return;
    void api<Evidence[]>(view === 'runbooks' ? '/runbooks' : '/history')
      .then(setLibrary)
      .catch((cause) => {
        setError(cause instanceof Error ? cause.message : 'Library unavailable');
      });
  }, [view]);
  useEffect(
    () => () => {
      selectionGenerationRef.current += 1;
      abortRef.current?.abort();
    },
    [],
  );
  useEffect(() => {
    if (!activeId) return;
    const saved = readStorage(`creditops-investigation:v1:${activeId}`);
    if (!saved) return;
    const controller = new AbortController();
    const generation = ++investigationGenerationRef.current;
    abortRef.current?.abort();
    abortRef.current = controller;
    void api<Investigation>(`/investigations/${encodeURIComponent(saved)}`, {
      signal: controller.signal,
    })
      .then((value) => monitorInvestigation(value, controller, generation))
      .catch(() => {
        if (!controller.signal.aborted) removeStorage(`creditops-investigation:v1:${activeId}`);
      });
    return () => {
      controller.abort();
    };
  }, [activeId, monitorInvestigation]);
  useEffect(() => {
    if (!mobileNav) return;
    const prior = document.activeElement as HTMLElement | null;
    navRef.current?.querySelector<HTMLElement>('.sidebar-close')?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileNav(false);
      if (event.key !== 'Tab') return;
      const items = navRef.current?.querySelectorAll<HTMLElement>('a, button');
      if (!items?.length) return;
      const first = items[0],
        last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handler);
    const original = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handler);
      document.body.style.overflow = original;
      prior?.focus();
    };
  }, [mobileNav]);

  const onEvidence = useCallback(
    (id: string) => {
      const request = ++evidenceRequestRef.current;
      setEvidenceId(id);
      setEvidenceError(null);
      const persisted =
        investigation?.incident_id === activeId
          ? investigation.evidence.find((item) => item.id === id)
          : undefined;
      setEvidence(persisted ?? null);
      if (persisted) return;
      void api<Evidence>(`/evidence/${encodeURIComponent(id)}`)
        .then((value) => {
          if (request === evidenceRequestRef.current) setEvidence(value);
        })
        .catch((cause) => {
          if (request === evidenceRequestRef.current)
            setEvidenceError(cause instanceof Error ? cause.message : 'Evidence not found');
        });
    },
    [investigation, activeId],
  );
  const closeEvidence = useCallback(() => setEvidenceId(null), []);
  const chooseIncident = (item: Incident) => {
    if (scenarioOperationRef.current) return;
    selectionGenerationRef.current += 1;
    stopInvestigation();
    setSelectedId(item.id);
    setSelectedScenario(item.scenario);
  };
  const chooseScenario = (value: string) => {
    if (scenarioOperationRef.current) return;
    selectionGenerationRef.current += 1;
    stopInvestigation();
    setSelectedScenario(value);
    setSelectedId(incidents.find((item) => item.scenario === value)?.id ?? '');
  };
  const run = async () => {
    if (scenarioOperationRef.current) return;
    scenarioOperationRef.current = true;
    const generation = ++selectionGenerationRef.current;
    const scenario = selectedScenario;
    setBusy(true);
    setError(null);
    stopInvestigation();
    try {
      const created = await api<Incident>(`/demo/scenarios/${scenario}/run`, {
        method: 'POST',
      });
      setIncidents((previous) => [...previous.filter((item) => item.id !== created.id), created]);
      if (generation !== selectionGenerationRef.current) return;
      stopInvestigation();
      setSelectedId(created.id);
      setSelectedScenario(created.scenario);
      await refresh();
      if (generation === selectionGenerationRef.current && view === 'overview')
        router.push('/incidents');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Scenario failed to start');
    } finally {
      scenarioOperationRef.current = false;
      setBusy(false);
    }
  };
  const reset = async () => {
    if (scenarioOperationRef.current) return;
    scenarioOperationRef.current = true;
    const generation = ++selectionGenerationRef.current;
    const scenario = selectedScenario;
    setBusy(true);
    setError(null);
    stopInvestigation();
    try {
      await api(`/demo/scenarios/${scenario}/reset`, { method: 'POST' });
      const resetting = incidents.find((item) => item.scenario === scenario);
      if (resetting) removeStorage(`creditops-investigation:v1:${resetting.id}`);
      setIncidents((previous) => previous.filter((item) => item.scenario !== scenario));
      if (generation !== selectionGenerationRef.current) return;
      setSelectedId('');
      setInvestigation(null);
      setMetrics([]);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Scenario reset failed');
    } finally {
      scenarioOperationRef.current = false;
      setBusy(false);
    }
  };
  const investigate = async () => {
    if (!active || scenarioOperationRef.current) return;
    stopInvestigation();
    const controller = new AbortController();
    const generation = ++investigationGenerationRef.current;
    const current = () =>
      generation === investigationGenerationRef.current && !controller.signal.aborted;
    abortRef.current = controller;
    setInvestigating(true);
    setError(null);
    setInvestigation(null);
    try {
      const created = await api<Investigation>('/investigations', {
        method: 'POST',
        body: JSON.stringify({ incident_id: active.id, mode: investigationMode }),
        signal: controller.signal,
      });
      if (!current()) return;
      writeStorage(`creditops-investigation:v1:${active.id}`, created.id);
      await monitorInvestigation(created, controller, generation);
    } catch (cause) {
      if (current())
        setError(cause instanceof Error ? cause.message : 'Investigation failed. Try again.');
    } finally {
      if (current()) setInvestigating(false);
    }
  };

  const page = copy[view] ?? copy.overview;
  const controls = {
    scenarios,
    selectedScenario,
    onScenario: chooseScenario,
    onRun: () => void run(),
    onReset: () => void reset(),
    busy: busy || investigating,
    running: busy,
    hasIncident: incidents.some((item) => item.scenario === selectedScenario),
  };
  const incidentProps = {
    incident: active,
    incidents,
    metrics,
    topology,
    investigation,
    investigating,
    investigationMode,
    onInvestigationMode: setInvestigationMode,
    running: busy,
    onInvestigate: () => void investigate(),
    onEvidence,
    onIncident: chooseIncident,
  };

  return (
    <div className="console-shell">
      <a className="skip-link" href="#main">
        Skip to main content
      </a>
      {mobileNav && (
        <button
          className="nav-backdrop"
          aria-label="Dismiss navigation"
          onClick={() => setMobileNav(false)}
        />
      )}
      <aside
        ref={navRef}
        role={mobileNav ? 'dialog' : undefined}
        aria-modal={mobileNav ? true : undefined}
        id="primary-navigation"
        className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}
        aria-label="Main navigation"
      >
        <button
          className="icon-button sidebar-close"
          aria-label="Close navigation"
          onClick={() => setMobileNav(false)}
        >
          <X size={17} />
        </button>
        <Link href="/" className="brand">
          <span className="brand-icon">
            <Box size={22} strokeWidth={1.8} />
          </span>
          <div>
            <strong>
              CreditOps<span> AI</span>
            </strong>
            <small>INCIDENT INTELLIGENCE</small>
          </div>
        </Link>
        <div className="sidebar-environment">
          <span className="live-dot" />
          <span>Synthetic environment</span>
          <span className="mono">DEMO</span>
        </div>
        <span className="nav-label">OPERATIONS CONSOLE</span>
        <nav>
          {navigation.map(({ id, href, label, icon: Icon }, index) => (
            <Link
              href={href}
              key={id}
              className={`nav-link ${view === id ? 'nav-active' : ''} ${index === 8 ? 'nav-separated' : ''}`}
              aria-current={view === id ? 'page' : undefined}
              onClick={() => setMobileNav(false)}
            >
              <Icon size={17} strokeWidth={1.7} />
              <span>{label}</span>
              {id === 'incidents' && incidents.length > 0 && (
                <span className="nav-count">{incidents.length}</span>
              )}
            </Link>
          ))}
        </nav>
        <div className="sidebar-foot">
          <ShieldCheck size={18} />
          <strong>Diagnostic access only</strong>
          <p>Human engineers retain operational authority.</p>
          <div>
            <span className="status-dot" /> Synthetic / session scoped
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              aria-expanded={mobileNav}
              aria-controls="primary-navigation"
              onClick={() => setMobileNav(true)}
            >
              <Menu size={20} />
            </button>
            <span className="breadcrumb">
              Operations <ChevronRight size={13} />
              <strong>{page[0]}</strong>
            </span>
          </div>
          <div className="topbar-right">
            <Badge tone={connected ? 'teal' : 'amber'}>
              {connected ? 'API connected' : 'Connecting to API'}
            </Badge>
            <span className="topbar-demo">SYNTHETIC DATA</span>
            <span className="operator-avatar" aria-label="Demo operator">
              OP
            </span>
          </div>
        </header>
        <main id="main">
          <div className="page-header">
            <div>
              <span className="eyebrow">CREDITOPS AI / {view.replaceAll('-', ' ')}</span>
              <h1>{page[0]}</h1>
              <p>{page[1]}</p>
            </div>
            <div className="page-context">
              <span className="live-dot" />
              <span>
                {overview?.telemetry_mode
                  ? overview.telemetry_mode.replaceAll('_', ' ')
                  : 'Persisted demo telemetry'}
              </span>
            </div>
          </div>
          {error && (
            <div className="error-banner" role="alert">
              <span>{error}</span>
              <button
                className="icon-button"
                aria-label="Dismiss error"
                onClick={() => setError(null)}
              >
                <X size={16} />
              </button>
              <button
                className="text-button"
                onClick={() => {
                  setError(null);
                  void refresh();
                }}
              >
                Retry
              </button>
            </div>
          )}
          {view === 'overview' && (
            <OverviewView
              overview={overview}
              scenarios={scenarios}
              selectedScenario={selectedScenario}
              onScenario={chooseScenario}
              onRun={() => void run()}
              busy={busy}
              metrics={metrics}
              topology={topology}
              onEvidence={onEvidence}
              onIncident={(item) => {
                if (scenarioOperationRef.current) return;
                chooseIncident(item);
                router.push('/incidents');
              }}
              evaluation={evaluation}
            />
          )}
          {['incidents', 'investigator', 'live-operations'].includes(view) && (
            <>
              <ScenarioControls {...controls} />
              <IncidentView {...incidentProps} onlyInvestigator={view === 'investigator'} />
            </>
          )}
          {view === 'observability' && (
            <ObservabilityView
              incident={active}
              incidents={incidents}
              onIncident={chooseIncident}
              selectionDisabled={busy}
              metrics={metrics}
              onEvidence={onEvidence}
            />
          )}
          {view === 'service-map' && (
            <Panel
              title="Electronic credit trading topology"
              eyebrow="10 synthetic services / directed dependencies"
            >
              <ServiceMap topology={topology} incident={active} />
            </Panel>
          )}
          {(view === 'runbooks' || view === 'history') && (
            <LibraryView items={library} onEvidence={onEvidence} history={view === 'history'} />
          )}
          {view === 'evaluations' && <EvaluationsView evaluation={evaluation} />}
          {view === 'architecture' && <ArchitectureView />}
          {view === 'about' && <AboutView />}
          {!overview && !error && (
            <div className="loading-row">
              <Spinner /> Connecting to the diagnostic API…
            </div>
          )}
          <footer className="console-footer">
            <div>
              <ShieldCheck size={16} />
              <span>{DISCLAIMER}</span>
            </div>
            <p>{SAFETY}</p>
            <span className="footer-meta">
              CREDITOPS AI <span>INDEPENDENT PORTFOLIO</span>
              <Link href="/architecture">
                Inspect architecture <ArrowUpRight size={12} />
              </Link>
            </span>
          </footer>
        </main>
      </div>
      {evidenceId && (
        <EvidenceDrawer
          id={evidenceId}
          evidence={evidence}
          error={evidenceError}
          onClose={closeEvidence}
        />
      )}
    </div>
  );
}
