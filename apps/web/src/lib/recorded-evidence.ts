import type { Evidence, Investigation } from './types';

export type RecordingIdentity = { incidentId: string; sourceSha256: string; exportedAt: string };
export type Coverage = { startMs: number; endMs: number };
export type TimedSource = { source: Evidence; timestampMs: number };
export type MetricSample = TimedSource & { metric: string; unit: string; value: number };
export type MetricGroup = {
  key: string;
  service: string;
  metric: string;
  unit: string;
  samples: readonly MetricSample[];
};
export type RequestSelection = { rfqId: string; economicOrderId: string | null };
export type RequestJourney = { rfqId: string | null; events: readonly Evidence[] };
export type WorkspaceFilters = {
  service: string | null;
  metricGroupKey: string | null;
  request: RequestSelection | null;
  window: Coverage | null;
};
export type RecordedRecording = {
  investigation: Readonly<Investigation>;
  incident: Evidence;
  identity: RecordingIdentity | null;
  sources: ReadonlyMap<string, Evidence>;
  metrics: readonly MetricGroup[];
  logs: readonly TimedSource[];
  journeys: readonly RequestJourney[];
  coverage: Coverage | null;
  warnings: readonly string[];
  contextReferences: readonly string[];
};
export type RecordedProjection =
  | { kind: 'legacy' }
  | { kind: 'blocked'; reason: string }
  | { kind: 'ready'; recording: RecordedRecording };
export type TimelineView = {
  valid: boolean;
  error: string | null;
  metrics: readonly MetricGroup[];
  logs: readonly TimedSource[];
  business: readonly TimedSource[];
  relatedSourceIds: ReadonlySet<string>;
};

function literal(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value : null;
}
function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
export function recordedTimestampMs(value: string): number | null {
  // Require an explicit timezone; local browser timezone must not invent UTC.
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value))
    return null;
  const calendar = Date.parse(value.slice(0, 10) + 'T00:00:00Z');
  if (
    !Number.isFinite(calendar) ||
    new Date(calendar).toISOString().slice(0, 10) !== value.slice(0, 10) ||
    Number(value.slice(11, 13)) > 23 ||
    Number(value.slice(14, 16)) > 59 ||
    Number(value.slice(17, 19)) > 59
  )
    return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}
function lexical(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}
function timedOrder(a: TimedSource, b: TimedSource): number {
  return a.timestampMs - b.timestampMs || lexical(a.source.id, b.source.id);
}
function eventOrder(a: Evidence, b: Evidence): number {
  const at = recordedTimestampMs(a.timestamp),
    bt = recordedTimestampMs(b.timestamp);
  if (at === null && bt !== null) return 1;
  if (bt === null && at !== null) return -1;
  return (at !== null && bt !== null ? at - bt : 0) || lexical(a.id, b.id);
}
export function recordedEconomicOrderId(source: Evidence): string | null {
  return literal(source.data.economic_order_id) ?? literal(source.data.order_id);
}
export function groupRecordedJourneys(evidence: readonly Evidence[]): readonly RequestJourney[] {
  const groups = new Map<string | null, Evidence[]>();
  for (const source of evidence) {
    if (source.kind !== 'business_event') continue;
    const rfqId = literal(source.data.rfq_id);
    const events = groups.get(rfqId) ?? [];
    events.push(source);
    groups.set(rfqId, events);
  }
  // Invalid-time events remain inspectable, after timed events, without chronology.
  return [...groups]
    .sort(([a], [b]) => (a === null ? (b === null ? 0 : 1) : b === null ? -1 : lexical(a, b)))
    .map(([rfqId, events]) => ({ rfqId, events: [...events].sort(eventOrder) }));
}
export function projectRecording(
  investigation: Investigation,
  selectedIncidentId: string,
): RecordedProjection {
  if (investigation.mode !== 'REPLAY' || !investigation.provenance?.showcase)
    return { kind: 'legacy' };
  const blocked = (reason: string): RecordedProjection => ({ kind: 'blocked', reason });
  if (investigation.incident_id !== selectedIncidentId)
    return blocked('The active recording does not match the selected incident.');
  if (!Array.isArray(investigation.evidence))
    return blocked('Returned evidence is missing from this recording.');
  const sources = new Map<string, Evidence>();
  for (const source of investigation.evidence) {
    if (
      !object(source) ||
      !literal(source.id) ||
      typeof source.kind !== 'string' ||
      typeof source.service !== 'string' ||
      typeof source.timestamp !== 'string' ||
      typeof source.summary !== 'string' ||
      !object(source.data)
    )
      return blocked('A returned source is malformed.');
    if (sources.has(source.id))
      return blocked(
        'Duplicate returned source ID: ' + source.id + '. Source identity is ambiguous.',
      );
    sources.set(source.id, source);
  }
  const incident = sources.get(selectedIncidentId);
  if (!incident || incident.kind !== 'incident')
    return blocked('The matching recorded incident source was not returned.');
  if (incident.data.incident_id !== selectedIncidentId)
    return blocked('The recorded incident identity does not match the selected incident.');
  if (
    investigation.evidence.some(
      (source) => source.kind === 'incident' && source.id !== selectedIncidentId,
    )
  )
    return blocked('The recording contains a different incident source.');
  const metadata = investigation.provenance.showcase;
  const sourceSha256 = literal(metadata.source_sha256),
    exportedAt = literal(metadata.exported_at);
  const identity =
    sourceSha256 && exportedAt
      ? { incidentId: selectedIncidentId, sourceSha256, exportedAt }
      : null;
  const warnings: string[] = [];
  const groups = new Map<
    string,
    { key: string; service: string; metric: string; unit: string; samples: MetricSample[] }
  >();
  const logs: TimedSource[] = [];
  const times: number[] = [];
  for (const source of sources.values()) {
    if (!['metric', 'log', 'business_event'].includes(source.kind)) continue;
    const timestampMs = recordedTimestampMs(source.timestamp);
    if (timestampMs === null) {
      warnings.push('Cannot plot this recorded row ' + source.id + ': invalid timestamp.');
      continue;
    }
    if (source.kind === 'metric') {
      const metric = literal(source.data.metric),
        unit = literal(source.data.unit),
        value = source.data.value;
      if (!metric || !unit || typeof value !== 'number' || !Number.isFinite(value)) {
        warnings.push(
          'Cannot plot this recorded row ' +
            source.id +
            ': metric name, unit or finite numeric value unavailable.',
        );
        continue;
      }
      const key = JSON.stringify([source.service, metric, unit]);
      const group = groups.get(key) ?? { key, service: source.service, metric, unit, samples: [] };
      group.samples.push({ source, timestampMs, metric, unit, value });
      groups.set(key, group);
    } else if (source.kind === 'log') logs.push({ source, timestampMs });
    times.push(timestampMs);
  }
  const metrics = [...groups.values()]
    .sort(
      (a, b) =>
        lexical(a.service, b.service) || lexical(a.metric, b.metric) || lexical(a.unit, b.unit),
    )
    .map((group) => ({ ...group, samples: [...group.samples].sort(timedOrder) }));
  const contextReferences = new Set<string>();
  // Only returned context annotations. They do not become extra source objects.
  if (Array.isArray(incident.data.timeline))
    for (const annotation of incident.data.timeline) {
      if (!object(annotation) || !Array.isArray(annotation.evidence_ids)) continue;
      for (const id of annotation.evidence_ids)
        if (literal(id) && !sources.has(id as string)) contextReferences.add(id as string);
    }
  return {
    kind: 'ready',
    recording: {
      investigation,
      incident,
      identity,
      sources,
      metrics,
      logs: [...logs].sort(timedOrder),
      journeys: groupRecordedJourneys(investigation.evidence),
      coverage: times.length ? { startMs: Math.min(...times), endMs: Math.max(...times) } : null,
      warnings,
      contextReferences: [...contextReferences],
    },
  };
}
export function defaultWorkspaceFilters(recording: RecordedRecording): WorkspaceFilters {
  return {
    service: null,
    metricGroupKey: recording.metrics[0]?.key ?? null,
    request: null,
    window: recording.coverage ? { ...recording.coverage } : null,
  };
}
function validCoverage(coverage: Coverage): boolean {
  return (
    Number.isFinite(coverage.startMs) &&
    Number.isFinite(coverage.endMs) &&
    coverage.startMs <= coverage.endMs
  );
}
function windowError(recording: RecordedRecording, window: Coverage | null): string | null {
  if (!window) return null;
  if (!validCoverage(window)) return 'Enter a valid UTC window with start at or before end.';
  if (
    !recording.coverage ||
    window.startMs < recording.coverage.startMs ||
    window.endMs > recording.coverage.endMs
  )
    return 'The display window must remain within returned-sample coverage.';
  return null;
}
function selectedEvents(
  recording: RecordedRecording,
  request: RequestSelection | null,
): readonly Evidence[] {
  return recording.journeys
    .filter((journey) => !request || journey.rfqId === request.rfqId)
    .flatMap((journey) =>
      journey.events.filter(
        (source) =>
          !request?.economicOrderId || recordedEconomicOrderId(source) === request.economicOrderId,
      ),
    );
}
function relatedSources(
  recording: RecordedRecording,
  request: RequestSelection | null,
): ReadonlySet<string> {
  if (!request) return new Set();
  const events = selectedEvents(recording, request);
  const rfqs = new Set<string>(),
    orders = new Set<string>(),
    traces = new Set<string>();
  for (const event of events) {
    const rfq = literal(event.data.rfq_id),
      trace = literal(event.data.trace_id);
    if (rfq) rfqs.add(rfq);
    if (trace) traces.add(trace);
    for (const field of ['order_id', 'economic_order_id']) {
      const order = literal(event.data[field]);
      if (order) orders.add(order);
    }
  }
  const ids = new Set(events.map((event) => event.id));
  for (const source of recording.sources.values()) {
    if (source.kind !== 'metric' && source.kind !== 'log') continue;
    const rfq = literal(source.data.rfq_id),
      trace = literal(source.data.trace_id);
    const order = literal(source.data.order_id),
      economic = literal(source.data.economic_order_id);
    if (
      (rfq && rfqs.has(rfq)) ||
      (trace && traces.has(trace)) ||
      (order && orders.has(order)) ||
      (economic && orders.has(economic))
    )
      ids.add(source.id);
  }
  return ids;
}
export function filterRecordedEvidence(
  recording: RecordedRecording,
  filters: WorkspaceFilters,
): TimelineView {
  const error = windowError(recording, filters.window);
  if (error)
    return {
      valid: false,
      error,
      metrics: [],
      logs: [],
      business: [],
      relatedSourceIds: new Set(),
    };
  const inWindow = (row: TimedSource) =>
    !filters.window ||
    (row.timestampMs >= filters.window.startMs && row.timestampMs <= filters.window.endMs);
  const matchesService = (service: string) =>
    filters.service === null || service === filters.service;
  const metrics = recording.metrics
    .filter(
      (group) =>
        matchesService(group.service) &&
        (filters.metricGroupKey === null || group.key === filters.metricGroupKey),
    )
    .map((group) => ({ ...group, samples: group.samples.filter(inWindow) }));
  const logs = recording.logs.filter((row) => matchesService(row.source.service) && inWindow(row));
  const business = selectedEvents(recording, filters.request)
    .flatMap((source) => {
      const timestampMs = recordedTimestampMs(source.timestamp);
      return timestampMs === null ? [] : [{ source, timestampMs }];
    })
    .filter(inWindow)
    .sort(timedOrder);
  return {
    valid: true,
    error: null,
    metrics,
    logs,
    business,
    relatedSourceIds: relatedSources(recording, filters.request),
  };
}
export function revealRecordedSource(
  recording: RecordedRecording,
  filters: WorkspaceFilters,
  id: string,
): WorkspaceFilters {
  const source = recording.sources.get(id);
  if (!source) return { ...filters };
  const result: WorkspaceFilters = { ...filters };
  if (source.kind === 'metric') {
    const group = recording.metrics.find((candidate) =>
      candidate.samples.some((sample) => sample.source.id === id),
    );
    if (group) {
      result.service = source.service;
      result.metricGroupKey = group.key;
    }
  } else if (source.kind === 'log') result.service = source.service;
  else if (
    source.kind === 'business_event' &&
    !selectedEvents(recording, filters.request).some((event) => event.id === id)
  )
    result.request = null;
  const timestampMs = recordedTimestampMs(source.timestamp);
  if (windowError(recording, result.window))
    result.window = recording.coverage ? { ...recording.coverage } : null;
  if (
    timestampMs !== null &&
    result.window &&
    recording.coverage &&
    timestampMs >= recording.coverage.startMs &&
    timestampMs <= recording.coverage.endMs
  ) {
    result.window = {
      startMs: Math.min(result.window.startMs, timestampMs),
      endMs: Math.max(result.window.endMs, timestampMs),
    };
  }
  return result;
}
export function samplePosition(timestampMs: number, coverage: Coverage): number | null {
  if (
    !Number.isFinite(timestampMs) ||
    !validCoverage(coverage) ||
    timestampMs < coverage.startMs ||
    timestampMs > coverage.endMs
  )
    return null;
  return coverage.startMs === coverage.endMs
    ? 0.5
    : (timestampMs - coverage.startMs) / (coverage.endMs - coverage.startMs);
}
export function metricDomain(samples: readonly MetricSample[]): readonly [number, number] | null {
  const values = samples.map((sample) => sample.value).filter(Number.isFinite);
  if (!values.length) return null;
  const min = Math.min(...values),
    max = Math.max(...values);
  if (min !== max) return [min, max];
  const padding = Math.max(Math.abs(min) * 0.05, 1);
  return [Math.max(-Number.MAX_VALUE, min - padding), Math.min(Number.MAX_VALUE, max + padding)];
}
export function countRecordedRfqs(journeys: readonly RequestJourney[]): number {
  return new Set(journeys.flatMap((journey) => (journey.rfqId === null ? [] : [journey.rfqId])))
    .size;
}
export function countRecordedEventRfqs(
  journeys: readonly RequestJourney[],
  eventType: string,
): number {
  return new Set(
    journeys.flatMap((journey) =>
      journey.rfqId !== null && journey.events.some((event) => event.data.event_type === eventType)
        ? [journey.rfqId]
        : [],
    ),
  ).size;
}
// Keep decimal strings exact. Converting requested par to a JS number would lose
// monetary precision and would invite financial calculations outside this demo.
export function formatRecordedDecimal(value: string): string {
  const [integer, fraction] = value.split('.');
  return `${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}${fraction === undefined ? '' : `.${fraction}`}`;
}
