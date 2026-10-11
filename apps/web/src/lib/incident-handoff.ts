export type HandoffTemplate = 'technical' | 'stakeholder';
export type HandoffSection = {
  heading: string;
  paragraphs: readonly string[];
  evidenceIds: readonly string[];
};
export type HandoffSource = {
  id: string;
  kind: string;
  service: string;
  timestamp: string;
  detail: string;
};
export type HandoffDraft = {
  template: HandoffTemplate;
  incidentId: string;
  preparedAt: string;
  labels: readonly string[];
  sections: readonly HandoffSection[];
  sources: readonly HandoffSource[];
  pinnedSourceIds: readonly string[];
  unavailableSourceIds: readonly string[];
};

import type { RecordedRecording } from './recorded-evidence';
import {
  projectRecording,
  recordedTimestampMs,
  recordedEconomicOrderId,
  countRecordedRfqs,
  countRecordedEventRfqs,
  formatRecordedDecimal,
} from './recorded-evidence';
import type { RecordedReview } from './recorded-review';
import type { Evidence } from './types';

function text(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}
function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [];
}
function object(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}
function sourceDetail(source: Evidence): string {
  const data = source.data;
  const fields: string[] = [];
  const literal = (key: string) => {
    const value = text(data[key]);
    if (value !== null) fields.push(key + '=' + value);
  };
  if (source.kind === 'metric') {
    literal('metric');
    if (typeof data.value === 'number' && Number.isFinite(data.value))
      fields.push('value=' + data.value);
    literal('unit');
  } else if (source.kind === 'log') {
    literal('message');
    literal('severity');
  } else if (source.kind === 'business_event') {
    // Explicit event fields only; no summaries, arbitrary data, client or machine metadata.
    for (const key of [
      'event_type',
      'rfq_id',
      'instrument_id',
      'side',
      'currency',
      'par_unit',
      'quote_id',
      'order_id',
      'economic_order_id',
      'trace_id',
      'requested_at',
      'rfq_expires_at',
      'source_timestamp',
      'quote_expires_at',
      'accepted_at',
      'submitted_at',
      'acknowledged_at',
    ])
      literal(key);
    for (const key of ['par_amount', 'clean_price_per_100_par']) {
      const value = text(data[key]);
      if (value !== null && /^\d+(?:\.\d+)?$/.test(value)) {
        fields.push(key + '=' + value);
        if (key === 'par_amount') fields.push('requested par=' + formatRecordedDecimal(value));
      }
    }
    if (typeof data.retransmission === 'boolean')
      fields.push('retransmission=' + data.retransmission);
  }
  return fields.join(' · ') || 'No exportable detail fields recorded.';
}

export function prepareHandoff(
  recording: RecordedRecording,
  review: RecordedReview,
  options: {
    template: HandoffTemplate;
    preparedAt: string;
    pinnedIds: readonly string[];
    includePinnedAppendix: boolean;
  },
): HandoffDraft {
  // Reproject the full returned evidence; display projections and pins cannot narrow scope.
  const projection = projectRecording(recording.investigation, recording.investigation.incident_id);
  if (
    projection.kind !== 'ready' ||
    !recording.identity ||
    !projection.recording.identity ||
    recording.incident.id !== recording.identity.incidentId ||
    recording.identity.incidentId !== projection.recording.identity.incidentId ||
    recording.identity.sourceSha256 !== projection.recording.identity.sourceSha256 ||
    recording.identity.exportedAt !== projection.recording.identity.exportedAt
  )
    throw Error('Safe recording identity is required to prepare a handoff.');
  if (recordedTimestampMs(options.preparedAt) === null)
    throw Error('A valid explicit preparation time is required.');
  if (!['technical', 'stakeholder'].includes(options.template))
    throw Error('Unknown handoff template.');
  const full = projection.recording;
  const assessment = full.investigation.assessment;
  const sections: HandoffSection[] = [];
  const references = new Set<string>(full.contextReferences);
  const add = (heading: string, paragraphs: string[], evidenceIds: string[] = []) => {
    for (const id of evidenceIds) references.add(id);
    // Verbatim recorded prose may contain source IDs. Keep missing references labeled.
    for (const paragraph of paragraphs) {
      for (const match of paragraph.matchAll(/\[([^\[\]]+)\]/g))
        for (const id of match[1].split(',').map((v) => v.trim()))
          if (/^[A-Z][A-Z0-9_.:-]+$/.test(id)) references.add(id);
    }
    sections.push({ heading, paragraphs, evidenceIds: [...new Set(evidenceIds)] });
  };
  const metadata = full.investigation.provenance?.showcase;
  add('Recording scope', [
    'Full returned recording; display filters and pinned highlights do not change scope.',
    'Original outcome: ' +
      (text(metadata?.recorded_execution_outcome) ?? 'Not recorded') +
      '. Playback status: ' +
      full.investigation.status +
      '.',
    'Observation coverage: ' +
      (full.coverage
        ? new Date(full.coverage.startMs).toISOString() +
          ' — ' +
          new Date(full.coverage.endMs).toISOString()
        : 'Unavailable') +
      '.',
    'Evidence cutoff: ' +
      (text(full.investigation.provenance?.snapshot_cutoff) ?? 'Not recorded') +
      '.',
    'Recording generated at: ' +
      (text(metadata?.generated_at) ?? 'Not recorded') +
      '. Recording exported at: ' +
      full.identity!.exportedAt +
      '.',
  ]);
  const advisoryIds = strings(assessment?.supporting_evidence_ids);
  if (assessment) {
    const cause = object(assessment.confirmed_cause);
    add(
      'Recorded advisory and supported condition',
      [
        text(assessment.incident_summary) ?? 'Incident summary not recorded.',
        'Recorded probable failure domain: ' +
          (text(assessment.probable_failure_domain) ?? 'Not recorded') +
          '.',
        'Recorded supported failure condition: ' +
          (text(assessment.supported_failure_condition) ?? 'Not recorded') +
          '.',
        cause && text(cause.statement)
          ? 'Recorded cause claim, requiring human verification: ' + cause.statement
          : 'The initiating cause remains unconfirmed.',
      ],
      [...advisoryIds, ...strings(cause?.evidence_ids)],
    );
    const observationParagraphs: string[] = [],
      observationIds: string[] = [];
    for (const entry of Array.isArray(assessment.observations) ? assessment.observations : []) {
      const claim = object(entry);
      if (claim && text(claim.statement) !== null) {
        observationParagraphs.push(claim.statement as string);
        observationIds.push(...strings(claim.evidence_ids));
      }
    }
    add(
      'Recorded observations',
      observationParagraphs.length ? observationParagraphs : ['No advisory observations recorded.'],
      observationIds,
    );
    const hypotheses: string[] = [],
      hypothesisIds: string[] = [];
    for (const entry of Array.isArray(assessment.possible_triggers)
      ? assessment.possible_triggers
      : []) {
      const claim = object(entry);
      if (claim && text(claim.statement) !== null) {
        hypotheses.push(
          'Candidate trigger — unconfirmed: ' +
            claim.statement +
            (text(claim.reason) !== null ? ' · ' + claim.reason : ''),
        );
        hypothesisIds.push(...strings(claim.evidence_ids));
      }
    }
    for (const entry of Array.isArray(assessment.alternative_hypotheses)
      ? assessment.alternative_hypotheses
      : []) {
      const claim = object(entry);
      if (claim && text(claim.domain) !== null) {
        hypotheses.push(
          'Alternative hypothesis — unconfirmed: ' +
            claim.domain +
            (text(claim.reason) !== null ? ' · ' + claim.reason : ''),
        );
        hypothesisIds.push(...strings(claim.evidence_ids));
      }
    }
    if (hypotheses.length)
      add('Unconfirmed candidates and alternatives', hypotheses, hypothesisIds);
    add(
      'Proposed checks — human review required',
      [
        ...new Set([
          ...strings(assessment.recommended_next_steps),
          ...strings(assessment.rca?.immediate_next_steps),
          ...strings(assessment.rca?.follow_up_work),
        ]),
      ].map((v) => 'Proposed check: ' + v),
    );
    for (const id of [
      ...strings(assessment.relevant_runbooks),
      ...strings(assessment.similar_incidents),
    ])
      references.add(id);
  } else
    add('Recorded advisory unavailable', [
      'No recorded advisory assessment available. Original proposals and separate playback checks are not substituted. The initiating cause remains unconfirmed.',
    ]);
  const events = full.journeys.flatMap((j) => j.events);
  const orders = new Set(
    events.flatMap((e) => {
      const id = recordedEconomicOrderId(e);
      return id ? [id] : [];
    }),
  );
  add(
    'Recorded business observations',
    [
      'RFQs in returned events: ' +
        countRecordedRfqs(full.journeys) +
        '. Recorded economic order identities: ' +
        orders.size +
        '.',
      ...[
        'QUOTE_STALE',
        'QUOTE_UNAVAILABLE',
        'RFQ_EXPIRED',
        'PROCESSING_TIMEOUT',
        'ACK_UNCERTAIN',
      ].map(
        (kind) =>
          kind +
          ': ' +
          countRecordedEventRfqs(full.journeys, kind) +
          ' RFQs with this observed event.',
      ),
      'Pending or uncertain acknowledgement requires reconciliation before any resubmission. Retransmission does not create a second economic order. No confirmed fill, financial loss or recovery is inferred.',
    ],
    events.map((e) => e.id),
  );
  const limitations = [
    'Scores are uncalibrated. Valid source references do not establish prose accuracy. Conservative normalization is not an independent factuality guarantee.',
    'Discrete observations do not establish continuous health, ordering between tied rows, causality, or health through the evidence cutoff.',
    'Project review notes are evidence-backed project observations, not an independent human audit.',
    ...strings(assessment?.unknowns),
    ...strings(assessment?.limitations),
    ...full.warnings,
  ];
  // Original material cautions survive as cautions; original answers are never substituted.
  for (const row of review.rows)
    if (['unknowns', 'limitations'].includes(row.path)) {
      if (row.original.kind === 'value') limitations.push(...strings(row.original.value));
      if (row.advisory.kind === 'value') limitations.push(...strings(row.advisory.value));
    }
  add('Material limitations and uncertainty', [...new Set(limitations)]);
  for (const category of [
    'identified',
    'overstatements',
    'validator_changes',
    'unknowns',
  ] as const) {
    const titles = {
      identified: 'Project observations',
      overstatements: 'Project narrative cautions',
      validator_changes: 'Project validation cautions',
      unknowns: 'Project unresolved questions',
    };
    const values = strings(review.projectNotes?.[category]);
    add(titles[category], values.length ? values : ['No project notes recorded in this category.']);
  }
  // Fixed copy translates observed event counts, never the recorded technical narrative.
  const impacts = [
    ['QUOTE_STALE', 'stale quotes'],
    ['QUOTE_UNAVAILABLE', 'unavailable quotes'],
    ['RFQ_EXPIRED', 'expired request deadlines'],
    ['PROCESSING_TIMEOUT', 'processing timeouts'],
    ['ACK_UNCERTAIN', 'uncertain acknowledgements'],
  ].flatMap(([kind, description]) => {
    const count = countRecordedEventRfqs(full.journeys, kind);
    return count ? [description + ' for ' + count + (count === 1 ? ' request' : ' requests')] : [];
  });
  const stakeholderBrief: HandoffSection = {
    heading: 'Stakeholder brief',
    paragraphs: [
      'Returned events cover ' +
        countRecordedRfqs(full.journeys) +
        ' uniquely identified requests for quotes and ' +
        orders.size +
        ' economic order identities. ' +
        (impacts.length
          ? 'Observed events include ' + impacts.join('; ') + '.'
          : 'No listed adverse request events were returned; this does not establish uninterrupted health.'),
      'Recorded advisory condition, requiring human verification: ' +
        (text(assessment?.supported_failure_condition) ?? 'Not recorded') +
        '.',
      'The cause and final business outcome require human confirmation. No confirmed fill, financial loss or recovery is inferred.',
      'Please have the owning team verify the recorded condition, reconcile pending or uncertain acknowledgements before any resubmission, and review the evidence and material cautions in the appendices.',
    ],
    evidenceIds: [],
  };
  const pinned = options.includePinnedAppendix ? [...new Set(options.pinnedIds)] : [];
  for (const id of pinned) references.add(id);
  const sources = [...full.sources.values()].map((source) => ({
    id: source.id,
    kind: source.kind,
    service: source.service,
    timestamp: source.timestamp,
    detail: sourceDetail(source),
  }));
  return {
    template: options.template,
    incidentId: full.incident.id,
    preparedAt: options.preparedAt,
    labels: ['Synthetic', 'Recorded', 'Draft', 'Human review required'],
    sections:
      options.template === 'technical'
        ? sections
        : [
            stakeholderBrief,
            ...sections.map((section) => ({
              ...section,
              heading: 'Appendix — ' + section.heading,
            })),
          ],
    sources,
    pinnedSourceIds: pinned.filter((id) => full.sources.has(id)),
    unavailableSourceIds: [...references].filter((id) => !full.sources.has(id)),
  };
}
function markdownText(value: string): string {
  // Encode original characters before inserting entities. Escape every Markdown
  // punctuation character; encode line/indentation boundaries so recorded text
  // cannot create block structure. Parsers decode back to the literal preview text.
  return value
    .replace(/[!-\/:-@\[-`{-~]/g, (character) =>
      character === '&'
        ? '&amp;'
        : character === '<'
          ? '&lt;'
          : character === '>'
            ? '&gt;'
            : '\\' + character,
    )
    .replaceAll('\r', '&#13;')
    .replaceAll('\n', '&#10;')
    .replaceAll('\t', '&#9;')
    .replace(/^ +| +$/g, (spaces) => '&#32;'.repeat(spaces.length));
}
export function handoffMarkdown(draft: HandoffDraft): string {
  const lines = [
    '# ' + (draft.template === 'technical' ? 'Technical handoff' : 'Stakeholder handoff'),
    '',
    draft.labels.join(' · '),
    '',
    'Incident: ' + markdownText(draft.incidentId),
    'Prepared at: ' + draft.preparedAt,
    '',
  ];
  for (const section of draft.sections) {
    lines.push(
      '## ' + section.heading,
      '',
      ...section.paragraphs.map((v) => markdownText(v) + '\n'),
    );
    if (section.evidenceIds.length)
      lines.push(
        'Source IDs (see appendix): ' + section.evidenceIds.map(markdownText).join(', '),
        '',
      );
  }
  if (draft.pinnedSourceIds.length)
    lines.push(
      '## Pinned source highlights — optional personal selection',
      '',
      'These highlights do not narrow the full recording.',
      ...draft.pinnedSourceIds.map((id) => '- ' + markdownText(id) + ' (see source appendix)'),
      '',
    );
  if (draft.unavailableSourceIds.length)
    lines.push(
      '## Unavailable source references',
      '',
      ...draft.unavailableSourceIds.map((id) => '- ' + markdownText(id) + ' — unavailable'),
      '',
    );
  lines.push('## Source appendix — full returned recording', '');
  for (const source of draft.sources)
    lines.push(
      '- ' +
        [source.id, source.kind, source.service, source.timestamp, source.detail]
          .map(markdownText)
          .join(' · '),
    );
  return lines.join('\n') + '\n';
}
