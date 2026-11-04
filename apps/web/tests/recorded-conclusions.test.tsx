import assert from 'node:assert/strict';
import { test } from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { projectRecordedConclusions } from '../src/lib/recorded-conclusions';
import { EvidenceConclusionExplorer } from '../src/components/evidence-conclusion-explorer';
import { GuidedRecordingReplay } from '../src/components/guided-recording-replay';
import { loadRecordedFixture } from './recorded-fixtures';

// Catch invented per-sentence support, source enrichment, and mixing original/final claims.
test('conclusions retain explicit claim citations separately from assessment-wide references', () => {
  const investigation = loadRecordedFixture('INC-DEMO-002');
  investigation.provider_proposal = {
    observations: [{ statement: '<original> literal', evidence_ids: ['METRIC-A', 'MISSING-A'] }],
    supporting_evidence_ids: ['LOG-B'],
    supported_failure_condition: 'Plain condition mentioning METRIC-A',
    probable_failure_domain: 'Plain domain',
    confirmed_cause: null,
  };
  investigation.assessment!.observations = [
    { statement: 'Advisory observation', evidence_ids: ['LOG-B'] },
  ];
  investigation.assessment!.confirmed_cause = null;
  investigation.assessment!.possible_triggers = [
    {
      statement: 'Candidate only',
      evidence_ids: ['MISSING-A'],
      status: 'candidate',
      reason: 'Unconfirmed',
    },
  ];
  investigation.assessment!.alternative_hypotheses = [
    { domain: 'Alternative', reason: 'Literal alternative reason', evidence_ids: ['LOG-B'] },
  ];
  const sources = new Map(
    investigation.evidence.slice(0, 2).map((source, index) => {
      const id = index === 0 ? 'METRIC-A' : 'LOG-B';
      return [id, { ...source, id }];
    }),
  );
  const before = structuredClone(investigation);
  const result = projectRecordedConclusions(investigation, sources);
  assert.deepEqual(result.original.claims, [
    {
      path: 'observations[0]',
      label: 'Observation',
      statement: '<original> literal',
      reason: null,
      references: [
        { id: 'METRIC-A', available: true },
        { id: 'MISSING-A', available: false },
      ],
    },
  ]);
  assert.deepEqual(result.original.assessmentReferences, [{ id: 'LOG-B', available: true }]);
  assert.equal(
    result.original.uncitedFields.find((field) => field.path === 'supported_failure_condition')
      ?.text,
    'Plain condition mentioning METRIC-A',
  );
  assert.equal(result.original.causeState, 'null');
  assert.deepEqual(
    result.advisory.claims.map((claim) => [claim.path, claim.label]),
    [
      ['observations[0]', 'Observation'],
      ['possible_triggers[0]', 'Candidate trigger — unconfirmed'],
      ['alternative_hypotheses[0]', 'Alternative hypothesis — unconfirmed'],
    ],
  );
  assert.deepEqual(investigation, before);
});

test('unavailable proposal and absent cause are distinct from explicit recorded null', () => {
  const investigation = loadRecordedFixture('INC-DEMO-002');
  investigation.provider_proposal = null;
  const missing = projectRecordedConclusions(investigation, new Map());
  assert.equal(missing.original.availability, 'unavailable');
  assert.equal(missing.original.causeState, 'missing');
  investigation.provider_proposal = { confirmed_cause: null, observations: [] };
  const explicit = projectRecordedConclusions(investigation, new Map());
  assert.equal(explicit.original.availability, 'available');
  assert.equal(explicit.original.causeState, 'null');
  assert.deepEqual(explicit.original.claims, []);
});

test('conclusions never resolve nested IDs or infer links from prose and validator reasons', () => {
  const investigation = loadRecordedFixture('INC-DEMO-002');
  investigation.provider_proposal = {
    observations: [{ statement: 'LOG-NESTED is mentioned in prose', evidence_ids: ['LOG-NESTED'] }],
    supporting_evidence_ids: [],
  };
  investigation.validation_outcome = {
    status: 'changed',
    changed_fields: [{ field: 'observations', reason: 'LOG-NESTED proves it' }],
  };
  const result = projectRecordedConclusions(investigation, new Map());
  assert.deepEqual(result.original.claims[0].references, [{ id: 'LOG-NESTED', available: false }]);
  assert.deepEqual(result.original.assessmentReferences, []);
  assert.equal(result.original.claims[0].reason, null);
});

test('explorer escapes recorded claims and leaves unavailable references inert', () => {
  const investigation = loadRecordedFixture('INC-DEMO-002');
  investigation.provider_proposal = {
    observations: [{ statement: '<script>hostile</script>', evidence_ids: ['MISSING-EXPLORER'] }],
  };
  const html = renderToStaticMarkup(
    <EvidenceConclusionExplorer
      investigation={investigation}
      sources={new Map()}
      onEvidence={() => {
        throw Error('Rendering must be local');
      }}
    />,
  );
  assert.ok(html.includes('&lt;script&gt;hostile&lt;/script&gt;'));
  assert.ok(!html.includes('<script>'));
  assert.match(html, /MISSING-EXPLORER[^<]* — unavailable/);
  assert.ok(!/<button[^>]*>MISSING-EXPLORER/.test(html));
  assert.match(html, /Original model proposal/);
  assert.match(html, /Recorded advisory/);
  assert.match(html, /Assessment-wide references/);
});

test('guided replay starts optional and inactive without selecting a stage while rendering', () => {
  const html = renderToStaticMarkup(
    <GuidedRecordingReplay
      onStep={() => {
        throw Error('No automatic stage selection');
      }}
    />,
  );
  assert.match(html, /Start guided replay/);
  assert.ok(!html.includes('aria-current="step"'));
  assert.ok(!html.includes('autoplay'));
});

test('missing claim origins and malformed references remain explicit without inferred citations', () => {
  const investigation = loadRecordedFixture('INC-DEMO-002');
  investigation.provider_proposal = {
    observations: [
      { statement: 'Unlinked observation mentions METRIC-NOT-A-LINK', evidence_ids: null },
    ],
    confirmed_cause: undefined,
    supporting_evidence_ids: ['UNKNOWN-SOURCE', null, 7, ''],
  };
  const result = projectRecordedConclusions(investigation, new Map());
  assert.deepEqual(result.original.claims[0].references, []);
  assert.deepEqual(result.original.assessmentReferences, [
    { id: 'UNKNOWN-SOURCE', available: false },
  ]);
  investigation.provider_proposal = null;
  investigation.assessment = null;
  const html = renderToStaticMarkup(
    <EvidenceConclusionExplorer
      investigation={investigation}
      sources={new Map()}
      onEvidence={() => {}}
    />,
  );
  assert.equal((html.match(/Recorded material unavailable/g) ?? []).length, 2);
  assert.equal((html.match(/Cause status not recorded/g) ?? []).length, 2);
  assert.ok(!html.includes('initiating cause unconfirmed'));
});

test('explorer offers every claim while initially showing one claim per recorded origin', () => {
  const investigation = loadRecordedFixture('INC-DEMO-002');
  investigation.provider_proposal = {
    observations: [
      { statement: 'First original full text', evidence_ids: ['MISSING-FIRST'] },
      { statement: 'Second original full text', evidence_ids: ['MISSING-SECOND'] },
    ],
    supporting_evidence_ids: ['MISSING-ASSESSMENT'],
    supported_failure_condition: 'Uncited full condition',
    confirmed_cause: null,
  };
  investigation.assessment!.observations = [
    { statement: 'First advisory full text', evidence_ids: [] },
  ];
  const html = renderToStaticMarkup(
    <EvidenceConclusionExplorer
      investigation={investigation}
      sources={new Map()}
      onEvidence={() => {}}
    />,
  );
  assert.match(html, /Original model proposal claim/);
  assert.match(html, /Recorded advisory claim/);
  assert.match(html, /<option[^>]*value="observations\[1\]"/);
  assert.ok(html.includes('First original full text'));
  assert.ok(!html.includes('Second original full text'));
  assert.ok(!html.includes('MISSING-SECOND'));
  assert.match(html, /MISSING-FIRST — unavailable/);
  assert.match(
    html,
    /<details[\s\S]*?Assessment-wide references[\s\S]*?MISSING-ASSESSMENT — unavailable/,
  );
  assert.match(html, /<details[\s\S]*?Recorded context[\s\S]*?Uncited full condition/);
  assert.match(html, /Explicit null cause: initiating cause unconfirmed/);
  assert.match(html, /id="guided-region-proposal"/);
});
