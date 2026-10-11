import assert from 'node:assert/strict';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { IncidentView } from '../src/views/incidents';
import { RecordedEvidenceTimeline } from '../src/components/recorded-evidence-timeline';
import {
  projectRecording,
  defaultWorkspaceFilters,
  filterRecordedEvidence,
} from '../src/lib/recorded-evidence';
import { Investigator } from '../src/components/investigator';
import { loadRecordedFixture } from './recorded-fixtures';
import type { Investigation, Incident } from '../src/lib/types';
const recording = loadRecordedFixture('INC-DEMO-001');
const incident = {
  id: recording.incident_id,
  scenario: 'kafka-pricing-lag',
  title: 'Current animation title',
  status: 'detected',
  severity: 'SEV2',
  started_at: '2026-10-09T14:00:00Z',
  affected_services: [],
  client_impact: 'current animation',
  summary: 'current state',
  timeline: [],
  simulated_elapsed_seconds: 0,
} as Incident;
function render(value: Investigation) {
  return renderToStaticMarkup(
    <IncidentView
      incident={incident}
      incidents={[incident]}
      metrics={[]}
      topology={null}
      investigation={value}
      investigating={false}
      investigationMode="REPLAY"
      onInvestigationMode={() => {}}
      running={false}
      onInvestigate={() => {}}
      onEvidence={() => {}}
      onIncident={() => {}}
    />,
  );
}
test('only_matching_showcase_replay_uses_workspace', () => {
  const html = render(recording);
  assert.match(html, /data-testid="recorded-workspace"/);
  for (const tab of ['Overview', 'Evidence', 'Review', 'Handoff'])
    assert.match(html, new RegExp('role="tab"[^>]*>' + tab));
  assert.match(html, /Synthetic · Recorded · Human review required/);
  assert.match(html, /Original outcome/);
  assert.match(html, /Playback status/);
  assert.equal(
    render({ ...recording, mode: 'MCP_DEMO' }).includes('data-testid="recorded-workspace"'),
    false,
  );
  assert.equal(
    render({ ...recording, provenance: {} }).includes('data-testid="recorded-workspace"'),
    false,
  );
  assert.match(render({ ...recording, incident_id: 'different' }), /Recording unavailable/);
});
test('workspace_absence_is_explicit', () => {
  const html = render({ ...recording, assessment: null });
  assert.match(html, /No assessment produced/);
  assert.equal(html.includes('data-testid="assessment"'), false);
  assert.match(
    render({ ...recording, evidence: recording.evidence.filter((row) => row.id !== incident.id) }),
    /Recording unavailable/,
  );
});
test('timeline_table_equals_discrete_sources', () => {
  const projection = projectRecording(recording, incident.id);
  assert.equal(projection.kind, 'ready');
  if (projection.kind !== 'ready') return;
  const filters = { ...defaultWorkspaceFilters(projection.recording), metricGroupKey: null };
  const view = filterRecordedEvidence(projection.recording, filters);
  const expected = [
    ...view.metrics.flatMap((group) => group.samples),
    ...view.logs,
    ...view.business,
  ];
  const html = renderToStaticMarkup(
    <RecordedEvidenceTimeline
      recording={projection.recording}
      filters={filters}
      selectedSourceId={null}
      onFilters={() => {}}
      onSelect={() => {}}
    />,
  );
  const table = html.match(/<tbody>([\s\S]*?)<\/tbody>/)![1];
  const ids = [...table.matchAll(/<tr[^>]*data-source-id="([^"]+)"/g)]
    .map((match) => match[1])
    .sort();
  assert.deepEqual(ids, expected.map((row) => row.source.id).sort());
  const markers = [...html.matchAll(/<circle[^>]*data-source-id="([^"]+)"/g)]
    .map((match) => match[1])
    .sort();
  assert.deepEqual(markers, ids);
  for (const row of expected) {
    const sourceRow = [...table.matchAll(/<tr[\s\S]*?<\/tr>/g)].find((match) =>
      match[0].includes('data-source-id="' + row.source.id + '"'),
    )![0];
    assert.ok(sourceRow.includes(row.source.timestamp));
    if (row.source.kind === 'metric') {
      assert.ok(sourceRow.includes(String(row.source.data.value)));
      assert.ok(sourceRow.includes(String(row.source.data.unit)));
    }
  }
  for (const svg of html.matchAll(/<svg[^>]*role="group"[\s\S]*?<\/svg>/g))
    assert.equal(/<path|<polygon|<polyline|<rect/.test(svg[0]), false);
  assert.match(html, /Recorded observations/);
  const unplottable = {
    ...recording.evidence.find((row) => row.kind === 'metric')!,
    id: 'UNPLOTTABLE-SOURCE',
    timestamp: 'invalid',
  };
  const changed = projectRecording(
    { ...recording, evidence: [...recording.evidence, unplottable] },
    incident.id,
  );
  assert.equal(changed.kind, 'ready');
  if (changed.kind === 'ready') {
    const contextHtml = renderToStaticMarkup(
      <RecordedEvidenceTimeline
        recording={changed.recording}
        filters={filters}
        selectedSourceId={unplottable.id}
        onFilters={() => {}}
        onSelect={() => {}}
      />,
    );
    assert.match(contextHtml, /data-source-id="UNPLOTTABLE-SOURCE" data-selected="true"/);
    assert.match(contextHtml, /Cannot plot this recorded row UNPLOTTABLE-SOURCE/);
  }
});
test('overlap_retains_all_sources', () => {
  const evidence = structuredClone(recording.evidence);
  const metric = evidence.find((row) => row.kind === 'metric')!;
  evidence.push({ ...metric, id: 'OVERLAP-A' }, { ...metric, id: 'OVERLAP-B' });
  const projection = projectRecording({ ...recording, evidence }, incident.id);
  assert.equal(projection.kind, 'ready');
  if (projection.kind !== 'ready') return;
  // Explicit All display keeps this test about overlap/source fidelity, separate from the default.
  const html = renderToStaticMarkup(
    <RecordedEvidenceTimeline
      recording={projection.recording}
      filters={{ ...defaultWorkspaceFilters(projection.recording), metricGroupKey: null }}
      selectedSourceId={null}
      onFilters={() => {}}
      onSelect={() => {}}
    />,
  );
  assert.match(html, /Choose overlapping sources/);
  assert.match(html, /OVERLAP-A/);
  assert.match(html, /OVERLAP-B/);
});
test('legacy_attribution_survives_extraction', () => {
  const html = renderToStaticMarkup(
    <Investigator
      incident={incident}
      investigation={recording}
      investigating={false}
      onMode={() => {}}
      onInvestigate={() => {}}
      onEvidence={() => {}}
    />,
  );
  assert.match(html, /Investigation path/);
  assert.match(html, /View recorded investigation/);
  assert.match(html, /Application-runbook initial diagnostic/);
  assert.match(html, /Recorded model response/);
  assert.match(html, /local validation/);
});

test('workspace_uses_lexical_metric_default', () => {
  const projection = projectRecording(recording, incident.id);
  assert.equal(projection.kind, 'ready');
  if (projection.kind !== 'ready') return;
  const metricSelect = render(recording).match(
    /Metric and unit<select[^>]*>([\s\S]*?)<\/select>/,
  )![1];
  const selected = metricSelect.match(/<option value="([^"]*)" selected="">/)?.[1];
  assert.equal(
    selected?.replaceAll('&quot;', '"').replaceAll('&amp;', '&'),
    defaultWorkspaceFilters(projection.recording).metricGroupKey,
  );
  assert.match(metricSelect, /<option value="">All metric groups/);
});

// Removing the shared facts or substituting current state must fail these oracles.
test('final_fix_header_uses_all_recorded_business_and_advisory_states', () => {
  const cases = [
    [
      'INC-DEMO-001',
      [
        '2 returned RFQs',
        'stale quotes: 1 RFQ',
        'unavailable quotes: 1 RFQ',
        'expired RFQ deadlines: 2 RFQs',
      ],
    ],
    [
      'INC-DEMO-002',
      ['2 returned RFQs', '2 economic order identities', 'uncertain acknowledgements: 2 RFQs'],
    ],
    [
      'INC-DEMO-003',
      ['2 returned RFQs', 'processing timeouts: 2 RFQs', 'expired RFQ deadlines: 2 RFQs'],
    ],
  ] as const;
  for (const [id, impacts] of cases) {
    const value = loadRecordedFixture(id);
    const html = renderToStaticMarkup(
      <IncidentView
        incident={{ ...incident, id }}
        incidents={[]}
        metrics={[]}
        topology={null}
        investigation={value}
        investigating={false}
        investigationMode="REPLAY"
        onInvestigationMode={() => {}}
        running={false}
        onInvestigate={() => {}}
        onEvidence={() => {}}
        onIncident={() => {}}
      />,
    );
    const header = html.match(/<header class="recorded-workspace-header"[\s\S]*?<\/header>/)![0];
    for (const text of impacts) assert.ok(header.includes(text), text);
    assert.ok(header.includes(value.assessment!.supported_failure_condition!));
    assert.ok(header.includes('Initiating cause unconfirmed'));
  }
  const header = (value: Investigation) =>
    render(value).match(/<header class="recorded-workspace-header"[\s\S]*?<\/header>/)![0];
  assert.match(
    header({ ...recording, assessment: null }),
    /Recorded advisory condition unavailable/,
  );
  assert.match(header({ ...recording, assessment: null }), /Initiating cause unavailable/);
  assert.match(
    header({
      ...recording,
      assessment: {
        ...recording.assessment!,
        confirmed_cause: { statement: 'Exact returned cause', evidence_ids: ['LOG-001-001'] },
      },
    }),
    /Initiating cause confirmed in recorded advisory: Exact returned cause/,
  );
});
test('final_fix_context_retains_annotation_time_label_references_without_promoting_sources', () => {
  const value = structuredClone(loadRecordedFixture('INC-DEMO-003'));
  const owner = value.evidence.find((row) => row.kind === 'incident')!;
  (owner.data.timeline as unknown[]).push(
    {
      timestamp: '2026-10-09T16:00:00Z',
      label: '<script>Outside context</script>',
      evidence_ids: ['LOG-003-001', 'OUTSIDE-NOT-RETURNED'],
    },
    {
      timestamp: 'invalid-time',
      label: 'Invalid annotation time',
      evidence_ids: ['INVALID-NOT-RETURNED'],
    },
  );
  const projection = projectRecording(value, value.incident_id);
  assert.equal(projection.kind, 'ready');
  if (projection.kind !== 'ready') return;
  const html = renderToStaticMarkup(
    <RecordedEvidenceTimeline
      recording={projection.recording}
      filters={defaultWorkspaceFilters(projection.recording)}
      selectedSourceId={null}
      onFilters={() => {}}
      onSelect={() => {}}
    />,
  );
  const annotations =
    html.match(/<ol class="recorded-context-annotations"[\s\S]*?<\/ol>/)?.[0] ?? '';
  assert.match(annotations, /Alert threshold crossed/);
  assert.match(annotations, /2026-10-09T14:00:00Z/);
  assert.match(annotations, /DEPLOY-003-001/);
  assert.match(annotations, /Referenced in context; source not returned/);
  assert.match(annotations, /2026-10-09T16:00:00Z/);
  assert.match(annotations, /Outside returned-sample coverage/);
  assert.match(annotations, /Invalid recorded annotation timestamp/);
  assert.match(annotations, /&lt;script&gt;Outside context/);
  assert.ok(!annotations.includes('<script>'));
  assert.equal(projection.recording.sources.size, value.evidence.length);
  assert.equal(projection.recording.sources.has('OUTSIDE-NOT-RETURNED'), false);
  assert.equal(projection.recording.coverage!.endMs, Date.parse('2026-10-09T14:02:24Z'));
});
