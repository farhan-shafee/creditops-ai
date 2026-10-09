import assert from 'node:assert/strict';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { Investigator } from '../src/components/investigator';
import type { Assessment, Incident, Investigation } from '../src/lib/types';

const incident: Incident = {
  id: 'INC-DEMO-003',
  scenario: 'db-pool-exhaustion',
  title: 'Synthetic processing delay',
  severity: 'SEV2',
  status: 'detected',
  started_at: '2026-10-09T14:00:00Z',
  affected_services: ['quote-service'],
  client_impact: 'Synthetic requests',
  summary: 'Synthetic incident',
  timeline: [],
  simulated_elapsed_seconds: 0,
};
const assessment = {
  incident_summary: 'Pool saturation and timeout signals were observed.',
  probable_failure_domain: 'database connection pool exhaustion following application change',
  confidence: 0.84,
  supporting_evidence_ids: ['DB-003-001'],
  alternative_hypotheses: [],
  recommended_next_steps: ['Check the pool waiters.'],
  relevant_runbooks: [],
  similar_incidents: [],
  requires_human_review: true,
  limitations: ['No causal mechanism has been established.'],
  observations: [{ statement: 'Pool usage reached its limit.', evidence_ids: ['DB-003-001'] }],
  supported_failure_condition: 'database connection pool exhaustion',
  possible_triggers: [],
  confirmed_cause: null,
  unknowns: ['Why connections remained occupied is unknown.'],
  score_kind: 'uncalibrated_support',
  rca: {
    executive_summary: 'Pool exhaustion is supported.',
    impact: 'Request processing is delayed.',
    timeline: [],
    observed_evidence: [],
    probable_root_cause: 'application change caused pool exhaustion',
    contributing_factors: [],
    immediate_next_steps: [],
    follow_up_work: [],
  },
} as Assessment;

test('assessment separates supported conditions from unknown triggers and causes and labels its score honestly', () => {
  const investigation: Investigation = {
    id: 'assessment-test',
    incident_id: incident.id,
    mode: 'REPLAY',
    status: 'complete',
    provider: 'deterministic',
    created_at: incident.started_at,
    steps: [],
    evidence: [],
    assessment,
    error: null,
    usage: {},
  };
  const markup = renderToStaticMarkup(
    <Investigator
      incident={incident}
      investigation={investigation}
      investigating={false}
      onInvestigate={() => {}}
      onEvidence={() => {}}
    />,
  );
  assert.match(markup, /Supported failure condition/);
  assert.match(markup, /Observed symptoms/);
  assert.match(markup, /Possible triggers/);
  assert.match(markup, /Confirmed cause/);
  assert.match(markup, /Not established/);
  assert.match(markup, /Why connections remained occupied is unknown/);
  assert.match(markup, /84\s*\/\s*100/);
  assert.match(markup, /uncalibrated support score/i);
  assert.equal(markup.includes('84%'), false);
  assert.equal(markup.includes('application change caused pool exhaustion'), false);
  assert.equal(markup.includes('following application change'), false);
});
