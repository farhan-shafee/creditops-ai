import assert from 'node:assert/strict';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { BusinessImpactContent } from '../src/components/business-impact';
import type { BusinessImpact } from '../src/lib/types';

test('business impact keeps decimal par exact and distinguishes RFQ, quote and acknowledgement states', () => {
  const impact: BusinessImpact = {
    incident_id: 'INC-DEMO-002',
    as_of: '2026-10-09T14:01:00Z',
    summary: 'An acknowledgement is unknown.',
    counters: {
      rfqs_total: 1,
      rfqs_affected: 1,
      stale_quotes: 0,
      unavailable_quotes: 0,
      expired_rfqs: 0,
      expired_quotes: 1,
      processing_timeouts: 0,
      pending_acknowledgements: 0,
      unknown_acknowledgements: 1,
    },
    requested_par_by_currency: { USD: '9007199254740993.25' },
    limitations: ['No execution or settlement is simulated.'],
    requests: [
      {
        rfq: {
          id: 'RFQ-DEMO-001',
          client_id: 'CLIENT-DEMO-001',
          instrument_id: 'BOND-DEMO-001',
          side: 'BUY',
          par_amount: '9007199254740993.25',
          currency: 'USD',
          par_unit: 'currency par',
          requested_at: '2026-10-09T14:00:00Z',
          expires_at: '2026-10-09T14:03:00Z',
          trace_id: 'TRACE-DEMO-001',
          status: 'OPEN',
        },
        instrument: {
          id: 'BOND-DEMO-001',
          issuer: 'Fictional Elm Industries',
          currency: 'USD',
          coupon_percent: '4.25',
          maturity: '2031-10-09',
          instrument_type: 'Synthetic corporate bond',
        },
        processing_state: 'QUOTE_AVAILABLE',
        quote: {
          id: 'QUOTE-DEMO-001',
          status: 'EXPIRED',
          clean_price_per_100_par: '99.25',
          source_timestamp: '2026-10-09T14:00:00Z',
          expires_at: '2026-10-09T14:00:30Z',
          accepted_at: null,
          freshness_ms: 60000,
        },
        order: {
          id: 'ORDER-DEMO-001',
          status: 'UNKNOWN',
          submitted_at: '2026-10-09T14:00:10Z',
          acknowledged_at: null,
          trace_id: 'TRACE-DEMO-001',
        },
        timeline: [
          {
            id: 'BUSINESS-001-ORDER_UNKNOWN',
            kind: 'business',
            service: 'fix-gateway',
            timestamp: '2026-10-09T14:00:40Z',
            summary: 'Acknowledgement remains unknown.',
            data: {},
          },
        ],
        evidence_ids: ['BUSINESS-001-ORDER_UNKNOWN'],
      },
    ],
  };
  const markup = renderToStaticMarkup(
    <BusinessImpactContent impact={impact} onEvidence={() => {}} />,
  );
  assert.match(markup, /9,007,199,254,740,993\.25/);
  assert.match(markup, /Requested par/);
  assert.match(markup, /RFQ state/);
  assert.match(markup, /Quote state/);
  assert.match(markup, /UNKNOWN/);
  assert.match(markup, /per 100 par/);
  assert.match(markup, /4\.25% annual coupon/);
  assert.match(markup, /BUSINESS-001-ORDER_UNKNOWN/);
  assert.equal(markup.includes('FAILED'), false);
  assert.equal(markup.includes('EXECUTED'), false);
  assert.equal(markup.includes('lost revenue'), false);
  assert.equal(markup.includes('settlement value'), false);
});
