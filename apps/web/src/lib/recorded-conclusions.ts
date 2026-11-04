import type { Evidence, Investigation } from './types';

export type ConclusionReference = { id: string; available: boolean };
export type RecordedConclusion = {
  path: string;
  label: string;
  statement: string;
  reason: string | null;
  references: readonly ConclusionReference[];
};
export type ConclusionStage = {
  availability: 'available' | 'unavailable';
  causeState: 'missing' | 'null' | 'value';
  claims: readonly RecordedConclusion[];
  assessmentReferences: readonly ConclusionReference[];
  uncitedFields: readonly { path: string; label: string; text: string }[];
};
function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
// Exact recorded IDs only. Prose, validation reasons and nearby observations do
// not establish links; the returned source map is the only resolution scope.
export function projectRecordedConclusions(
  investigation: Investigation,
  sources: ReadonlyMap<string, Evidence>,
): { original: ConclusionStage; advisory: ConclusionStage } {
  const references = (value: unknown): ConclusionReference[] =>
    Array.isArray(value)
      ? value.flatMap((id) =>
          typeof id === 'string' && id.trim().length ? [{ id, available: sources.has(id) }] : [],
        )
      : [];
  const stage = (value: unknown): ConclusionStage => {
    const root = object(value) ? value : null;
    const claims: RecordedConclusion[] = [];
    const add = (entry: unknown, path: string, label: string, statementKey = 'statement') => {
      if (!object(entry) || typeof entry[statementKey] !== 'string') return;
      claims.push({
        path,
        label,
        statement: entry[statementKey] as string,
        reason: typeof entry.reason === 'string' ? entry.reason : null,
        references: references(entry.evidence_ids),
      });
    };
    for (const [field, label, key] of [
      ['observations', 'Observation', 'statement'],
      ['possible_triggers', 'Candidate trigger — unconfirmed', 'statement'],
      ['alternative_hypotheses', 'Alternative hypothesis — unconfirmed', 'domain'],
    ]) {
      const entries = root?.[field];
      if (Array.isArray(entries))
        entries.forEach((entry, index) => add(entry, `${field}[${index}]`, label, key));
    }
    if (root?.confirmed_cause !== null)
      add(
        root?.confirmed_cause,
        'confirmed_cause',
        'Recorded cause claim — human verification required',
      );
    return {
      availability: root ? 'available' : 'unavailable',
      causeState:
        !root || !Object.hasOwn(root, 'confirmed_cause')
          ? 'missing'
          : root.confirmed_cause === null
            ? 'null'
            : 'value',
      claims,
      assessmentReferences: references(root?.supporting_evidence_ids),
      uncitedFields: [
        ['incident_summary', 'Incident summary'],
        ['probable_failure_domain', 'Probable failure domain'],
        ['supported_failure_condition', 'Supported failure condition'],
      ].flatMap(([path, label]) =>
        typeof root?.[path] === 'string' ? [{ path, label, text: root[path] as string }] : [],
      ),
    };
  };
  return {
    original: stage(investigation.provider_proposal),
    advisory: stage(investigation.assessment),
  };
}
