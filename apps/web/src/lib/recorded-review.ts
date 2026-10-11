import type { Investigation } from './types';
export type RecordedValue =
  { kind: 'missing' } | { kind: 'null' } | { kind: 'value'; value: unknown };
export type RecordedChange = {
  field: string;
  stage: string | null;
  reason: string | null;
  kind: 'changed' | 'rejected';
};
export type ReviewRow = {
  path: string;
  original: RecordedValue;
  advisory: RecordedValue;
  changes: readonly RecordedChange[];
};
type Provenance = NonNullable<Investigation['provenance']>;
export type RecordedReview = {
  rows: readonly ReviewRow[];
  otherChanges: readonly RecordedChange[];
  uniqueChangedPathCount: number;
  proposalAvailability: 'available' | 'unavailable';
  validationAvailability: 'available' | 'unavailable';
  advisoryAvailability: 'available' | 'unavailable';
  projectNotes: NonNullable<Provenance['showcase']>['review_notes'] | null;
  playbackValidation: Provenance['playback_validation'] | null;
};
const fields = [
  'incident_summary',
  'probable_failure_domain',
  'supported_failure_condition',
  'observations',
  'supporting_evidence_ids',
  'confirmed_cause',
  'possible_triggers',
  'unknowns',
  'limitations',
  'alternative_hypotheses',
  'recommended_next_steps',
  'relevant_runbooks',
  'similar_incidents',
  'requires_human_review',
  'confidence',
  'score_kind',
  'rca.executive_summary',
  'rca.impact',
  'rca.timeline',
  'rca.observed_evidence',
  'rca.probable_root_cause',
  'rca.contributing_factors',
  'rca.immediate_next_steps',
  'rca.follow_up_work',
] as const;
function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function recordedValue(root: unknown, path: string): RecordedValue {
  let value = root;
  for (const part of path.split('.')) {
    if (!object(value) || !Object.hasOwn(value, part)) return { kind: 'missing' };
    value = value[part];
  }
  return value === null ? { kind: 'null' } : { kind: 'value', value };
}
function recordedChanges(value: unknown, kind: RecordedChange['kind']): RecordedChange[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) =>
    !object(entry) || typeof entry.field !== 'string'
      ? []
      : [
          {
            field: entry.field,
            stage: typeof entry.stage === 'string' ? entry.stage : null,
            reason: typeof entry.reason === 'string' ? entry.reason : null,
            kind,
          },
        ],
  );
}
export function projectRecordedReview(investigation: Investigation): RecordedReview {
  const proposal = investigation.provider_proposal,
    advisory = investigation.assessment,
    validation = investigation.validation_outcome;
  const changes = [
    ...recordedChanges(validation?.changed_fields, 'changed'),
    ...recordedChanges(validation?.rejected_fields, 'rejected'),
  ];
  const known = new Set<string>(fields);
  return {
    rows: fields.map((path) => ({
      path,
      original: recordedValue(proposal, path),
      advisory: recordedValue(advisory, path),
      changes: changes.filter((change) => change.field === path),
    })),
    otherChanges: changes.filter((change) => !known.has(change.field)),
    uniqueChangedPathCount: new Set(
      changes.filter((change) => change.kind === 'changed').map((change) => change.field),
    ).size,
    proposalAvailability: object(proposal) ? 'available' : 'unavailable',
    validationAvailability: object(validation) ? 'available' : 'unavailable',
    advisoryAvailability: object(advisory) ? 'available' : 'unavailable',
    projectNotes: investigation.provenance?.showcase?.review_notes ?? null,
    playbackValidation: investigation.provenance?.playback_validation ?? null,
  };
}
