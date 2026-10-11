import { useEffect, useRef, useState } from 'react';
import type {
  RecordedRecording,
  TimelineView,
  TimedSource,
  WorkspaceFilters,
} from '@/lib/recorded-evidence';
import {
  defaultWorkspaceFilters,
  filterRecordedEvidence,
  metricDomain,
  recordedTimestampMs,
  samplePosition,
  recordedEconomicOrderId,
} from '@/lib/recorded-evidence';
import { Citation, Empty, Panel, time } from './primitives';
export function timelineSourceIds(view: TimelineView): ReadonlySet<string> {
  return new Set([
    ...view.metrics.flatMap((group) => group.samples.map((row) => row.source.id)),
    ...view.logs.map((row) => row.source.id),
    ...view.business.map((row) => row.source.id),
  ]);
}
type Props = {
  recording: RecordedRecording;
  filters: WorkspaceFilters;
  selectedSourceId: string | null;
  onFilters: (value: WorkspaceFilters) => void;
  onSelect: (id: string) => void;
};
export function RecordedEvidenceTimeline({
  recording,
  filters,
  selectedSourceId,
  onFilters,
  onSelect,
}: Props) {
  const [chooser, setChooser] = useState<{ timestampMs: number; sourceIds: string[] } | null>(null);
  const chooserRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (chooser) chooserRef.current?.querySelector<HTMLButtonElement>('button')?.focus();
  }, [chooser]);
  const view = filterRecordedEvidence(recording, filters);
  const rows = [
    ...view.metrics.flatMap((group) => group.samples),
    ...view.logs,
    ...view.business,
  ].sort((a, b) => a.timestampMs - b.timestampMs || a.source.id.localeCompare(b.source.id));
  const selected = selectedSourceId ? recording.sources.get(selectedSourceId) : undefined;
  const selectedTime = selected ? recordedTimestampMs(selected.timestamp) : null;
  const instants = new Map<number, TimedSource[]>();
  for (const row of rows) {
    const tied = instants.get(row.timestampMs) ?? [];
    tied.push(row);
    instants.set(row.timestampMs, tied);
  }
  const coverage = filters.window ?? recording.coverage;
  const orderChoices = recording.journeys.flatMap((journey) => {
    if (journey.rfqId === null || (filters.request && journey.rfqId !== filters.request.rfqId))
      return [];
    return [
      ...new Set(
        journey.events.flatMap((event) => {
          const id = recordedEconomicOrderId(event);
          return id === null ? [] : [id];
        }),
      ),
    ]
      .sort()
      .map((id) => ({ id, rfqId: journey.rfqId! }));
  });
  const attribution = (row: TimedSource) => {
    if (!filters.request || !['metric', 'log'].includes(row.source.kind)) return null;
    return view.relatedSourceIds.has(row.source.id)
      ? 'Explicit returned identity match to this ' +
          (filters.request.economicOrderId ? 'economic order' : 'RFQ')
      : 'Not attributed to this ' + (filters.request.economicOrderId ? 'economic order' : 'RFQ');
  };
  const services = [
    ...new Set([
      ...recording.metrics.map((group) => group.service),
      ...recording.logs.map((row) => row.source.service),
    ]),
  ].sort();
  const plottableIds = new Set([
    ...recording.metrics.flatMap((group) => group.samples.map((row) => row.source.id)),
    ...recording.logs.map((row) => row.source.id),
    ...recording.journeys.flatMap((journey) =>
      journey.events
        .filter((row) => recordedTimestampMs(row.timestamp) !== null)
        .map((row) => row.id),
    ),
  ]);
  const context = [...recording.sources.values()].filter((source) => !plottableIds.has(source.id));
  const windowValue = (side: 'startMs' | 'endMs') =>
    filters.window && Number.isFinite(filters.window[side])
      ? new Date(filters.window[side]).toISOString()
      : '';
  const [windowDraft, setWindowDraft] = useState({
    window: filters.window,
    start: windowValue('startMs'),
    end: windowValue('endMs'),
  });
  if (windowDraft.window !== filters.window)
    setWindowDraft({
      window: filters.window,
      start: windowValue('startMs'),
      end: windowValue('endMs'),
    });
  const onWindow = (side: 'startMs' | 'endMs', value: string) => {
    const next = {
      ...(filters.window ?? recording.coverage ?? { startMs: NaN, endMs: NaN }),
      [side]: recordedTimestampMs(value) ?? NaN,
    };
    setWindowDraft({ ...windowDraft, window: next, [side === 'startMs' ? 'start' : 'end']: value });
    onFilters({ ...filters, window: next });
  };
  const marker = (row: TimedSource, y: number, owners: readonly TimedSource[]) => {
    const activate = () => {
      if (owners.length > 1)
        setChooser({
          timestampMs: row.timestampMs,
          sourceIds: owners.map((owner) => owner.source.id),
        });
      else onSelect(row.source.id);
    };
    return (
      <circle
        key={row.source.id}
        cx={40 + (samplePosition(row.timestampMs, coverage!) ?? 0) * 720}
        cy={y}
        r={selectedTime === row.timestampMs ? 7 : 5}
        role="button"
        tabIndex={0}
        aria-label={
          (owners.length > 1 ? 'Choose sources at shared location for ' : 'Open recorded source ') +
          row.source.id
        }
        data-testid="timeline-marker"
        data-source-id={row.source.id}
        data-instant-selected={selectedTime === row.timestampMs}
        data-selected={selectedSourceId === row.source.id}
        data-related={view.relatedSourceIds.has(row.source.id)}
        onClick={activate}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            activate();
          }
        }}
      >
        <title>
          {row.source.id +
            ' · ' +
            row.source.timestamp +
            ' · ' +
            row.source.summary +
            (attribution(row) ? ' · ' + attribution(row) : '')}
        </title>
      </circle>
    );
  };
  const lane = (
    title: string,
    samples: readonly TimedSource[],
    metric?: { unit: string; samples: readonly import('@/lib/recorded-evidence').MetricSample[] },
  ) => {
    const domain = metric ? metricDomain(metric.samples) : null;
    const coordinates = samples.map((row) => {
      const value = metric && 'value' in row ? Number(row.value) : null;
      const scale = domain ? Math.max(Math.abs(domain[0]), Math.abs(domain[1]), 1) : 1;
      const scaled =
        value !== null && domain
          ? (value / scale - domain[0] / scale) / (domain[1] / scale - domain[0] / scale)
          : 0.5;
      return { row, y: 90 - scaled * 65 };
    });
    const instants = [...new Set(samples.map((row) => row.timestampMs))].sort((a, b) => a - b);
    const boundaries = coverage
      ? [...new Set([coverage.startMs, ...instants, coverage.endMs])].sort((a, b) => a - b)
      : [];
    const gaps = boundaries.slice(1).map((end, index) => ({ start: boundaries[index], end }));
    const utc = (timestamp: number) => new Date(timestamp).toISOString() + ' UTC';
    return (
      <div className="recorded-lane" key={title}>
        <h3>{title}</h3>
        {filters.request && samples.some((row) => attribution(row)) && (
          <p className="recorded-attribution">
            {filters.request.economicOrderId ? 'Economic order' : 'RFQ'} attribution is shown for
            each service metric/log in the table below; co-display does not establish a
            relationship.
            {samples.every((row) => !view.relatedSourceIds.has(row.source.id)) &&
              ' Not attributed to this ' +
                (filters.request.economicOrderId ? 'economic order.' : 'RFQ.')}
          </p>
        )}
        {metric && domain && (
          <p>
            Plot scale: {domain[0]} — {domain[1]} {metric.unit}. Each metric uses its own scale.
          </p>
        )}
        {coverage && (
          <p className="recorded-lane-boundaries">
            Display boundaries: {utc(coverage.startMs)} — {utc(coverage.endMs)}
          </p>
        )}
        {instants.length > 0 && (
          <p className="recorded-lane-coverage">
            Returned lane coverage in this display: {utc(instants[0])} —{' '}
            {utc(instants[instants.length - 1])} · {samples.length} discrete observations.
          </p>
        )}
        {gaps.length > 0 && (
          <details className="recorded-lane-gaps">
            <summary>{gaps.length} intervals without returned observations</summary>
            <p>
              Intervals are gaps in returned evidence; they do not establish health or continuity.
            </p>
            <ul>
              {gaps.map(({ start, end }) => (
                <li key={start}>
                  No returned observations between {utc(start)} and {utc(end)} (endpoints excluded).
                </li>
              ))}
            </ul>
          </details>
        )}
        {!samples.length ? (
          <p>No observations match this lane and display window.</p>
        ) : !coverage ? (
          <p>No returned-sample coverage is available.</p>
        ) : (
          <svg viewBox="0 0 800 130" role="group" aria-label={title + ' discrete observations'}>
            <line x1="40" y1="98" x2="760" y2="98" className="recorded-axis" />
            {coordinates.map(({ row, y }) =>
              marker(
                row,
                y,
                coordinates
                  .filter((point) => point.row.timestampMs === row.timestampMs && point.y === y)
                  .map((point) => point.row),
              ),
            )}
            <text x="40" y="122">
              {time(new Date(coverage.startMs).toISOString())} UTC
            </text>
            <text x="760" y="122" textAnchor="end">
              {time(new Date(coverage.endMs).toISOString())} UTC
            </text>
          </svg>
        )}
      </div>
    );
  };
  return (
    <Panel title="Linked evidence timeline" eyebrow="Discrete recorded observations">
      <div className="recorded-timeline">
        <p>
          Actual UTC time distance · no interpolation. Matching instants are highlighted across
          lanes; concurrence does not establish cause. Request-related sources use explicit returned
          identity fields.
        </p>
        <p className="recorded-filter-notice">
          Recorded assessment unchanged; filters do not rerun investigation.
        </p>
        <div className="recorded-evidence-columns">
          <aside
            className="recorded-evidence-controls"
            aria-label="Evidence display controls and request journey"
          >
            <div className="recorded-filter-grid">
              <label>
                Service filter
                <select
                  value={filters.service ?? ''}
                  onChange={(event) =>
                    onFilters({ ...filters, service: event.target.value || null })
                  }
                >
                  <option value="">All recorded services</option>
                  {services.map((service) => (
                    <option key={service}>{service}</option>
                  ))}
                </select>
              </label>
              <label>
                Metric and unit
                <select
                  value={filters.metricGroupKey ?? ''}
                  onChange={(event) =>
                    onFilters({ ...filters, metricGroupKey: event.target.value || null })
                  }
                >
                  <option value="">All metric groups · separate scales</option>
                  {recording.metrics.map((group) => (
                    <option key={group.key} value={group.key}>
                      {group.service + ' · ' + group.metric + ' · ' + group.unit}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Request filter
                <select
                  value={filters.request?.rfqId ?? ''}
                  onChange={(event) =>
                    onFilters({
                      ...filters,
                      request: event.target.value
                        ? { rfqId: event.target.value, economicOrderId: null }
                        : null,
                    })
                  }
                >
                  <option value="">All returned requests</option>
                  {recording.journeys
                    .filter((journey) => journey.rfqId !== null)
                    .map((journey) => (
                      <option key={journey.rfqId!}>{journey.rfqId}</option>
                    ))}
                </select>
              </label>
              <label>
                Economic order filter
                <select
                  value={filters.request?.economicOrderId ?? ''}
                  onChange={(event) => {
                    const choice = orderChoices.find((order) => order.id === event.target.value);
                    onFilters({
                      ...filters,
                      request: choice
                        ? { rfqId: choice.rfqId, economicOrderId: choice.id }
                        : filters.request
                          ? { ...filters.request, economicOrderId: null }
                          : null,
                    });
                  }}
                >
                  <option value="">All economic orders in request scope</option>
                  {orderChoices.map((order) => (
                    <option key={order.rfqId + ':' + order.id} value={order.id}>
                      {order.id}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                UTC start
                <input
                  type="text"
                  aria-label="UTC start"
                  placeholder="YYYY-MM-DDTHH:mm:ssZ"
                  value={windowDraft.start}
                  onChange={(event) => onWindow('startMs', event.target.value)}
                />
              </label>
              <label>
                UTC end
                <input
                  type="text"
                  aria-label="UTC end"
                  placeholder="YYYY-MM-DDTHH:mm:ssZ"
                  value={windowDraft.end}
                  onChange={(event) => onWindow('endMs', event.target.value)}
                />
              </label>
              <button
                className="button secondary"
                onClick={() => {
                  setChooser(null);
                  onFilters(defaultWorkspaceFilters(recording));
                }}
              >
                Reset display filters
              </button>
            </div>
            <div className="recorded-selected-journey">
              <h3>Returned request / order journey</h3>
              {filters.request ? (
                <>
                  <p>
                    {filters.request.rfqId}
                    {filters.request.economicOrderId ? ' · ' + filters.request.economicOrderId : ''}
                  </p>
                  <p>
                    Literal returned membership only. Retransmission preserves the economic order
                    identity.
                  </p>
                  <ol>
                    {view.business.map((row) => (
                      <li key={row.source.id}>
                        <Citation id={row.source.id} onEvidence={onSelect} />
                        <span>
                          {String(row.source.data.event_type ?? 'Event type unavailable')} ·{' '}
                          {row.source.timestamp} UTC
                        </span>
                      </li>
                    ))}
                  </ol>
                  {!view.business.length && (
                    <p>No timed business events match this selection and display window.</p>
                  )}
                </>
              ) : (
                <p>
                  Choose a returned RFQ or economic order to inspect its explicit journey. Service
                  metrics and logs remain separately inspectable.
                </p>
              )}
            </div>
          </aside>
          <div className="recorded-evidence-observations">
            {view.error && (
              <p className="error-banner" role="alert">
                {view.error}
              </p>
            )}
            {view.valid && (
              <>
                <div className="recorded-lanes">
                  {view.metrics.map((group) =>
                    lane(
                      group.service + ' · ' + group.metric + ' (' + group.unit + ')',
                      group.samples,
                      group,
                    ),
                  )}
                  {lane('Logs', view.logs)}
                  {lane('Business events', view.business)}
                </div>
                {!rows.length && (
                  <Empty title="No observations match the display filters">
                    Returned sources remain available; adjust the display filters.
                  </Empty>
                )}
                <div className="recorded-overlaps">
                  {[...instants]
                    .filter(([, sources]) => sources.length > 1)
                    .map(([instant, sources]) => (
                      <button
                        className="button secondary"
                        key={instant}
                        data-source-ids={sources.map((row) => row.source.id).join('|')}
                        onClick={() =>
                          setChooser({
                            timestampMs: instant,
                            sourceIds: sources.map((row) => row.source.id),
                          })
                        }
                      >
                        Choose overlapping sources · {time(new Date(instant).toISOString())} UTC (
                        {sources.length})
                      </button>
                    ))}
                </div>
                {chooser !== null &&
                  chooser.sourceIds.every((id) => rows.some((row) => row.source.id === id)) && (
                    <div
                      ref={chooserRef}
                      className="recorded-overlap-list"
                      role="group"
                      aria-label="Overlapping recorded sources"
                    >
                      <p>
                        Choose an exact returned source at{' '}
                        {new Date(chooser.timestampMs).toISOString()} · UTC. Tied timestamps do not
                        establish ordering.
                      </p>
                      {chooser.sourceIds.map((id) => (
                        <Citation key={id} id={id} onEvidence={onSelect} />
                      ))}
                    </div>
                  )}
              </>
            )}
          </div>
        </div>
        {view.valid && (
          <div className="recorded-table-scroll">
            <table aria-label="Recorded observations">
              <caption>Recorded observations · same sources as plotted lanes</caption>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>UTC timestamp</th>
                  <th>Service / kind</th>
                  <th>Observed value / unit</th>
                  <th>Summary</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.source.id}
                    data-source-id={row.source.id}
                    data-timestamp={row.timestampMs}
                    data-selected={selectedSourceId === row.source.id}
                    data-instant-selected={selectedTime === row.timestampMs}
                    data-related={view.relatedSourceIds.has(row.source.id)}
                  >
                    <td>
                      <Citation id={row.source.id} onEvidence={onSelect} />
                    </td>
                    <td>
                      <time dateTime={row.source.timestamp}>{row.source.timestamp} UTC</time>
                    </td>
                    <td>
                      {row.source.service} / {row.source.kind}
                    </td>
                    <td>
                      {row.source.kind === 'metric'
                        ? String(row.source.data.value) + ' ' + String(row.source.data.unit)
                        : '—'}
                    </td>
                    <td>
                      {row.source.summary}
                      {attribution(row) && (
                        <p className="recorded-attribution">{attribution(row)}</p>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {recording.warnings.map((warning) => (
          <p className="recorded-warning" key={warning}>
            {warning}
          </p>
        ))}
        <div className="recorded-context" data-testid="recorded-context">
          <h3>Context and unplottable sources</h3>
          <p>
            Context is outside the plotted observation lanes. Missing references were not returned
            and cannot be resolved from current session evidence.
          </p>
          {context.map((source) => (
            <div
              key={source.id}
              data-source-id={source.id}
              data-selected={selectedSourceId === source.id}
            >
              <Citation id={source.id} onEvidence={onSelect} />
              <span>
                {source.timestamp} · {source.summary}
              </span>
            </div>
          ))}
          <h3>Recorded incident context annotations</h3>
          <ol className="recorded-context-annotations">
            {recording.contextAnnotations.map((annotation, index) => (
              <li key={index}>
                <p>
                  <strong>{annotation.label ?? 'Annotation label unavailable'}</strong> ·
                  {annotation.timestampMs === null ? (
                    <span>
                      {annotation.timestamp ?? 'Timestamp unavailable'} · Invalid recorded
                      annotation timestamp; chronology unavailable
                    </span>
                  ) : (
                    <time dateTime={annotation.timestamp!}>{annotation.timestamp} UTC</time>
                  )}
                  {annotation.timestampMs !== null &&
                    recording.coverage &&
                    (annotation.timestampMs < recording.coverage.startMs ||
                      annotation.timestampMs > recording.coverage.endMs) && (
                      <span> · Outside returned-sample coverage</span>
                    )}
                </p>
                <div className="recorded-context-references">
                  {annotation.evidenceIds.map((id, referenceIndex) =>
                    recording.sources.has(id) ? (
                      <Citation key={referenceIndex} id={id} onEvidence={onSelect} />
                    ) : (
                      <span key={referenceIndex}>
                        <code>{id}</code> · Referenced in context; source not returned
                      </span>
                    ),
                  )}
                </div>
                {!annotation.evidenceIds.length && (
                  <p>No source references returned for this annotation.</p>
                )}
              </li>
            ))}
          </ol>
          <div data-testid="missing-recorded-context">
            {recording.contextReferences.map((id) => (
              <p key={id}>
                <code>{id}</code> · not returned in this recording
              </p>
            ))}
          </div>
        </div>
      </div>
    </Panel>
  );
}
