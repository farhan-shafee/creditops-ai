import assert from 'node:assert/strict';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { Investigator } from '../src/components/investigator';
import type { Incident, Investigation } from '../src/lib/types';

test('replay provenance uses the persisted provider and still discloses no current live model call', () => {
  const incident: Incident = {
    id: 'INC-DEMO-001',
    scenario: 'kafka-pricing-lag',
    title: 'Synthetic latency',
    severity: 'SEV2',
    status: 'detected',
    started_at: '2026-10-09T14:00:00Z',
    affected_services: ['quote-service'],
    client_impact: 'Synthetic RFQs delayed',
    summary: 'Synthetic incident',
    timeline: [],
    simulated_elapsed_seconds: 0,
  };
  const investigation: Investigation = {
    id: 'demo-investigation',
    incident_id: incident.id,
    mode: 'REPLAY',
    provider: 'openai',
    status: 'completed',
    created_at: incident.started_at,
    steps: [],
    evidence: [],
    assessment: null,
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
  assert.match(markup, /Replay · openai artifact/);
  assert.match(markup, /no live model call/);
  assert.equal(markup.includes('Replay · deterministic provider'), false);
});
