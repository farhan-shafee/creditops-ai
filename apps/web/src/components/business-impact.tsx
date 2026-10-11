import { useEffect, useState } from 'react';
import { ArrowRight, ChevronDown, ShieldCheck } from 'lucide-react';
import { api } from '@/lib/api';
import {
  formatRecordedDecimal as par,
  groupRecordedJourneys,
  recordedTimestampMs,
  countRecordedRfqs,
  countRecordedEventRfqs,
} from '@/lib/recorded-evidence';
import type { BusinessImpact, BusinessImpactRequest, Evidence, Investigation } from '@/lib/types';
import { Badge, Citation, Panel, Spinner, Status, time } from './primitives';

export function BusinessImpactPanel({
  incidentId,
  onEvidence,
  investigation,
}: {
  incidentId: string;
  onEvidence: (id: string) => void;
  investigation?: Investigation | null;
}) {
  const [snapshot, setSnapshot] = useState<{
    incidentId: string;
    data: BusinessImpact | null;
    error: string | null;
  } | null>(null);
  useEffect(() => {
    if (investigation?.mode === 'REPLAY') return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      try {
        const data = await api<BusinessImpact>(
          `/incidents/${encodeURIComponent(incidentId)}/business-impact`,
          { signal: controller.signal },
        );
        if (data.incident_id !== incidentId)
          throw new Error('Business impact returned an unexpected incident reference');
        if (!controller.signal.aborted) setSnapshot({ incidentId, data, error: null });
      } catch (error) {
        if (!controller.signal.aborted)
          setSnapshot({
            incidentId,
            data: null,
            error: error instanceof Error ? error.message : 'Business evidence unavailable',
          });
      } finally {
        if (!controller.signal.aborted)
          timer = setTimeout(() => {
            void load();
          }, 2000);
      }
    };
    void load();
    return () => {
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [incidentId, investigation?.mode]);
  const current = snapshot?.incidentId === incidentId ? snapshot : null;
  if (investigation?.mode === 'REPLAY')
    return <RecordedBusinessImpact investigation={investigation} onEvidence={onEvidence} />;
  return (
    <Panel
      title="Business impact / affected requests"
      eyebrow="Fictional corporate bonds / event-derived states"
      action={<Badge>Current simulation window</Badge>}
      className="business-impact-panel"
    >
      {current?.data ? (
        <BusinessImpactContent impact={current.data} onEvidence={onEvidence} />
      ) : current?.error ? (
        <p className="padded muted" role="alert">
          {current.error} · Retrying the diagnostic API.
        </p>
      ) : (
        <div className="loading-row">
          <Spinner /> Loading the session-scoped request lifecycle…
        </div>
      )}
    </Panel>
  );
}

function recordedJourneyStatus(events: readonly Evidence[]): string {
  const last = events.at(-1);
  if (!last) return 'State not recorded';
  if (events.some((event) => recordedTimestampMs(event.timestamp) === null))
    return 'Chronology uncertain';
  const latestTimestamp = recordedTimestampMs(last.timestamp);
  const latestStates = new Set(
    events
      .filter((event) => recordedTimestampMs(event.timestamp) === latestTimestamp)
      .map((event) => event.data.event_type),
  );
  return latestStates.size > 1
    ? 'Chronology uncertain'
    : String(last.data.event_type ?? 'State not recorded');
}
function RecordedBusinessImpact({
  investigation,
  onEvidence,
}: {
  investigation: Investigation;
  onEvidence: (id: string) => void;
}) {
  const journeys = groupRecordedJourneys(investigation.evidence);
  const events = journeys.flatMap((journey) => journey.events);
  const groups = new Map(journeys.map((journey) => [journey.rfqId, journey.events]));
  const metadata = investigation.provenance?.showcase;
  return (
    <Panel
      title="Business impact / affected requests"
      eyebrow="Recorded events / entirely synthetic data"
      action={<Badge>Complete recorded snapshot</Badge>}
      className="business-impact-panel"
    >
      <div className="business-impact" data-testid="recorded-business-impact">
        <div className="business-summary">
          <p>Business state below comes only from the recorded evidence snapshot.</p>
          <span>
            Returned-sample coverage:{' '}
            {metadata ? `${metadata.sample_start} — ${metadata.sample_end}` : 'not recorded'} · UTC
          </span>
          <span>
            Snapshot cutoff: {investigation.provenance?.snapshot_cutoff ?? 'not recorded'} · UTC.
            The complete snapshot can contain later events than the current simulation animation.
            Sample coverage does not establish health at the cutoff.
          </span>
        </div>
        <div className="business-counters">
          <Counter
            label="RFQs in returned events"
            value={String(countRecordedRfqs(journeys))}
            id="rfqs-recorded"
          />
          {(
            [
              'QUOTE_STALE',
              'QUOTE_UNAVAILABLE',
              'RFQ_EXPIRED',
              'PROCESSING_TIMEOUT',
              'ACK_UNCERTAIN',
            ] as const
          ).map((kind) => (
            <Counter
              key={kind}
              label={
                {
                  QUOTE_STALE: 'Observed stale quotes',
                  QUOTE_UNAVAILABLE: 'Observed unavailable quotes',
                  RFQ_EXPIRED: 'Observed RFQ expiry',
                  PROCESSING_TIMEOUT: 'Observed processing timeouts',
                  ACK_UNCERTAIN: 'Observed uncertain acknowledgements',
                }[kind]
              }
              value={String(countRecordedEventRfqs(journeys, kind))}
              id={`recorded-${kind.toLowerCase()}`}
            />
          ))}
        </div>
        <div className="request-journeys">
          {[...groups].map(([id, rows], index) => (
            <details
              key={id === null ? 'unknown' : 'rfq:' + id}
              className="request-journey"
              open={index === 0}
              data-testid="request-journey"
            >
              <summary>
                <div>
                  <strong className="mono">{id ?? 'Request identity not recorded'}</strong>
                  <span>{String(rows[0].data.instrument_id ?? 'Instrument not recorded')}</span>
                </div>
                <div>
                  <span>
                    {String(rows[0].data.side ?? '')} · {String(rows[0].data.currency ?? '')}{' '}
                    {rows[0].data.par_amount
                      ? par(String(rows[0].data.par_amount)) + ' requested par'
                      : ''}
                  </span>
                  <Status value={recordedJourneyStatus(rows)} />
                </div>
                <ChevronDown size={15} />
              </summary>
              <div className="request-detail">
                <ol className="business-timeline">
                  {rows.map((event) => (
                    <li key={event.id}>
                      {recordedTimestampMs(event.timestamp) === null ? (
                        <div className="muted">
                          <p>Cannot plot this recorded row</p>
                          <p>
                            Invalid recorded timestamp: <code>{event.timestamp}</code>
                          </p>
                        </div>
                      ) : (
                        <time dateTime={event.timestamp}>
                          {time(event.timestamp)}
                          <span>UTC</span>
                        </time>
                      )}
                      <div>
                        <strong>{event.summary}</strong>
                        <p>
                          {String(event.data.event_type)} · {event.service}
                        </p>
                        {typeof event.data.order_id === 'string' && (
                          <p>
                            Economic order identity:{' '}
                            <code>
                              {String(event.data.economic_order_id ?? event.data.order_id)}
                            </code>
                            {event.data.retransmission === true
                              ? ' · retransmission of the same order'
                              : ''}
                          </p>
                        )}
                        <Citation id={event.id} onEvidence={onEvidence} />
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            </details>
          ))}
          {!events.length && (
            <p className="padded muted">
              No business events were returned in this recording. Current session rows are not
              substituted.
            </p>
          )}
        </div>
        <div className="business-boundary">
          <ShieldCheck size={15} />
          <p>
            Pending or uncertain acknowledgement requires reconciliation before any resubmission.
            Retransmission does not create a second economic order. These events do not establish
            fills, executed trades, financial losses, or revenue impact.
          </p>
        </div>
      </div>
    </Panel>
  );
}

export function BusinessImpactContent({
  impact,
  onEvidence,
}: {
  impact: BusinessImpact;
  onEvidence: (id: string) => void;
}) {
  const counters = impact.counters;
  return (
    <div className="business-impact" data-testid="business-impact">
      <div className="business-summary">
        <p>{impact.summary}</p>
        <span>
          Observed as of <time dateTime={impact.as_of}>{impact.as_of}</time>
        </span>
        <span>
          Lifecycle counters count unique RFQs with observed events; acknowledgement counters show
          the current state.
        </span>
      </div>
      <div className="business-counters">
        <Counter
          label="Affected RFQs"
          value={`${counters.rfqs_affected} / ${counters.rfqs_total}`}
          id="rfqs-affected"
        />
        <Counter
          label="Stale / unavailable quotes"
          value={`${counters.stale_quotes} / ${counters.unavailable_quotes}`}
          id="quote-quality"
        />
        <Counter
          label="Expired RFQs / quotes"
          value={`${counters.expired_rfqs} / ${counters.expired_quotes}`}
          id="expired-deadlines"
        />
        <Counter
          label="Processing timeouts"
          value={String(counters.processing_timeouts)}
          id="processing-timeouts"
        />
        <Counter
          label="Pending / unknown acks"
          value={`${counters.pending_acknowledgements} / ${counters.unknown_acknowledgements}`}
          id="acknowledgements"
        />
      </div>
      <div className="requested-par">
        <span>Requested par</span>
        {Object.entries(impact.requested_par_by_currency).map(([currency, amount]) => (
          <strong key={currency}>
            {currency} {par(amount)}
          </strong>
        ))}
        <small>Currency units of par · affected requests are not a financial-loss estimate</small>
      </div>
      <div className="request-journeys">
        {impact.requests.map((request, index) => (
          <RequestJourney
            key={request.rfq.id}
            request={request}
            onEvidence={onEvidence}
            initiallyOpen={index === 0}
          />
        ))}
        {!impact.requests.length && (
          <p className="padded muted">No request events are visible at this simulation time.</p>
        )}
      </div>
      <div className="business-boundary">
        <ShieldCheck size={15} />
        <p>
          Pending or unknown acknowledgement requires reconciliation; it is not evidence of a failed
          or executed order. An acknowledgement records receipt only. Quote expiry and RFQ expiry
          are separate states.
        </p>
      </div>
      {impact.limitations.length > 0 && (
        <details className="business-limitations">
          <summary>Simulation boundaries</summary>
          <ul>
            {impact.limitations.map((value) => (
              <li key={value}>{value}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function Counter({ label, value, id }: { label: string; value: string; id: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong data-testid={`impact-${id}`}>{value}</strong>
    </div>
  );
}

function RequestJourney({
  request: r,
  onEvidence,
  initiallyOpen,
}: {
  request: BusinessImpactRequest;
  onEvidence: (id: string) => void;
  initiallyOpen: boolean;
}) {
  return (
    <details className="request-journey" open={initiallyOpen} data-testid="request-journey">
      <summary>
        <div>
          <strong className="mono">{r.rfq.id}</strong>
          <span>
            {r.instrument.issuer} · {r.instrument.id}
          </span>
        </div>
        <div>
          <span>
            {r.rfq.side} · {r.rfq.currency} {par(r.rfq.par_amount)} par
          </span>
          <Status value={r.processing_state} />
        </div>
        <ChevronDown size={15} />
      </summary>
      <div className="request-detail">
        <div className="request-chain">
          <span>{r.instrument.id}</span>
          <ArrowRight size={12} />
          <span>{r.rfq.id}</span>
          <ArrowRight size={12} />
          <span>{r.quote.id ?? 'Quote unavailable'}</span>
          <ArrowRight size={12} />
          <span>{r.order?.id ?? 'No order submitted'}</span>
        </div>
        <p className="instrument-description">
          {r.instrument.instrument_type} · {r.instrument.currency} · {r.instrument.coupon_percent}%
          annual coupon · maturity {r.instrument.maturity}
        </p>
        <div className="request-states">
          <div>
            <h4>RFQ state</h4>
            <Status value={r.rfq.status} />
            <p>
              {r.rfq.client_id} · client {r.rfq.side.toLowerCase()}
            </p>
            <p>
              Requested {time(r.rfq.requested_at)} UTC
              <br />
              RFQ deadline {time(r.rfq.expires_at)} UTC
            </p>
          </div>
          <div>
            <h4>Quote state</h4>
            <Status value={r.quote.status} />
            <p>
              {r.quote.clean_price_per_100_par === null
                ? 'No published clean price'
                : `Clean price ${r.quote.clean_price_per_100_par} per 100 par`}
            </p>
            <p>
              Source{' '}
              {r.quote.source_timestamp ? `${time(r.quote.source_timestamp)} UTC` : 'not published'}
              <br />
              Quote deadline {r.quote.expires_at ? `${time(r.quote.expires_at)} UTC` : 'not set'}
            </p>
            {r.quote.freshness_ms !== null && (
              <p>Quote age {r.quote.freshness_ms.toLocaleString('en-US')} ms</p>
            )}
            <p>
              Accepted {r.quote.accepted_at ? `${time(r.quote.accepted_at)} UTC` : 'not accepted'}
            </p>
          </div>
          <div>
            <h4>Order acknowledgement</h4>
            {r.order ? (
              <>
                <Status value={r.order.status} />
                <p>{r.order.id}</p>
                <p>
                  {r.order.acknowledged_at
                    ? `Receipt acknowledged ${time(r.order.acknowledged_at)} UTC`
                    : 'No confirmed acknowledgement receipt'}
                </p>
              </>
            ) : (
              <p>No economic order submitted.</p>
            )}
            <p className="muted">Execution and settlement are not simulated.</p>
          </div>
        </div>
        <div className="request-correlation">
          <span>
            Correlation <code>{r.rfq.trace_id}</code>
          </span>
          <span>
            Requested par{' '}
            <strong>
              {r.rfq.currency} {par(r.rfq.par_amount)}
            </strong>{' '}
            · {r.rfq.par_unit}
          </span>
        </div>
        <h4 className="request-timeline-title">Request / quote / order event timeline</h4>
        <ol className="business-timeline">
          {r.timeline.map((event) => (
            <li key={event.id}>
              <time dateTime={event.timestamp}>
                {time(event.timestamp)}
                <span>UTC</span>
              </time>
              <div>
                <strong>{event.summary}</strong>
                <p>
                  Affected service <code>{event.service}</code>
                </p>
                <Citation id={event.id} onEvidence={onEvidence} />
              </div>
            </li>
          ))}
        </ol>
        {!r.timeline.length && (
          <p className="muted">No lifecycle event is visible at this cutoff.</p>
        )}
      </div>
    </details>
  );
}
