import assert from 'node:assert/strict';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { Investigator } from '../src/components/investigator';
import type { Assessment, Incident, Investigation, Step } from '../src/lib/types';

const incident: Incident = {
  id: 'INC-DEMO-001',
  scenario: 'kafka-pricing-lag',
  title: 'Reported synthetic latency',
  severity: 'SEV2',
  status: 'detected',
  started_at: '2026-10-09T14:00:00Z',
  affected_services: ['quote-service'],
  client_impact: 'Reported synthetic requests',
  summary: 'Synthetic incident',
  timeline: [],
  simulated_elapsed_seconds: 0,
};

function step(tool: string, selected_by?: Step['selected_by']): Step {
  return {
    id: `STEP-${tool}`,
    action: tool,
    tool,
    status: 'complete',
    evidence_ids: [],
    timestamp: incident.started_at,
    duration_ms: 12,
    transport: selected_by === 'validator' ? 'local_validation' : 'mcp_stdio',
    provider: 'openai',
    provider_turn: selected_by === 'application_runbook' ? 0 : 1,
    selected_by,
  };
}

function investigation(overrides: Partial<Investigation> = {}): Investigation {
  return {
    id: 'evidence-first-test',
    incident_id: incident.id,
    mode: 'LIVE_AI',
    provider: 'openai',
    status: 'complete',
    created_at: incident.started_at,
    assessment: null,
    error: null,
    evidence: [],
    steps: [],
    usage: {},
    provenance: {
      workflow: 'evidence_first_v1',
      transport: 'mcp_stdio',
      model_called: true,
      assessment_source: { kind: 'live_provider', provider: 'openai' },
    },
    ...overrides,
  };
}

function render(value: Investigation): string {
  return renderToStaticMarkup(
    <Investigator
      incident={incident}
      investigation={value}
      investigating={false}
      onInvestigate={() => {}}
      onEvidence={() => {}}
    />,
  );
}

const abstention: Assessment = {
  incident_summary: 'Returned samples do not establish a failure domain.',
  probable_failure_domain: 'insufficient evidence',
  confidence: 0.23,
  supporting_evidence_ids: [],
  alternative_hypotheses: [],
  recommended_next_steps: ['Review missing coverage.'],
  relevant_runbooks: [],
  similar_incidents: [],
  requires_human_review: true,
  limitations: ['A point observation does not establish continuous health.'],
  supported_failure_condition: null,
  confirmed_cause: null,
  rca: {
    executive_summary: 'Human review required.',
    impact: 'Business impact is unverified.',
    timeline: [],
    observed_evidence: [],
    probable_root_cause: 'Insufficient evidence.',
    contributing_factors: [],
    immediate_next_steps: [],
    follow_up_work: [],
  },
};

test('evidence-first trace credits the initial packet to the application and only live follow-ups to the model', () => {
  const markup = render(
    investigation({
      steps: [
        ...['get_incident', 'get_service_topology', 'query_metrics', 'search_logs'].map((tool) =>
          step(tool, 'application_runbook'),
        ),
        step('inspect_database_health', 'model'),
        step('validate_assessment', 'validator'),
      ],
    }),
  );
  assert.match(markup, /Workflow: evidence_first_v1/);
  assert.equal((markup.match(/Application-runbook initial diagnostic/g) ?? []).length, 4);
  assert.equal((markup.match(/Model-selected follow-up diagnostic/g) ?? []).length, 1);
  assert.match(markup, /Validator-authored assessment check/);
  assert.equal(markup.includes('Provider turn 0'), false);
});

test('deterministic and scripted follow-ups never receive model-selected labels', () => {
  const markup = render(
    investigation({
      mode: 'MCP_DEMO',
      provider: 'deterministic',
      steps: [
        step('inspect_fix_session', 'deterministic'),
        step('search_runbooks', 'scripted_provider'),
      ],
      provenance: { workflow: 'evidence_first_v1', model_called: false },
    }),
  );
  assert.match(markup, /Deterministic-provider-selected diagnostic/);
  assert.match(markup, /Scripted-provider-selected diagnostic/);
  assert.equal(markup.includes('Model-selected follow-up diagnostic'), false);
});

test('legacy recordings retain their workflow and missing action selection remains unrecorded', () => {
  const markup = render(
    investigation({
      mode: 'REPLAY',
      steps: [step('get_incident'), step('get_service_topology')],
      provenance: {
        workflow: 'recorded_replay', original_workflow: 'adaptive',
        original_transport: 'mcp_stdio', recorded: true,
      },
    }),
  );
  assert.match(markup, /Workflow: recorded_replay/);
  assert.match(markup, /Original workflow: adaptive/);
  assert.equal((markup.match(/Selection source not recorded/g) ?? []).length, 2);
  assert.equal(markup.includes('evidence_first_v1'), false);
  assert.equal(markup.includes('Application-runbook initial diagnostic'), false);
  assert.match(markup, /Recorded tool result/);
});

test('new recordings display the recorded evidence-first workflow and original action attribution', () => {
  const markup = render(
    investigation({
      mode: 'REPLAY',
      steps: [step('query_metrics', 'application_runbook')],
      provenance: {
        workflow: 'recorded_replay', original_workflow: 'evidence_first_v1',
        original_transport: 'mcp_stdio', recorded: true,
      },
    }),
  );
  assert.match(markup, /Original workflow: evidence_first_v1/);
  assert.match(markup, /Application-runbook initial diagnostic/);
  assert.match(markup, /Recorded tool result/);
});

test('completed abstention separates execution, model proposal, validator edits and final advisory outcome', () => {
  const markup = render(
    investigation({
      assessment: abstention,
      provider_proposal: {
        probable_failure_domain: 'insufficient evidence',
        incident_summary: '<script>untrusted proposal</script>',
      },
      validation_outcome: {
        status: 'abstained',
        changed_fields: [
          {
            field: 'incident_summary',
            reason: 'abstention_narrative_normalization',
            stage: 'diagnostic_validation',
          },
        ],
        rejected_fields: [],
      },
    }),
  );
  assert.match(markup, /Execution complete/);
  assert.match(markup, /Abstained · no failure domain identified/);
  assert.match(markup, /Model-authored proposal · openai/);
  assert.match(markup, /Validator-authored changes and rejections/);
  assert.match(markup, /abstention_narrative_normalization/);
  assert.match(markup, /Final advisory assessment/);
  assert.match(markup, /&lt;script&gt;untrusted proposal&lt;\/script&gt;/);
  assert.equal(markup.includes('<script>untrusted proposal</script>'), false);
  assert.equal(markup.includes('Evidence-backed assessment'), false);
});

test('deterministic fallback origin does not erase earlier model-decision provenance', () => {
  const markup = render(
    investigation({
      assessment: abstention,
      provenance: {
        workflow: 'evidence_first_v1',
        model_called: true,
        assessment_source: {
          kind: 'orchestrator_fallback',
          provider: 'deterministic',
          reason: 'budget_or_no_progress',
        },
      },
    }),
  );
  assert.match(markup, /Model call recorded/);
  assert.match(markup, /Deterministic fallback assessment · deterministic/);
  assert.equal(markup.includes('Model-authored proposal'), false);
});

test('strict failure before assessment retains the rejection and reports assessment absence', () => {
  const markup = render(
    investigation({
      status: 'failed',
      error: 'Strict verification stopped: duplicate diagnostic action.',
      validation_outcome: {
        status: 'not_validated',
        provider_response: 'not_requested_due_to_guard_stop',
        rejected_fields: [
          { field: 'action', reason: 'duplicate_action', stage: 'investigation_guard' },
        ],
      },
      provenance: { workflow: 'evidence_first_v1', model_called: true, assessment_source: null },
    }),
  );
  assert.match(markup, /Execution failed/);
  assert.match(markup, /No assessment produced/);
  assert.match(markup, /duplicate_action/);
  assert.match(markup, /not_requested_due_to_guard_stop/);
  assert.equal(markup.includes('Final advisory assessment'), false);
  assert.equal(markup.includes('Model-authored proposal'), false);
});
