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

test('fresh adaptive MCP provenance exposes verified transport, cutoff, safe filters and actual tool status', () => {
  const incident = {
    id: 'INC-DEMO-001',
    scenario: 'kafka-pricing-lag',
    title: 'Synthetic latency',
    severity: 'SEV2',
    status: 'detected',
    started_at: '2026-10-09T14:00:00Z',
    affected_services: ['pricing-service'],
    client_impact: 'Synthetic requests',
    summary: 'Synthetic incident',
    timeline: [],
    simulated_elapsed_seconds: 60,
  } as Incident;
  const investigation = {
    id: 'adaptive-test',
    incident_id: incident.id,
    mode: 'MCP_DEMO',
    provider: 'deterministic',
    status: 'complete',
    created_at: incident.started_at,
    assessment: null,
    error: null,
    evidence: [],
    usage: {},
    provenance: {
      transport: 'mcp_stdio',
      workflow: 'adaptive',
      provider: 'deterministic',
      model_called: false,
      snapshot_cutoff: '2026-10-09T14:01:00Z',
      snapshot_kind: 'frozen_current',
      tool_schema_verified: true,
      recorded: false,
    },
    steps: [
      {
        id: 'STEP-001',
        action: 'Inspect backlog',
        tool: 'inspect_kafka_lag',
        status: 'complete',
        evidence_ids: ['KAFKA-001-001'],
        timestamp: '2026-10-09T14:00:58Z',
        duration_ms: 12,
        transport: 'mcp_stdio',
        provider: 'deterministic',
        provider_turn: 2,
        safe_arguments: { service: 'pricing-service' },
        recorded: false,
        error: null,
      },
    ],
  } as Investigation;
  const markup = renderToStaticMarkup(
    <Investigator
      incident={incident}
      investigation={investigation}
      investigating={false}
      onInvestigate={() => {}}
      onEvidence={() => {}}
    />,
  );
  assert.match(markup, /MCP · adaptive deterministic/);
  assert.match(markup, /MCP stdio/);
  assert.match(markup, /2026-10-09T14:01:00Z/);
  assert.match(markup, /frozen current snapshot/i);
  assert.match(markup, /Tool schemas verified/);
  assert.match(markup, /Executed tool call/);
  assert.match(markup, /Provider turn 2/);
  assert.match(markup, /pricing-service/);
  assert.equal(markup.includes('Replay · deterministic provider'), false);
});

test('complete-snapshot replay labels recorded results and original transport without inventing a cutoff', () => {
  const incident = {
    id: 'INC-DEMO-001',
    scenario: 'kafka-pricing-lag',
    title: 'Synthetic latency',
    severity: 'SEV2',
    status: 'detected',
    started_at: '2026-10-09T14:00:00Z',
    affected_services: [],
    client_impact: '',
    summary: '',
    timeline: [],
    simulated_elapsed_seconds: 0,
  } as Incident;
  const investigation = {
    id: 'replay-test',
    incident_id: incident.id,
    mode: 'REPLAY',
    provider: 'deterministic',
    status: 'complete',
    created_at: incident.started_at,
    assessment: null,
    error: null,
    evidence: [],
    usage: {},
    provenance: {
      transport: 'recorded_replay',
      workflow: 'recorded_replay',
      original_transport: 'direct',
      snapshot_kind: 'complete_scenario',
      snapshot_cutoff: null,
      recorded: true,
      model_called: false,
    },
    steps: [
      {
        id: 'STEP-001',
        action: 'Inspect database',
        tool: 'inspect_database_health',
        status: 'complete',
        evidence_ids: [],
        timestamp: '2026-10-09T14:00:58Z',
        duration_ms: 12,
        transport: 'direct',
        recorded: true,
      },
    ],
  } as Investigation;
  const markup = renderToStaticMarkup(
    <Investigator
      incident={incident}
      investigation={investigation}
      investigating={false}
      onInvestigate={() => {}}
      onEvidence={() => {}}
    />,
  );
  assert.match(markup, /complete scenario snapshot/i);
  assert.match(markup, /Recorded tool result/);
  assert.match(markup, /Original transport: direct/);
  assert.match(markup, /Cutoff not recorded/);
  assert.match(markup, /datetime="2026-10-09T14:00:58Z"/i);
  assert.equal(markup.includes('Executed tool call'), false);
});
