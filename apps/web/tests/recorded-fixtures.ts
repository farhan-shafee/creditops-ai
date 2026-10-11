import { readFileSync } from 'node:fs';
import type { Investigation } from '../src/lib/types';
export type RecordedFixtureId = 'INC-DEMO-001' | 'INC-DEMO-002' | 'INC-DEMO-003';
// Test-only clones of preserved bytes; adapt replay presentation, never answers.
export function loadRecordedFixture(id: RecordedFixtureId): Investigation {
  const payload = JSON.parse(
    readFileSync(new URL('../../../data/showcase/' + id + '.json', import.meta.url), 'utf8'),
  ).payload;
  const investigation: Investigation = structuredClone(payload.investigation);
  investigation.mode = 'REPLAY';
  investigation.provenance = {
    ...investigation.provenance,
    original_workflow: payload.provenance.workflow,
    original_model: payload.provenance.original_model,
    snapshot_cutoff: payload.provenance.snapshot_cutoff,
    transport: 'recorded_replay',
    recorded: true,
    model_called: false,
  };
  return investigation;
}
export function loadRecordedManifest() {
  return JSON.parse(
    readFileSync(new URL('../../../data/showcase/manifest.json', import.meta.url), 'utf8'),
  );
}
