import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parsers } from 'prettier/plugins/markdown';
import type { ParserOptions } from 'prettier';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import * as handoff from '../src/lib/incident-handoff';
import { projectRecording, filterRecordedEvidence } from '../src/lib/recorded-evidence';
import { projectRecordedReview } from '../src/lib/recorded-review';
import { loadRecordedFixture, type RecordedFixtureId } from './recorded-fixtures';
const preparedAt = '2030-01-02T03:04:05.000Z';
function recording(id: RecordedFixtureId = 'INC-DEMO-002') {
  const investigation = loadRecordedFixture(id);
  const projection = projectRecording(investigation, id);
  assert.equal(projection.kind, 'ready');
  if (projection.kind !== 'ready') throw Error('fixture');
  return projection.recording;
}
function prepare(
  value: ReturnType<typeof recording>,
  template: handoff.HandoffTemplate,
  pinnedIds: string[] = [],
  includePinnedAppendix = true,
) {
  assert.equal(typeof handoff.prepareHandoff, 'function', 'full-record composer must exist');
  return handoff.prepareHandoff(value, projectRecordedReview(value.investigation), {
    template,
    preparedAt,
    pinnedIds,
    includePinnedAppendix,
  });
}
// A narrowed composer, dropped appendix, generic serialization, or substituted
// proposal/current assessment must fail these tests.
test('handoff_full_scope_survives_filters_and_pins', () => {
  const value = recording();
  const before = structuredClone(value.investigation);
  const narrowed = filterRecordedEvidence(value, {
    service: 'rfq-gateway',
    metricGroupKey: null,
    request: null,
    window: null,
  });
  assert.equal(narrowed.metrics.length, 0);
  for (const template of ['technical', 'stakeholder'] as const) {
    const draft = prepare(value, template, [value.investigation.evidence[0].id]);
    assert.deepEqual(draft.sources.map((s) => s.id).sort(), [...value.sources.keys()].sort());
    assert.equal(draft.pinnedSourceIds.length, 1);
    assert.deepEqual(prepare(value, template).sources, draft.sources);
    assert.deepEqual(prepare(value, template, ['LOG-002-002'], false).pinnedSourceIds, []);
    assert.ok(handoff.handoffMarkdown(draft).includes('4900'));
  }
  assert.deepEqual(value.investigation, before);
});
test('handoff_sources_and_material_unknowns_survive_both_templates', () => {
  for (const id of ['INC-DEMO-001', 'INC-DEMO-002', 'INC-DEMO-003'] as const) {
    const value = recording(id);
    value.investigation.assessment!.supporting_evidence_ids.push('SOURCE-NOT-RETURNED');
    for (const template of ['technical', 'stakeholder'] as const) {
      const draft = prepare(value, template, ['PIN-NOT-RETURNED']);
      const markdown = handoff.handoffMarkdown(draft).replace(/\\([^\p{L}\p{N}\s])/gu, '$1');
      for (const text of [
        ...value.investigation.assessment!.unknowns!,
        ...value.investigation.assessment!.limitations,
        ...Object.values(value.investigation.provenance!.showcase!.review_notes).flat(),
        'Synthetic · Recorded · Draft · Human review required',
        'initiating cause remains unconfirmed',
        'uncalibrated',
        'Retransmission does not create a second economic order',
        'No confirmed fill, financial loss or recovery is inferred',
      ])
        assert.ok(markdown.includes(text), text);
      for (const source of draft.sources) assert.ok(value.sources.has(source.id));
      assert.ok(markdown.includes('SOURCE-NOT-RETURNED — unavailable'));
      assert.ok(markdown.includes('PIN-NOT-RETURNED — unavailable'));
      for (const section of draft.sections)
        for (const sourceId of section.evidenceIds)
          assert.ok(
            draft.sources.some((s) => s.id === sourceId) ||
              draft.unavailableSourceIds.includes(sourceId),
          );
      if (id === 'INC-DEMO-002') {
        assert.ok(markdown.includes('ACK_UNCERTAIN'));
        assert.ok(markdown.includes('retransmission=true'));
        assert.ok(markdown.includes('1000000.00'));
      }
    }
  }
});
test('handoff_allowlist_excludes_personal_and_private_data', async () => {
  const value = recording();
  const canary = 'PRIVATE-CANARY-C:\\machine\\admin';
  Object.assign(value.investigation, {
    notes: canary,
    filters: canary,
    config: canary,
    session: canary,
    metadata: canary,
  });
  value.investigation.usage.private = canary;
  value.investigation.provenance!.private = canary;
  Object.assign(value.investigation.provenance!.showcase!, { config: canary, receipt: canary });
  Object.assign(value.investigation.provenance!.showcase!.review_notes, { private: [canary] });
  Object.assign(value.investigation.assessment!, { private: canary });
  Object.assign(value.investigation.assessment!.observations![0], { private: canary });
  for (const source of value.sources.values()) {
    Object.assign(source, { private: canary });
    source.data.private = canary;
    source.data.config = { private: canary };
  }
  value.investigation.assessment!.observations!.push({
    statement: '<script>alert(1)</script>',
    evidence_ids: ['LOG-002-002'],
  });
  const review = projectRecordedReview(value.investigation);
  const before = structuredClone({ recording: value, review });
  assert.equal(typeof handoff.prepareHandoff, 'function', 'full-record composer must exist');
  const { HandoffPreview } = await import('../src/components/incident-handoff');
  for (const template of ['technical', 'stakeholder'] as const) {
    const draft = handoff.prepareHandoff(value, review, {
      template,
      preparedAt,
      pinnedIds: [],
      includePinnedAppendix: false,
    });
    const markdown = handoff.handoffMarkdown(draft).replace(/\\([^\p{L}\p{N}\s])/gu, '$1');
    const html = renderToStaticMarkup(
      <HandoffPreview
        draft={draft}
        onEvidence={() => {
          throw Error('render must be inert');
        }}
      />,
    );
    assert.ok(!JSON.stringify(draft).includes(canary));
    assert.ok(!markdown.includes(canary));
    assert.ok(!html.includes(canary));
    assert.equal(draft.preparedAt, preparedAt);
    assert.ok(markdown.includes('Prepared at: ' + preparedAt));
    assert.ok(html.includes(preparedAt));
    const metadata = value.investigation.provenance!.showcase!;
    for (const marker of [
      'Recording generated at: ' + metadata.generated_at,
      'Recording exported at: ' + metadata.exported_at,
    ]) {
      assert.ok(markdown.includes(marker));
      assert.ok(html.includes(marker));
    }
    assert.ok(html.includes('&lt;script&gt;'));
    assert.ok(!html.includes('<script>'));
    for (const source of draft.sources) assert.ok(html.includes(source.id));
  }
  assert.deepEqual({ recording: value, review }, before);
});
test('handoff_missing_assessment_does_not_invent_answer', () => {
  const value = recording();
  Object.assign(value.investigation, {
    assessment: null,
    provider_proposal: { incident_summary: 'PROPOSAL-MUST-NOT-BECOME-ANSWER' },
  });
  value.investigation.provenance!.playback_validation = {
    recorded_output_preserved: true,
    assessment_would_change: true,
    current_validation_assessment: { incident_summary: 'CURRENT-MUST-NOT-BECOME-ANSWER' },
  };
  for (const template of ['technical', 'stakeholder'] as const) {
    const markdown = handoff
      .handoffMarkdown(prepare(value, template))
      .replace(/\\([^\p{L}\p{N}\s])/gu, '$1');
    assert.ok(markdown.includes('No recorded advisory assessment available'));
    assert.ok(!markdown.includes('PROPOSAL-MUST-NOT-BECOME-ANSWER'));
    assert.ok(!markdown.includes('CURRENT-MUST-NOT-BECOME-ANSWER'));
    assert.ok(markdown.includes('ACK_UNCERTAIN'));
  }
});
test('handoff_rejects_unsafe_identity_and_invalid_preparation_time', () => {
  const value = recording();
  assert.equal(typeof handoff.prepareHandoff, 'function', 'full-record composer must exist');
  assert.throws(() => prepare({ ...value, identity: null }, 'technical'), /identity/i);
  assert.throws(
    () => prepare({ ...value, incident: { ...value.incident, id: 'WRONG' } }, 'technical'),
    /identity/i,
  );
  assert.equal(typeof handoff.prepareHandoff, 'function');
  assert.throws(
    () =>
      handoff.prepareHandoff(value, projectRecordedReview(value.investigation), {
        template: 'technical',
        preparedAt: 'not-time',
        pinnedIds: [],
        includePinnedAppendix: false,
      }),
    /time/i,
  );
});

test('handoff_stakeholder_short_impact_summary_retains_complete_labeled_appendices', () => {
  for (const id of ['INC-DEMO-001', 'INC-DEMO-002', 'INC-DEMO-003'] as const) {
    const value = recording(id);
    const technical = prepare(value, 'technical');
    const stakeholder = prepare(value, 'stakeholder');
    const brief = stakeholder.sections[0];
    assert.equal(brief.heading, 'Stakeholder brief');
    assert.equal(brief.paragraphs.length, 4);
    assert.equal(brief.evidenceIds.length, 0, 'complete references belong in appendices');
    assert.ok(brief.paragraphs[1].includes('requiring human verification'));
    assert.ok(
      brief.paragraphs[1].includes(value.investigation.assessment!.supported_failure_condition!),
    );
    assert.ok(brief.paragraphs[2].includes('cause'));
    assert.ok(brief.paragraphs[2].includes('final business outcome'));
    assert.ok(brief.paragraphs[3].startsWith('Please have the owning team verify'));
    const briefText = brief.paragraphs.join('\n');
    assert.ok(!briefText.includes('QUOTE_STALE'));
    assert.ok(!briefText.includes('ACK_UNCERTAIN'));
    assert.ok(!briefText.includes(value.investigation.assessment!.incident_summary));
    assert.ok(stakeholder.sections.slice(1).every((s) => s.heading.startsWith('Appendix — ')));
    assert.ok(
      stakeholder.sections.some(
        (s) => s.heading === 'Appendix — Material limitations and uncertainty',
      ),
    );
    assert.ok(
      stakeholder.sections.some(
        (s) => s.heading === 'Appendix — Proposed checks — human review required',
      ),
    );
    assert.ok(
      stakeholder.sections.some((s) => s.heading === 'Appendix — Project narrative cautions'),
    );
    assert.deepEqual(
      stakeholder.sections.slice(1).map((s) => [s.paragraphs, s.evidenceIds]),
      technical.sections.map((s) => [s.paragraphs, s.evidenceIds]),
    );
    assert.deepEqual(stakeholder.sources, technical.sources);
    if (id === 'INC-DEMO-002')
      assert.equal(
        brief.paragraphs[0],
        'Returned events cover 2 uniquely identified requests for quotes and 2 economic order identities. Observed events include uncertain acknowledgements for 2 requests.',
      );
  }
});
type MarkdownNode = {
  type: string;
  value?: string;
  depth?: number;
  ordered?: boolean;
  children?: MarkdownNode[];
};
function markdownTextContent(node: MarkdownNode): string {
  return node.value ?? node.children?.map(markdownTextContent).join('') ?? '';
}
test('handoff_markdown_parser_preserves_hostile_recorded_text_and_generated_structure', async () => {
  const value = recording();
  const hostile = [
    '1. Recorded observation\n2. Another observation\n\n---\n\n~~qualified~~',
    '\tindented tab\n    indented spaces\n    3. literal number',
    'Heading\n===\n\nHeading\n---',
    '> quoted\n- bullet\n+ bullet\n* bullet',
    '~~~js\ncode\n~~~\n\n```js\ncode\n```',
    '**claim** _emphasis_ ~~~tilde~~~ `code` [label](https://example.invalid) ![image](https://example.invalid) [ref][id]',
    '[id]: https://example.invalid\nhttps://example.invalid and www.example.invalid and person@example.invalid',
    '| label | value |\n| --- | --- |\n| a | b |',
    '<script>alert(1)</script> &amp; <https://example.invalid> \\',
  ];
  value.investigation.assessment!.observations = hostile.map((statement) => ({
    statement,
    evidence_ids: [],
  }));
  const markdown = handoff.handoffMarkdown(prepare(value, 'technical'));
  const ast: MarkdownNode = await parsers.markdown.parse(markdown, {
    parser: 'markdown',
  } as ParserOptions<MarkdownNode>);
  const children = ast.children!;
  const start = children.findIndex(
    (node) => node.type === 'heading' && markdownTextContent(node) === 'Recorded observations',
  );
  assert.ok(start >= 0);
  const nextHeading = children.findIndex((node, index) => index > start && node.type === 'heading');
  const body = children.slice(start + 1, nextHeading);
  assert.ok(
    body.every((node) => node.type === 'paragraph'),
    'recorded lines cannot create lists, headings, code, tables, HTML or breaks',
  );
  const allText = (node: MarkdownNode): boolean =>
    node.type === 'text' || (node.type === 'paragraph' && Boolean(node.children?.every(allText)));
  assert.ok(
    body.every(allText),
    'recorded inline syntax cannot create formatting, links or images',
  );
  assert.equal(
    body.map(markdownTextContent).join('\n\n'),
    hostile.join('\n\n'),
    'parsed text must equal the captured preview text',
  );
  assert.ok(
    children.some(
      (node) =>
        node.type === 'heading' &&
        node.depth === 1 &&
        markdownTextContent(node) === 'Technical handoff',
    ),
  );
  assert.ok(
    children.some((node) => node.type === 'list' && node.ordered === false),
    'generated source appendix list remains a list',
  );
});
