import { useCallback, useEffect, useState } from 'react';
import { Search, SlidersHorizontal } from 'lucide-react';
import { api } from '@/lib/api';
import type { Evidence, Incident, MetricSeries } from '@/lib/types';
import { Citation, Empty, Panel, Spinner, time } from '@/components/primitives';
import { TelemetryChart } from '@/components/telemetry-chart';

export function ObservabilityView({
  incident,
  incidents,
  onIncident,
  selectionDisabled = false,
  metrics,
  onEvidence,
}: {
  incident: Incident | null;
  incidents: Incident[];
  onIncident: (incident: Incident) => void;
  selectionDisabled?: boolean;
  metrics: MetricSeries[];
  onEvidence: (id: string) => void;
}) {
  const [telemetry, setTelemetry] = useState<Record<string, Evidence[]>>({});
  const [logs, setLogs] = useState<Evidence[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [filters, setFilters] = useState({
    service: '',
    severity: '',
    trace_id: '',
    q: '',
    start: '',
    end: '',
  });
  const [metricFilters, setMetricFilters] = useState({
    service: '',
    metric: '',
    aggregation: 'raw',
  });
  const [queriedMetrics, setQueriedMetrics] = useState<MetricSeries[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const incidentId = incident?.id;
  const initialLoad = useCallback(async () => {
    try {
      const query = incidentId ? `?incident_id=${encodeURIComponent(incidentId)}` : '';
      const records = await Promise.all(
        ['kafka', 'fix', 'database', 'deployments'].map(
          async (kind) => [kind, await api<Evidence[]>(`/telemetry/${kind}${query}`)] as const,
        ),
      );
      setTelemetry(Object.fromEntries(records));
      const result = await api<{ items: Evidence[]; total: number }>(
        `/logs/search${query}${query ? '&' : '?'}limit=20`,
      );
      setLogs(result.items);
      setTotal(result.total);
      setOffset(0);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to retrieve telemetry');
    }
  }, [incidentId]);
  useEffect(() => {
    const initial = setTimeout(() => {
      void initialLoad();
    }, 0);
    return () => clearTimeout(initial);
  }, [initialLoad]);

  const search = async (nextOffset = 0) => {
    setBusy(true);
    setError(null);
    try {
      const query = new URLSearchParams({
        limit: '20',
        offset: String(nextOffset),
        ...(incidentId ? { incident_id: incidentId } : {}),
      });
      Object.entries(filters).forEach(([key, value]) => {
        if (value)
          query.set(key, key === 'start' || key === 'end' ? new Date(value).toISOString() : value);
      });
      const result = await api<{ items: Evidence[]; total: number }>(`/logs/search?${query}`);
      setLogs(result.items);
      setTotal(result.total);
      setOffset(nextOffset);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Log query failed');
    } finally {
      setBusy(false);
    }
  };
  const queryMetrics = async () => {
    setBusy(true);
    setError(null);
    try {
      const query = new URLSearchParams(incidentId ? { incident_id: incidentId } : {});
      Object.entries(metricFilters).forEach(([key, value]) => {
        if (value) query.set(key, value);
      });
      for (const key of ['start', 'end'] as const)
        if (filters[key]) query.set(key, new Date(filters[key]).toISOString());
      setQueriedMetrics(await api<MetricSeries[]>(`/metrics/query?${query}`));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Metric query failed');
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="window-selector">
        <SlidersHorizontal size={16} />
        <label htmlFor="incident-window">Incident time window</label>
        <select
          id="incident-window"
          value={incidentId ?? ''}
          disabled={selectionDisabled}
          onChange={(event) => {
            const item = incidents.find((value) => value.id === event.target.value);
            if (item) {
              onIncident(item);
              setQueriedMetrics(null);
            }
          }}
        >
          <option value="">Current synthetic environment</option>
          {incidents.map((item) => (
            <option key={item.id} value={item.id}>
              {item.id} · {item.title}
            </option>
          ))}
        </select>
        <span className="tiny-label">PERSISTED TELEMETRY</span>
      </div>
      {error && (
        <p className="error-banner" role="alert">
          {error}
        </p>
      )}
      <Panel title="Service-level metrics" eyebrow="Bounded diagnostic query">
        <form
          className="query-form metric-query"
          onSubmit={(event) => {
            event.preventDefault();
            void queryMetrics();
          }}
        >
          <label>
            Service
            <input
              placeholder="e.g. quote-service"
              value={metricFilters.service}
              onChange={(event) =>
                setMetricFilters({ ...metricFilters, service: event.target.value })
              }
            />
          </label>
          <label>
            Metric
            <input
              placeholder="e.g. request_latency_p95"
              value={metricFilters.metric}
              onChange={(event) =>
                setMetricFilters({ ...metricFilters, metric: event.target.value })
              }
            />
          </label>
          <label>
            Aggregation
            <select
              value={metricFilters.aggregation}
              onChange={(event) =>
                setMetricFilters({ ...metricFilters, aggregation: event.target.value })
              }
            >
              <option value="raw">Raw samples</option>
              <option value="avg">Average</option>
              <option value="max">Maximum</option>
              <option value="min">Minimum</option>
            </select>
          </label>
          <button className="button secondary" disabled={busy}>
            Query metrics
          </button>
        </form>
        <div className="grid-two charts-grid">
          {(queriedMetrics ?? metrics).length ? (
            (queriedMetrics ?? metrics).map((series, index) => (
              <TelemetryChart
                key={`${series.service}-${series.metric}`}
                series={series}
                color={index % 2 ? 'amber' : 'teal'}
                onEvidence={onEvidence}
              />
            ))
          ) : (
            <Empty title="No metric samples in this window">
              Run an incident to populate telemetry, or adjust your query.
            </Empty>
          )}
        </div>
      </Panel>
      <div className="grid-three">
        {['kafka', 'fix', 'database'].map((kind) => (
          <Panel
            key={kind}
            title={
              kind === 'kafka'
                ? 'Kafka consumer health'
                : kind === 'fix'
                  ? 'FIX session health'
                  : 'Database health'
            }
            eyebrow="Diagnostic records"
          >
            <EvidenceRecords items={telemetry[kind] ?? []} onEvidence={onEvidence} />
          </Panel>
        ))}
      </div>
      <Panel
        title="Log explorer"
        eyebrow="Sanitized, bounded, searchable"
        action={<span className="tiny-label">{total} MATCHING RECORDS</span>}
      >
        <form
          className="query-form"
          onSubmit={(event) => {
            event.preventDefault();
            void search();
          }}
        >
          <label>
            Service
            <input
              value={filters.service}
              placeholder="All services"
              onChange={(event) => setFilters({ ...filters, service: event.target.value })}
            />
          </label>
          <label>
            Severity
            <select
              value={filters.severity}
              onChange={(event) => setFilters({ ...filters, severity: event.target.value })}
            >
              <option value="">All severities</option>
              <option>INFO</option>
              <option>WARN</option>
              <option>ERROR</option>
              <option>CRITICAL</option>
            </select>
          </label>
          <label>
            Trace ID
            <input
              value={filters.trace_id}
              placeholder="TRACE-DEMO…"
              onChange={(event) => setFilters({ ...filters, trace_id: event.target.value })}
            />
          </label>
          <label>
            Free text
            <input
              value={filters.q}
              placeholder="pool timeout, stale…"
              onChange={(event) => setFilters({ ...filters, q: event.target.value })}
            />
          </label>
          <label>
            From (local time)
            <input
              type="datetime-local"
              value={filters.start}
              onChange={(event) => setFilters({ ...filters, start: event.target.value })}
            />
          </label>
          <label>
            To (local time)
            <input
              type="datetime-local"
              value={filters.end}
              onChange={(event) => setFilters({ ...filters, end: event.target.value })}
            />
          </label>
          <button className="button secondary" disabled={busy}>
            {busy ? <Spinner /> : <Search size={14} />} Search logs
          </button>
        </form>
        <div className="table-scroll">
          <table className="logs-table">
            <thead>
              <tr>
                <th>UTC time / evidence</th>
                <th>Service</th>
                <th>Level</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id}>
                  <td>
                    <span>{time(log.timestamp)}</span>
                    <Citation id={log.id} onEvidence={onEvidence} />
                  </td>
                  <td>
                    <code>{log.service}</code>
                  </td>
                  <td>
                    <span className="log-level">
                      {String(log.data.level ?? log.data.severity ?? 'INFO')}
                    </span>
                  </td>
                  <td>
                    {log.summary}
                    <small className="mono muted">{String(log.data.trace_id ?? '')}</small>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!logs.length && (
          <Empty title="No logs match this query">Adjust your filters or start an incident.</Empty>
        )}
        <div className="pagination">
          <span>
            Showing {total ? offset + 1 : 0}–{Math.min(offset + logs.length, total)} of {total}
          </span>
          <button
            className="text-button"
            disabled={busy || offset === 0}
            onClick={() => void search(Math.max(0, offset - 20))}
          >
            Previous
          </button>
          <button
            className="text-button"
            disabled={busy || offset + logs.length >= total}
            onClick={() => void search(offset + 20)}
          >
            Next
          </button>
        </div>
      </Panel>
      <Panel title="Recent deployments & change events" eyebrow="Temporal correlation">
        <EvidenceRecords items={telemetry.deployments ?? []} onEvidence={onEvidence} />
      </Panel>
    </>
  );
}

export function EvidenceRecords({
  items,
  onEvidence,
}: {
  items: Evidence[];
  onEvidence: (id: string) => void;
}) {
  if (!items.length) return <div className="record-empty">No records in this session window.</div>;
  return (
    <div className="evidence-records">
      {items.slice(0, 12).map((item) => (
        <article key={item.id}>
          <div>
            <span className="mono muted">{item.service}</span>
            <span className="record-time">{time(item.timestamp)} UTC</span>
          </div>
          <h3>{item.summary}</h3>
          <div className="record-values">
            {Object.entries(item.data)
              .filter(
                ([, value]) =>
                  typeof value === 'number' ||
                  typeof value === 'boolean' ||
                  (typeof value === 'string' && value.length < 45),
              )
              .slice(0, 4)
              .map(([key, value]) => (
                <span key={key}>
                  <small>{key.replaceAll('_', ' ')}</small>
                  <strong>{String(value)}</strong>
                </span>
              ))}
          </div>
          <Citation id={item.id} onEvidence={onEvidence} />
        </article>
      ))}
    </div>
  );
}
