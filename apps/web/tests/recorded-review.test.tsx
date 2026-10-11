import assert from 'node:assert/strict';
import { test } from 'node:test';
import { projectRecordedReview } from '../src/lib/recorded-review';
import { loadRecordedFixture } from './recorded-fixtures';
// Catch altered collections, absence collapse, dropped recorded reasons/stages,
// duplicate path counts, and mixing project/playback findings into recorded rows.
test('review_preserves_values_reasons_and_absence', () => {
  const value = loadRecordedFixture('INC-DEMO-002'),
    proposal = value.provider_proposal!;
  proposal.supported_failure_condition = null;
  delete proposal.confirmed_cause;
  proposal.unknowns = [];
  value.validation_outcome!.changed_fields!.push({
    field: 'unfamiliar.path',
    stage: 'new_stage',
    reason: 'recorded_reason',
  });
  value.validation_outcome!.rejected_fields = [
    { field: 'confidence', stage: 'reference_validation', reason: 'recorded_rejection' },
  ];
  value.provenance!.playback_validation = {
    recorded_output_preserved: true,
    assessment_would_change: true,
    current_validation_assessment: { incident_summary: 'Do not substitute current result' },
  };
  const before = structuredClone(value),
    review = projectRecordedReview(value);
  const get = (path: string) => {
    const found = review.rows.find((r) => r.path === path);
    assert.ok(found, path);
    return found;
  };
  assert.deepEqual(get('incident_summary').original, {
    kind: 'value',
    value: proposal.incident_summary,
  });
  assert.deepEqual(get('incident_summary').advisory, {
    kind: 'value',
    value: value.assessment!.incident_summary,
  });
  assert.deepEqual(get('observations').original, { kind: 'value', value: proposal.observations });
  assert.deepEqual(get('observations').advisory, {
    kind: 'value',
    value: value.assessment!.observations,
  });
  assert.deepEqual(get('supported_failure_condition').original, { kind: 'null' });
  assert.deepEqual(get('confirmed_cause').original, { kind: 'missing' });
  assert.deepEqual(get('unknowns').original, { kind: 'value', value: [] });
  assert.deepEqual(
    get('limitations').changes.map((r) => [r.field, r.stage, r.reason]),
    [
      ['limitations', 'diagnostic_validation', 'known_domain_rule_normalization'],
      ['limitations', 'orchestration', 'execution_provenance_limitation'],
    ],
  );
  assert.deepEqual(get('confidence').changes.at(-1), {
    field: 'confidence',
    stage: 'reference_validation',
    reason: 'recorded_rejection',
    kind: 'rejected',
  });
  assert.equal(review.uniqueChangedPathCount, 18);
  assert.deepEqual(review.otherChanges, [
    { field: 'unfamiliar.path', stage: 'new_stage', reason: 'recorded_reason', kind: 'changed' },
  ]);
  assert.deepEqual(review.projectNotes, value.provenance!.showcase!.review_notes);
  assert.deepEqual(review.playbackValidation, value.provenance!.playback_validation);
  assert.equal(review.proposalAvailability, 'available');
  assert.equal(review.validationAvailability, 'available');
  assert.equal(review.advisoryAvailability, 'available');
  for (const field of [
    'probable_failure_domain',
    'supporting_evidence_ids',
    'alternative_hypotheses',
    'recommended_next_steps',
    'relevant_runbooks',
    'similar_incidents',
    'requires_human_review',
    'score_kind',
    'possible_triggers',
  ])
    assert.ok(get(field));
  for (const field of Object.keys(value.assessment!.rca)) {
    assert.deepEqual(get('rca.' + field).original, {
      kind: 'value',
      value: (proposal.rca as Record<string, unknown>)[field],
    });
    assert.deepEqual(get('rca.' + field).advisory, {
      kind: 'value',
      value: (value.assessment!.rca as unknown as Record<string, unknown>)[field],
    });
  }
  assert.deepEqual(value, before);
});
test('review_unavailable_states_are_independent_and_do_not_substitute_playback', () => {
  const value = loadRecordedFixture('INC-DEMO-001');
  value.provider_proposal = null;
  value.validation_outcome = null;
  value.assessment = null;
  value.provenance = {
    playback_validation: {
      recorded_output_preserved: true,
      assessment_would_change: true,
      current_validation_assessment: { incident_summary: 'Current result' },
    },
  };
  const result = projectRecordedReview(value);
  assert.equal(result.proposalAvailability, 'unavailable');
  assert.equal(result.validationAvailability, 'unavailable');
  assert.equal(result.advisoryAvailability, 'unavailable');
  assert.equal(result.projectNotes, null);
  assert.equal(result.uniqueChangedPathCount, 0);
  assert.ok(
    result.rows.every((r) => r.original.kind === 'missing' && r.advisory.kind === 'missing'),
  );
  const independent = projectRecordedReview({
    ...value,
    provider_proposal: { incident_summary: '' },
    validation_outcome: { status: 'abstained' },
  });
  assert.equal(independent.proposalAvailability, 'available');
  assert.equal(independent.validationAvailability, 'available');
  assert.equal(independent.advisoryAvailability, 'unavailable');
  assert.deepEqual(independent.rows[0].original, { kind: 'value', value: '' });
});
