import assert from 'node:assert/strict';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { Investigator } from '../src/components/investigator';
import { BusinessImpactPanel } from '../src/components/business-impact';
import { OverviewView } from '../src/views/overview';
import { EvaluationsView } from '../src/views/evaluations';
import type { Incident, Investigation, Evaluation } from '../src/lib/types';

const incident: Incident = {
  id: 'INC-DEMO-001',
  scenario: 'kafka-pricing-lag',
  title: 'Pricing backlog',
  severity: 'SEV2',
  status: 'detected',
  started_at: '2026-10-09T14:00:00Z',
  affected_services: ['quote-service'],
  client_impact: 'Synthetic RFQs',
  summary: 'Pricing is delayed.',
  timeline: [],
  simulated_elapsed_seconds: 0,
};
const recording = {
  id: 'recorded-test',
  incident_id: incident.id,
  mode: 'REPLAY',
  status: 'complete',
  provider: 'openai',
  created_at: '2026-10-10T00:00:00Z',
  assessment: null,
  steps: [],
  error: null,
  usage: {},
  evidence: [
    {
      id: 'BUSINESS-001-001',
      kind: 'business_event',
      service: 'rfq-gateway',
      timestamp: '2026-10-09T14:02:00Z',
      summary: 'Recorded RFQ expired',
      data: { event_type: 'RFQ_EXPIRED', rfq_id: 'RFQ-RECORDED-ONLY', order_id: null },
    },
  ],
  provider_calls: [
    {
      schema: 'AvailableAdaptiveDecision',
      structured_output: { action: 'assess', request: null },
      started_at: '2026-10-09T20:00:00Z',
      duration_ms: 1200,
    },
    {
      schema: 'Assessment',
      structured_output: {},
      started_at: '2026-10-09T20:00:02Z',
      duration_ms: 2800,
    },
  ],
  provider_proposal: { incident_summary: '<script>incorrect claim</script>', confidence: 0.97 },
  validation_outcome: {
    status: 'accepted',
    changed_fields: [{ field: 'incident_summary', reason: 'conservative_narrative_normalization' }],
  },
  provenance: {
    original_workflow: 'evidence_first_v1',
    snapshot_cutoff: '2026-10-09T15:00:00Z',
    showcase: {
      title: 'Pricing backlog',
      scenario_id: 'kafka-pricing-lag',
      generated_at: '2026-10-09T20:00:00Z',
      exported_at: '2026-10-10T01:00:00Z',
      sample_start: '2026-10-09T14:00:00Z',
      sample_end: '2026-10-09T14:02:24Z',
      original_duration_seconds: 4,
      source_commit: 'original-source',
      source_receipt: 'source.json',
      review_notes: {
        identified: ['Backlog symptoms are supported.'],
        overstatements: ['Continuous health at the cutoff is unproven.'],
        validator_changes: ['Narrative normalized; not every edit detects an error.'],
        unknowns: ['The trigger remains unknown.'],
      },
    },
  },
} as unknown as Investigation;
const evaluation = {
  selected_recordings: [
    {
      incident_id: incident.id,
      title: 'Pricing backlog',
      scenario_id: incident.scenario,
      execution_outcome: 'completed',
      proposed_domain: 'pricing backlog',
      final_domain: 'pricing backlog',
      validation_status: 'accepted',
      application_selected_diagnostic_count: 4,
      model_selected_diagnostic_count: 0,
      model_decision_count: 1,
      model_assessment_count: 1,
      original_duration_seconds: 4,
      major_limitations: ['Continuous coverage is unproven.'],
    },
  ],
} as Evaluation;

test('recording inspection retains untrusted proposal, project review notes and separate clock meanings', () => {
  const markup = renderToStaticMarkup(
    <Investigator
      incident={incident}
      investigation={recording}
      investigating={false}
      onInvestigate={() => {}}
      onEvidence={() => {}}
    />,
  );
  assert.match(markup, /Original model proposal and review notes/);
  assert.match(markup, /Project review notes/);
  assert.match(markup, /Continuous health at the cutoff is unproven/);
  assert.match(markup, /Returned-sample coverage/);
  assert.match(markup, /Original generation/);
  assert.match(markup, /Exported/);
  assert.match(markup, /Playback started/);
  assert.match(markup, /Model decision · assess/);
  assert.match(markup, /Model assessment/);
  assert.equal(markup.includes('<script>incorrect claim</script>'), false);
  assert.equal(markup.includes('Model-selected follow-up diagnostic'), false);
});

test('recorded business impact renders only captured events rather than loading session state', () => {
  const props = { incidentId: incident.id, onEvidence: () => {}, investigation: recording };
  const markup = renderToStaticMarkup(<BusinessImpactPanel {...props} />);
  assert.match(markup, /RFQ-RECORDED-ONLY/);
  assert.match(markup, /Recorded RFQ expired/);
  assert.match(markup, /Complete recorded snapshot/);
  assert.equal(markup.includes('Current simulation window'), false);
  assert.equal(markup.includes('Loading the session-scoped request lifecycle'), false);
});

test('recruiter entry offers the three recordings and identifies paid-call-free playback', () => {
  const markup = renderToStaticMarkup(
    <OverviewView
      overview={null}
      scenarios={[
        {
          id: incident.scenario,
          title: 'Pricing backlog',
          description: 'Recorded RFQ expiry',
          incident_id: incident.id,
        },
        {
          id: 'fix-session-instability',
          title: 'FIX session instability',
          description: 'Recorded uncertain acknowledgement',
          incident_id: 'INC-DEMO-002',
        },
        {
          id: 'db-pool-exhaustion',
          title: 'Database pool exhaustion',
          description: 'Recorded DB wait',
          incident_id: 'INC-DEMO-003',
        },
      ]}
      selectedScenario={incident.scenario}
      onScenario={() => {}}
      onRun={() => {}}
      busy={false}
      metrics={[]}
      topology={null}
      onEvidence={() => {}}
      onIncident={() => {}}
      evaluation={evaluation}
    />,
  );
  assert.match(markup, /View recorded investigation/);
  assert.match(markup, /Recorded model-assisted run/);
  assert.match(markup, /No new model calls during playback/);
  assert.match(markup, /Human review required/);
  assert.equal((markup.match(/data-testid="recorded-example"/g) ?? []).length, 3);
});

test('selected results expose attribution and limitations separately from the benchmark', () => {
  const markup = renderToStaticMarkup(<EvaluationsView evaluation={evaluation} />);
  assert.match(markup, /Selected recorded synthetic examples/);
  assert.match(markup, /Pricing backlog/);
  assert.match(markup, /0 model-selected diagnostics/);
  assert.match(markup, /Continuous coverage is unproven/);
  assert.match(markup, /Earlier attempts failed or abstained/);
  const review = markup.match(
    /<details([^>]*)><summary>Project review notes<\/summary>([\s\S]*?)<\/details>/,
  );
  assert.ok(review, 'Narrative limitations belong in expandable project notes');
  assert.equal(/\bopen(?:=|\s|$)/.test(review[1]), false, 'Project notes start collapsed');
  assert.match(review[2], /Continuous coverage is unproven/);
});

test('recorded model decision and proposal precede the local validator in the trace', () => {
  const value = {
    ...recording,
    steps: [
      {
        id: 'initial',
        action: 'Initial diagnostic',
        tool: 'query_metrics',
        status: 'complete',
        evidence_ids: [],
        timestamp: incident.started_at,
        duration_ms: 10,
        selected_by: 'application_runbook',
      },
      {
        id: 'validator',
        action: 'Local validation marker',
        tool: 'assessment_validation',
        status: 'complete',
        evidence_ids: [],
        timestamp: incident.started_at,
        duration_ms: 0,
        selected_by: 'validator',
        transport: 'local_validation',
      },
    ],
  } as Investigation;
  const markup = renderToStaticMarkup(
    <Investigator
      incident={incident}
      investigation={value}
      investigating={false}
      onInvestigate={() => {}}
      onEvidence={() => {}}
    />,
  );
  const trace = markup.slice(markup.indexOf('class="investigation-trace"'));
  assert.ok(trace.indexOf('Initial diagnostic') < trace.indexOf('Model decision · assess'));
  assert.ok(trace.indexOf('Model decision · assess') < trace.indexOf('Model assessment'));
  assert.ok(trace.indexOf('Model assessment') < trace.indexOf('Local validation marker'));
});

test('playback revalidation changes stay explicitly separate from the preserved recorded output', () => {
  const value = {
    ...recording,
    provenance: {
      ...recording.provenance,
      playback_validation: {
        recorded_output_preserved: true,
        assessment_would_change: true,
        checked_at: '2026-10-10T02:00:00Z',
        current_validation_assessment: {
          incident_summary: 'Current check output, not the recording',
        },
        scope: 'Structural and reference checks',
      },
    },
  };
  const markup = renderToStaticMarkup(
    <Investigator
      incident={incident}
      investigation={value}
      investigating={false}
      onInvestigate={() => {}}
      onEvidence={() => {}}
    />,
  );
  assert.match(markup, /Playback validation check — recorded output preserved/);
  assert.match(markup, /Current check would change the assessment/);
  assert.match(markup, /Current check output, not the recording/);
  assert.match(markup, /&lt;script&gt;incorrect claim/);
});

test('replay transport cannot relabel validator-authored checks as recorded diagnostic tools', () => {
  const value: Investigation = {
    ...recording,
    steps: [
      {
        id: 'by-author',
        action: 'Original validator check',
        tool: 'validation_check',
        status: 'complete',
        evidence_ids: [],
        timestamp: incident.started_at,
        duration_ms: 0,
        selected_by: 'validator',
        transport: 'recorded_replay',
        recorded: true,
      },
      {
        id: 'by-tool',
        action: 'Legacy assessment validation',
        tool: 'assessment_validation',
        status: 'complete',
        evidence_ids: [],
        timestamp: incident.started_at,
        duration_ms: 0,
        transport: 'recorded_replay',
        recorded: true,
      },
    ],
  };
  const markup = renderToStaticMarkup(
    <Investigator
      incident={incident}
      investigation={value}
      investigating={false}
      onInvestigate={() => {}}
      onEvidence={() => {}}
    />,
  );
  const trace = markup.slice(markup.indexOf('class="investigation-trace"'));
  assert.equal((trace.match(/Recorded validation action/g) ?? []).length, 2);
  assert.equal((trace.match(/<span>local validation<\/span>/g) ?? []).length, 2);
  assert.equal(trace.includes('Recorded tool result'), false);
});
