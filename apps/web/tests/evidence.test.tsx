import assert from 'node:assert/strict';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { EvidenceText } from '../src/components/evidence-text';

test('evidence references become inspectable citations without inventing identifiers', () => {
  const markup = renderToStaticMarkup(
    <EvidenceText text="Pool waits increased [DB-EVID-003, LOG-000142]." onEvidence={() => {}} />,
  );
  assert.match(markup, /<button[^>]*>DB-EVID-003<\/button>/);
  assert.match(markup, /<button[^>]*>LOG-000142<\/button>/);
  assert.match(markup, /Pool waits increased/);
});

test('ordinary operational prose remains prose', () => {
  const markup = renderToStaticMarkup(
    <EvidenceText
      text="No supported conclusion; escalate for human review."
      onEvidence={() => {}}
    />,
  );
  assert.equal(markup.includes('<button'), false);
});

test('metric citations retain the entire persisted identifier including underscores', () => {
  const id = 'METRIC-001-SERIES-QUOTE-SERVICE-REQUEST_LATENCY_P95_MS-2';
  const markup = renderToStaticMarkup(
    <EvidenceText text={`Latency rises [${id}].`} onEvidence={() => {}} />,
  );
  assert.match(markup, new RegExp(`<button[^>]*>${id}</button>`));
});

test('business event references open exact evidence identifiers rather than becoming inert prose', () => {
  const id = 'BUSINESS-001-RFQ-DEMO-001-QUOTE_STALE';
  const markup = renderToStaticMarkup(
    <EvidenceText text={`Quote freshness changed [${id}].`} onEvidence={() => {}} />,
  );
  assert.match(markup, new RegExp(`<button[^>]*>${id}</button>`));
});
