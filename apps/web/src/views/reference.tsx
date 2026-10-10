import { useMemo, useState } from 'react';
import Link from 'next/link';
import {
  ArrowDown,
  ArrowRight,
  BookOpen,
  Box,
  Cable,
  Database,
  FileClock,
  Gauge,
  Network,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import type { Evidence } from '@/lib/types';
import { Citation, Empty, Panel } from '@/components/primitives';

export const DISCLAIMER =
  'CreditOps AI is an independent portfolio project using entirely synthetic data. It is not affiliated with or connected to any trading venue, broker, financial institution, or employer.';
export const SAFETY =
  'CreditOps AI intentionally exposes diagnostic capabilities only. AI recommendations are advisory. Production mutation tools are excluded by design.';

export function LibraryView({
  items,
  onEvidence,
  history = false,
}: {
  items: Evidence[];
  onEvidence: (id: string) => void;
  history?: boolean;
}) {
  const [query, setQuery] = useState('');
  const filtered = useMemo(
    () => items.filter((item) => JSON.stringify(item).toLowerCase().includes(query.toLowerCase())),
    [items, query],
  );
  return (
    <>
      <div className="library-search">
        <label htmlFor="library-search">
          {history ? 'Search historical incidents' : 'Search runbooks'}
        </label>
        <input
          id="library-search"
          placeholder="Search symptoms, services, error signatures…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <span className="muted">{filtered.length} synthetic records</span>
      </div>
      <div className="grid-two">
        {filtered.map((item) => (
          <Panel
            key={item.id}
            title={String(item.data.title ?? item.summary)}
            eyebrow={`${item.kind} / ${item.service}`}
          >
            <div className="library-record">
              {history ? (
                <FileClock size={24} strokeWidth={1.3} />
              ) : (
                <BookOpen size={24} strokeWidth={1.3} />
              )}
              <p>{item.summary}</p>
              {history && (
                <p className="muted">
                  Matching explanations and source fields are available in the evidence record.
                  Retrieval combines overlapping services, symptoms, and error signatures; optional
                  vector search requires configured embeddings.
                </p>
              )}
              <div className="tags">
                {Array.isArray(item.data.tags) &&
                  item.data.tags.map((tag) => <span key={String(tag)}>{String(tag)}</span>)}
              </div>
              <Citation id={item.id} onEvidence={onEvidence} />
            </div>
          </Panel>
        ))}
      </div>
      {!filtered.length && (
        <Empty title="No matching records">Try a different symptom or service.</Empty>
      )}
      <div className="safety-note">
        <ShieldCheck size={17} />
        <span>
          {history
            ? 'Historical incidents are synthetic learning records. Matches support a hypothesis; they do not prove a root cause.'
            : 'Runbooks contain human-reviewed diagnostic guidance. Commands and rollback considerations are never executed by the investigator.'}
        </span>
      </div>
    </>
  );
}

export function ArchitectureView() {
  const layers = [
    [
      {
        icon: <Box />,
        title: 'User / operations engineer',
        text: 'Session-scoped browser demo · no public login',
      },
    ],
    [
      {
        icon: <Network />,
        title: 'Next.js web console',
        text: 'Typed REST client · SSE trace · same-origin proxy',
      },
      {
        icon: <Cable />,
        title: 'MCP diagnostic interface',
        text: 'Official SDK · stdio + HTTP · bounded read-only tools',
      },
    ],
    [
      {
        icon: <Gauge />,
        title: 'FastAPI diagnostic API',
        text: 'Validated schemas · rate limits · sanitized evidence',
      },
      {
        icon: <Sparkles />,
        title: 'AI investigator',
        text: 'Evidence-adaptive loop · explicit MCP / direct adapters · bounded claim validation',
      },
    ],
    [
      {
        icon: <Database />,
        title: 'PostgreSQL / pgvector',
        text: 'Immutable evidence · persisted timelines · lexical retrieval fallback',
      },
      {
        icon: <Network />,
        title: 'Kafka / Redpanda',
        text: 'Real event streaming locally · persisted telemetry in public demo',
      },
      {
        icon: <Cable />,
        title: 'Synthetic FIX simulator',
        text: 'Heartbeats · reconnects · sequence gaps · acknowledgements',
      },
    ],
    [
      {
        icon: <Gauge />,
        title: 'Prometheus / Grafana',
        text: 'Local metrics collection & provisioned dashboards',
      },
      {
        icon: <BookOpen />,
        title: 'Runbooks / historical incidents',
        text: 'Synthetic operational knowledge · treated as untrusted data',
      },
    ],
  ];
  return (
    <>
      <Panel
        title="The diagnostic path"
        eyebrow="Architecture / independent synthetic infrastructure"
      >
        <div className="architecture-diagram">
          {layers.map((layer, index) => (
            <div key={index} className="architecture-layer">
              {index > 0 && (
                <div className="architecture-connect">
                  <ArrowDown size={20} />
                  <span>
                    {index === 2
                      ? 'validated read-only requests'
                      : index === 3
                        ? 'bounded diagnostic retrieval'
                        : index === 4
                          ? 'observability & operational knowledge'
                          : 'same-origin API / diagnostic client'}
                  </span>
                </div>
              )}
              <div className="architecture-row">
                {layer.map((node) => (
                  <div className="architecture-node" key={node.title}>
                    {node.icon}
                    <h3>{node.title}</h3>
                    <p>{node.text}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Panel>
      <div className="grid-three">
        <Panel title="Real locally" eyebrow="Docker Compose">
          <ul className="prose-list">
            <li>PostgreSQL with optional pgvector</li>
            <li>Redpanda event publication and consumption</li>
            <li>Prometheus and Grafana provisioning</li>
            <li>FastAPI, MCP, and synthetic FIX simulation</li>
          </ul>
        </Panel>
        <Panel title="Public demo" eyebrow="Predictable, bounded cost">
          <ul className="prose-list">
            <li>Persisted synthetic telemetry adapter</li>
            <li>Accelerated deterministic incident clock</li>
            <li>Three selected recordings from completed model-assisted development runs</li>
            <li>
              Application-selected initial MCP checks, recorded model proposal, and local validation
            </li>
            <li>Keyless replay: no new model, embedding, or recorded-tool calls</li>
            <li>Legacy deterministic MCP demonstration remains separately labeled</li>
          </ul>
        </Panel>
        <Panel title="Optional integrations" eyebrow="Explicit configuration">
          <ul className="prose-list">
            <li>Protected OpenAI or Anthropic live provider</li>
            <li>Neon PostgreSQL deployment</li>
            <li>Embeddings and vector retrieval</li>
            <li>Vercel frontend and container backend hosting</li>
          </ul>
        </Panel>
      </div>
      <div className="safety-note">
        <ShieldCheck size={18} />
        <span>{SAFETY}</span>
      </div>
    </>
  );
}

export function AboutView() {
  return (
    <>
      <section className="about-intro">
        <span className="eyebrow">Independent engineering portfolio</span>
        <h2>
          Operational authority stays
          <br />
          with human engineers.
        </h2>
        <p>
          CreditOps AI demonstrates how production-support teams can turn fragmented diagnostic
          signals into an inspectable incident assessment. The project models electronic credit
          trading workflows using fictional services, clients, RFQs, orders, and FIX sessions.
        </p>
      </section>
      <div className="grid-two">
        <Panel title="Why this project exists" eyebrow="The support problem">
          <p className="prose">
            An incident rarely arrives with its cause attached. Latency, stale quotes, consumer
            backlog, session reconnects, and deployment changes live in different systems. This
            console connects those signals through bounded tools and stable evidence references,
            giving an engineer a reviewable starting point for triage.
          </p>
        </Panel>
        <Panel title="Evidence before certainty" eyebrow="The engineering principle">
          <p className="prose">
            The investigator separates observations, supported failure conditions, candidate
            triggers and unknown causes. Its support score is uncalibrated, and its domain-specific
            checks do not establish arbitrary claim truth. The selected recordings preserve real
            model proposals and separate validation with project review notes. Playback makes no new
            model or recorded-tool calls. The legacy deterministic MCP demonstration remains a
            separate path. Synthetic evaluations do not establish financial losses or production
            outcomes.
          </p>
        </Panel>
        <Panel title="Why production mutation is excluded" eyebrow="Deliberate safety boundary">
          <p className="prose">{SAFETY}</p>
          <p className="prose">
            No agent tool can restart a service, roll back a deployment, scale infrastructure,
            execute shell commands, or mutate records. Diagnostic telemetry is sanitized and treated
            as untrusted data. Suggested next steps remain subject to human verification.
          </p>
        </Panel>
        <Panel title="Scope & limitations" eyebrow="Honest portfolio positioning">
          <p className="prose">
            This is a compact, independently built demonstration. It does not connect to real
            trading systems and has no real customer or incident data. The three selected completed
            examples are development recordings, with earlier failed or abstaining attempts
            preserved. They do not establish general live-model accuracy. Original model latency and
            synthetic benchmark latency are not measured reductions in real production MTTR. Paid
            live-model and embedding actions are disabled in the public showcase profile.
          </p>
          <Link className="text-button" href="/evaluations">
            Inspect the generated evaluations <ArrowRight size={14} />
          </Link>
        </Panel>
      </div>
      <div className="disclaimer-box">
        <ShieldCheck size={22} />
        <p>{DISCLAIMER}</p>
      </div>
    </>
  );
}
