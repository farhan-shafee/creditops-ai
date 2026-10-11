import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { BusinessImpactPanel } from '../src/components/business-impact';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { Evidence, Investigation } from '../src/lib/types';
import {
  projectRecording,
  defaultWorkspaceFilters,
  filterRecordedEvidence,
  revealRecordedSource,
  samplePosition,
  metricDomain,
  formatRecordedDecimal,
  groupRecordedJourneys,
  countRecordedRfqs,
  countRecordedEventRfqs,
  recordedEconomicOrderId,
} from '../src/lib/recorded-evidence';
import { loadRecordedFixture, loadRecordedManifest } from './recorded-fixtures';
function ready(value: Investigation) {
  const projection = projectRecording(value, value.incident_id);
  assert.equal(projection.kind, 'ready');
  if (projection.kind !== 'ready') throw Error('Recording unavailable');
  return projection.recording;
}
function row(
  id: string,
  kind: string,
  data: Record<string, unknown>,
  timestamp = '2026-10-09T14:00:00Z',
  service = 'quote-service',
): Evidence {
  return { id, kind, data, timestamp, service, summary: id };
}
function variant(rows: Evidence[]): Investigation {
  const value = loadRecordedFixture('INC-DEMO-001');
  value.evidence = [value.evidence[0], ...rows];
  return value;
}
// Catch global indexes, weak identity guards, and nested-source enrichment.
test('recording_identity_is_scoped_and_ambiguous_ids_block', () => {
  const a = loadRecordedFixture('INC-DEMO-001'),
    b = loadRecordedFixture('INC-DEMO-002');
  const ar = ready(a),
    br = ready(b);
  assert.equal(ar.sources.get('TOPOLOGY-001'), a.evidence[1]);
  assert.equal(br.sources.get('TOPOLOGY-001'), b.evidence[1]);
  assert.notEqual(ar.sources.get('TOPOLOGY-001'), br.sources.get('TOPOLOGY-001'));
  assert.deepEqual(ar.identity, {
    incidentId: a.incident_id,
    sourceSha256: a.provenance!.showcase!.source_sha256,
    exportedAt: a.provenance!.showcase!.exported_at,
  });
  assert.equal(projectRecording(a, b.incident_id).kind, 'blocked');
  assert.equal(
    projectRecording({ ...a, evidence: a.evidence.slice(1) }, a.incident_id).kind,
    'blocked',
  );
  assert.equal(
    projectRecording({ ...a, evidence: [...a.evidence, a.evidence[1]] }, a.incident_id).kind,
    'blocked',
  );
  assert.equal(projectRecording({ ...a, mode: 'MCP_DEMO' }, a.incident_id).kind, 'legacy');
  assert.equal(projectRecording({ ...a, provenance: {} }, a.incident_id).kind, 'legacy');
  const nested = structuredClone(a);
  nested.evidence[0].data.timeline = [
    { evidence_ids: ['NESTED-NOT-RETURNED'], data: { id: 'NESTED-ID' } },
  ];
  const scoped = ready(nested);
  assert.deepEqual(scoped.contextReferences, ['NESTED-NOT-RETURNED']);
  assert.equal(scoped.sources.has('NESTED-NOT-RETURNED'), false);
  assert.equal(scoped.sources.has('NESTED-ID'), false);
  delete nested.provenance!.showcase!.source_sha256;
  assert.equal(ready(nested).identity, null);
  assert.equal(ready(nested).sources.size, a.evidence.length);
});
// Catch evenly spaced charts, merged ties, coerced values, or healthy empty lanes.
test('discrete_samples_preserve_time_value_unit_and_ties', () => {
  const value = variant([
    row('M-C', 'metric', { metric: 'count', unit: 'count', value: -2.25 }, '2026-10-09T14:05:00Z'),
    row('M-B', 'metric', { metric: 'count', unit: 'count', value: 1.5 }, '2026-10-09T14:01:00Z'),
    row('M-A', 'metric', { metric: 'count', unit: 'count', value: -2.25 }, '2026-10-09T14:01:00Z'),
    row('M-D', 'metric', { metric: 'count', unit: 'count', value: 1.5 }, '2026-10-09T14:01:00Z'),
    row('M-UNIT', 'metric', { metric: 'count', unit: 'ms', value: 1.5 }, '2026-10-09T14:01:00Z'),
    row('M-BAD-TIME', 'metric', { metric: 'count', unit: 'count', value: 7 }, 'invalid'),
    row('M-INFINITY', 'metric', { metric: 'count', unit: 'count', value: Infinity }),
    row('M-STRING', 'metric', { metric: 'count', unit: 'count', value: '2' }),
    row('BAD-BUSINESS', 'business_event', { event_type: 'RFQ_EXPIRED', rfq_id: 'R' }, 'invalid'),
    row('L-Z', 'log', {}),
  ]);
  const before = structuredClone(value),
    recording = ready(value),
    group = recording.metrics.find((g) => g.unit === 'count')!;
  assert.deepEqual(
    group.samples.map((s) => [s.source.id, s.value]),
    [
      ['M-A', -2.25],
      ['M-B', 1.5],
      ['M-D', 1.5],
      ['M-C', -2.25],
    ],
  );
  assert.equal(group.samples[0].timestampMs, Date.parse('2026-10-09T14:01:00Z'));
  assert.equal(recording.metrics.length, 2);
  assert.equal(recording.sources.has('M-INFINITY'), true);
  assert.equal(recording.sources.has('M-BAD-TIME'), true);
  assert.equal(recording.journeys[0].events[0].id, 'BAD-BUSINESS');
  for (const id of ['M-INFINITY', 'M-BAD-TIME', 'M-STRING', 'BAD-BUSINESS'])
    assert.ok(recording.warnings.some((w) => w.includes(id)));
  assert.deepEqual(recording.coverage, {
    startMs: Date.parse('2026-10-09T14:00:00Z'),
    endMs: Date.parse('2026-10-09T14:05:00Z'),
  });
  assert.equal(samplePosition(60_000, { startMs: 0, endMs: 300_000 }), 0.2);
  assert.equal(samplePosition(0, { startMs: 0, endMs: 0 }), 0.5);
  assert.equal(samplePosition(-1, { startMs: 0, endMs: 300_000 }), null);
  assert.equal(samplePosition(1, { startMs: 2, endMs: 1 }), null);
  assert.equal(samplePosition(NaN, { startMs: 0, endMs: 1 }), null);
  assert.deepEqual(metricDomain(group.samples), [-2.25, 1.5]);
  const constant = metricDomain(group.samples.filter((s) => s.value === -2.25))!;
  assert.ok(constant[0] < -2.25 && constant[1] > -2.25);
  assert.equal(metricDomain([]), null);
  assert.deepEqual(ready(variant([])).metrics, []);
  assert.equal(ready(variant([])).coverage, null);
  assert.equal(formatRecordedDecimal('9007199254740993.25'), '9,007,199,254,740,993.25');
  assert.equal(formatRecordedDecimal('-12345.00'), '-12,345.00');
  assert.deepEqual(value, before);
});
// Catch guessed relationships and economic-order duplication on retransmission.
test('request_relationships_require_exact_returned_fields', () => {
  const recording = ready(
    variant([
      row('B-1', 'business_event', {
        rfq_id: 'RFQ-1',
        order_id: 'ORDER-1',
        economic_order_id: 'ECON-1',
        trace_id: 'TRACE-1',
        event_type: 'ACK_UNCERTAIN',
      }),
      row('B-2', 'business_event', {
        rfq_id: 'RFQ-1',
        order_id: 'ORDER-1-RETRY',
        economic_order_id: 'ECON-1',
        trace_id: 'TRACE-1',
        retransmission: true,
      }),
      row('L-RFQ', 'log', { rfq_id: 'RFQ-1' }),
      row('L-ORDER', 'log', { order_id: 'ORDER-1' }),
      row('L-TRACE', 'log', { trace_id: 'TRACE-1' }),
      row('L-PREFIX', 'log', { rfq_id: 'RFQ-1-SIMILAR', trace_id: 'TRACE-1-SIMILAR' }),
      row('L-NESTED', 'log', { context: { rfq_id: 'RFQ-1' } }),
      row('M-UNLINKED', 'metric', { metric: 'latency', unit: 'ms', value: 3 }),
      row('M-LINKED', 'metric', { metric: 'latency', unit: 'ms', value: 4, trace_id: 'TRACE-1' }),
      row('B-UNKNOWN', 'business_event', { rfq_id: '', event_type: 'ACK_UNCERTAIN' }),
    ]),
  );
  const view = filterRecordedEvidence(recording, {
    ...defaultWorkspaceFilters(recording),
    request: { rfqId: 'RFQ-1', economicOrderId: 'ECON-1' },
  });
  assert.deepEqual(
    view.business.map((r) => r.source.id),
    ['B-1', 'B-2'],
  );
  assert.deepEqual([...view.relatedSourceIds].sort(), [
    'B-1',
    'B-2',
    'L-ORDER',
    'L-RFQ',
    'L-TRACE',
    'M-LINKED',
  ]);
  assert.equal(view.metrics[0].samples.length, 2);
  assert.equal(view.logs.length, 5);
  assert.deepEqual(
    recording.journeys.map((j) => j.rfqId),
    ['RFQ-1', null],
  );
  assert.equal(countRecordedRfqs(recording.journeys), 1);
  assert.equal(countRecordedEventRfqs(recording.journeys, 'ACK_UNCERTAIN'), 1);
  assert.deepEqual(recording.journeys[0].events.map(recordedEconomicOrderId), ['ECON-1', 'ECON-1']);
  const real = ready(loadRecordedFixture('INC-DEMO-002'));
  const realView = filterRecordedEvidence(real, {
    ...defaultWorkspaceFilters(real),
    request: { rfqId: 'RFQ-DEMO-002-001', economicOrderId: null },
  });
  for (const id of ['LOG-002-001', 'LOG-002-002', 'LOG-002-003'])
    assert.equal(realView.relatedSourceIds.has(id), false);
});
// Catch mutation, cross-lane filtering, invalid windows and cutoff stretching.
test('filters_are_display_only_and_do_not_mutate_sources', () => {
  const value = variant([
    row('M-Q', 'metric', { metric: 'cpu', unit: '%', value: 1 }),
    row(
      'M-E',
      'metric',
      { metric: 'cpu', unit: '%', value: 2 },
      '2026-10-09T14:05:00Z',
      'execution-service',
    ),
    row('L-E', 'log', {}, '2026-10-09T14:05:00Z', 'execution-service'),
    row('L-Q', 'log', {}),
    row('B-E', 'business_event', { rfq_id: 'R-E' }, '2026-10-09T14:05:00Z', 'execution-service'),
    row('B-Q', 'business_event', { rfq_id: 'R-Q' }),
  ]);
  const before = structuredClone(value),
    recording = ready(value),
    defaults = defaultWorkspaceFilters(recording);
  assert.equal(defaults.service, null);
  assert.equal(defaults.request, null);
  assert.equal(defaults.metricGroupKey, recording.metrics[0].key);
  assert.equal(recording.metrics[0].service, 'execution-service');
  assert.deepEqual(defaults.window, recording.coverage);
  assert.equal(recording.coverage!.endMs, Date.parse('2026-10-09T14:05:00Z'));
  const all = { ...defaults, metricGroupKey: null },
    service = filterRecordedEvidence(recording, { ...all, service: 'quote-service' });
  assert.deepEqual(
    service.metrics.flatMap((g) => g.samples.map((s) => s.source.id)),
    ['M-Q'],
  );
  assert.deepEqual(
    service.logs.map((r) => r.source.id),
    ['L-Q'],
  );
  assert.equal(service.business.length, 2);
  const metricOnly = filterRecordedEvidence(recording, defaults);
  assert.equal(metricOnly.logs.length, 2);
  assert.equal(metricOnly.business.length, 2);
  const requestOnly = filterRecordedEvidence(recording, {
    ...all,
    request: { rfqId: 'R-Q', economicOrderId: null },
  });
  assert.equal(requestOnly.metrics.length, 2);
  assert.equal(requestOnly.logs.length, 2);
  assert.deepEqual(
    requestOnly.business.map((r) => r.source.id),
    ['B-Q'],
  );
  for (const window of [
    { startMs: 2, endMs: 1 },
    { startMs: NaN, endMs: 4 },
    { startMs: recording.coverage!.startMs - 1, endMs: recording.coverage!.endMs },
  ]) {
    const invalid = filterRecordedEvidence(recording, { ...all, window });
    assert.equal(invalid.valid, false);
    assert.ok(invalid.error);
    assert.equal(invalid.metrics.length, 0);
  }
  const hidden = {
    ...defaults,
    service: 'execution-service',
    request: { rfqId: 'R-E', economicOrderId: null },
    window: { startMs: recording.coverage!.endMs, endMs: recording.coverage!.endMs },
  };
  const revealed = revealRecordedSource(recording, hidden, 'M-Q');
  assert.ok(
    filterRecordedEvidence(recording, revealed).metrics.some((g) =>
      g.samples.some((s) => s.source.id === 'M-Q'),
    ),
  );
  assert.equal(revealed.request?.rfqId, 'R-E');
  assert.ok(
    filterRecordedEvidence(recording, revealRecordedSource(recording, hidden, 'B-Q')).business.some(
      (s) => s.source.id === 'B-Q',
    ),
  );
  assert.deepEqual(revealRecordedSource(recording, hidden, 'NOT-RETURNED'), hidden);
  assert.deepEqual(value, before);
});
test('packaged_recordings_match_manifest_and_returned_rows_without_enrichment', () => {
  const manifest = loadRecordedManifest();
  for (const [id, expected] of [
    ['INC-DEMO-001', 67],
    ['INC-DEMO-002', 71],
    ['INC-DEMO-003', 65],
  ] as const) {
    const value = loadRecordedFixture(id),
      before = structuredClone(value),
      recording = ready(value);
    const metadata = manifest.selected_recordings.find(
      (r: { incident_id: string }) => r.incident_id === id,
    );
    assert.equal(recording.sources.size, expected);
    assert.equal(
      recording.metrics.reduce((n, g) => n + g.samples.length, 0),
      50,
    );
    assert.deepEqual(recording.coverage, {
      startMs: Date.parse(metadata.sample_start),
      endMs: Date.parse(metadata.sample_end),
    });
    assert.equal(recording.identity!.sourceSha256, metadata.source_sha256);
    for (const group of recording.metrics)
      for (const sample of group.samples) {
        assert.equal(
          sample.source,
          value.evidence.find((r) => r.id === sample.source.id),
        );
        assert.equal(sample.value, sample.source.data.value);
        assert.equal(sample.unit, sample.source.data.unit);
        assert.equal(sample.metric, sample.source.data.metric);
        assert.equal(sample.timestampMs, Date.parse(sample.source.timestamp));
      }
    assert.equal(countRecordedRfqs(groupRecordedJourneys(value.evidence)), 2);
    assert.deepEqual(value, before);
  }
});
// Catch Date.parse normalizing an impossible calendar date into a new observation.
test('impossible_recorded_times_are_inspectable_without_invented_chronology', () => {
  const recording = ready(
    variant([
      row(
        'ROLLED-METRIC',
        'metric',
        { metric: 'cpu', unit: '%', value: 3 },
        '2026-02-30T14:00:00Z',
      ),
      row('ROLLED-LOG', 'log', {}, '2026-10-09T24:00:00Z'),
      row(
        'UNTIMED-EVENT',
        'business_event',
        { rfq_id: 'R', event_type: 'RFQ_EXPIRED' },
        '2026-02-30T14:00:00Z',
      ),
    ]),
  );
  assert.deepEqual(recording.metrics, []);
  assert.deepEqual(recording.logs, []);
  assert.equal(recording.coverage, null);
  assert.equal(recording.sources.size, 4);
  assert.equal(countRecordedEventRfqs(recording.journeys, 'RFQ_EXPIRED'), 1);
  assert.equal(recording.warnings.length, 3);
});

// Catch an unknown-display label colliding with a literal returned RFQ identity.
test('recorded_business_unknown_identity_does_not_replace_a_literal_named_request', () => {
  const investigation = variant([
    row('B-KNOWN', 'business_event', {
      rfq_id: 'Request identity not recorded',
      event_type: 'RFQ_EXPIRED',
    }),
    row('B-UNKNOWN', 'business_event', { event_type: 'RFQ_EXPIRED' }),
  ]);
  const markup = renderToStaticMarkup(
    <BusinessImpactPanel
      incidentId={investigation.incident_id}
      investigation={investigation}
      onEvidence={() => {}}
    />,
  );
  assert.equal((markup.match(/data-testid="request-journey"/g) ?? []).length, 2);
  assert.match(markup, /B-KNOWN/);
  assert.match(markup, /B-UNKNOWN/);
});
// Untimed rows remain observations, never an inferred final request state or UTC instant.
test('recorded_business_untimed_events_show_uncertain_status_and_unplottable_time', () => {
  for (const timestamp of ['2026-02-30T14:00:00Z', '2026-10-09T24:00:00Z', 'invalid']) {
    const investigation = variant([
      row('B-TIMED', 'business_event', { rfq_id: 'R', event_type: 'RFQ_REQUESTED' }),
      row('B-UNTIMED', 'business_event', { rfq_id: 'R', event_type: 'RFQ_EXPIRED' }, timestamp),
    ]);
    const before = structuredClone(investigation);
    const markup = renderToStaticMarkup(
      <BusinessImpactPanel
        incidentId={investigation.incident_id}
        investigation={investigation}
        onEvidence={() => {}}
      />,
    );
    const summary = markup.match(
      /<details[^>]*data-testid="request-journey"[^>]*><summary>([\s\S]*?)<\/summary>/,
    )![1];
    assert.match(summary, /Chronology uncertain/);
    assert.equal(summary.includes('RFQ EXPIRED'), false);
    const untimed = [...markup.matchAll(/<li>([\s\S]*?)<\/li>/g)]
      .map((match) => match[1])
      .find((content) => content.includes('B-UNTIMED'))!;
    assert.ok(untimed);
    assert.equal(untimed.includes('<time'), false);
    assert.equal(untimed.includes('<span>UTC</span>'), false);
    assert.match(untimed, /Cannot plot this recorded row/);
    assert.match(untimed, /Invalid recorded timestamp/);
    assert.ok(untimed.includes(timestamp));
    assert.equal(markup.includes('dateTime="' + timestamp + '"'), false);
    assert.match(markup, /dateTime="2026-10-09T14:00:00Z"/);
    assert.match(markup, /Observed RFQ expiry<\/span><strong[^>]*>1<\/strong>/);
    assert.match(markup, /class="citation"[^>]*>B-UNTIMED/);
    assert.deepEqual(investigation, before);
  }
});

// Timestamp/ID tie-breaking is inspection order, not a uniquely established state.
test('recorded_business_conflicting_latest_time_does_not_choose_status_by_source_id', () => {
  const investigation = variant([
    row('B-A', 'business_event', { rfq_id: 'R', event_type: 'QUOTE_AVAILABLE' }),
    row('B-Z', 'business_event', { rfq_id: 'R', event_type: 'RFQ_EXPIRED' }),
  ]);
  const markup = renderToStaticMarkup(
    <BusinessImpactPanel
      incidentId={investigation.incident_id}
      investigation={investigation}
      onEvidence={() => {}}
    />,
  );
  const summary = markup.match(
    /<details[^>]*data-testid="request-journey"[^>]*><summary>([\s\S]*?)<\/summary>/,
  )![1];
  assert.match(summary, /Chronology uncertain/);
  assert.equal(summary.includes('RFQ EXPIRED'), false);
  assert.match(markup, /B-A/);
  assert.match(markup, /B-Z/);
  assert.match(markup, /Observed RFQ expiry<\/span><strong[^>]*>1<\/strong>/);
});
