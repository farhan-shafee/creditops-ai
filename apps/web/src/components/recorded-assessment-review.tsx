import type { RecordedReview, RecordedValue, RecordedChange } from '@/lib/recorded-review';
import type { Evidence } from '@/lib/types';
import { Citation, Panel } from './primitives';
export function RecordedAssessmentReview({
  review,
  sources,
  onEvidence,
}: {
  review: RecordedReview;
  sources: ReadonlyMap<string, Evidence>;
  onEvidence: (id: string) => void;
}) {
  function content(value: unknown, field: string): React.ReactNode {
    if (value === null) return <span>Explicit null</span>;
    if (Array.isArray(value))
      return value.length ? (
        <ol>
          {value.map((item, index) => (
            <li key={index}>{content(item, field)}</li>
          ))}
        </ol>
      ) : (
        <span>Empty collection</span>
      );
    if (typeof value === 'object')
      return (
        <dl>
          {Object.entries(value as Record<string, unknown>).map(([key, item]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>{content(item, key)}</dd>
            </div>
          ))}
        </dl>
      );
    if (typeof value === 'string' && /(?:evidence|source)_ids?$/.test(field))
      return sources.has(value) ? (
        <Citation id={value} onEvidence={onEvidence} />
      ) : (
        <span>{value} — unavailable</span>
      );
    return <span className="recorded-verbatim">{String(value)}</span>;
  }
  const recorded = (value: RecordedValue, field: string) =>
    value.kind === 'missing' ? (
      <span>Not recorded</span>
    ) : value.kind === 'null' ? (
      <span>Explicit null</span>
    ) : (
      content(value.value, field)
    );
  const changes = (items: readonly RecordedChange[]) =>
    items.length ? (
      <ul>
        {items.map((item, index) => (
          <li key={index}>
            {item.kind} · {item.field} · {item.stage ?? 'Stage not recorded'} ·{' '}
            {item.reason ?? 'Reason not recorded'}
          </li>
        ))}
      </ul>
    ) : (
      <p>No recorded change or rejection for this field.</p>
    );
  return (
    <Panel
      title="Recorded assessment comparison"
      eyebrow="Read-only recorded review"
      className="recorded-readable-review"
    >
      <div className="padded">
        <p>
          Faithful recorded values before and after validation. Scores are uncalibrated; valid
          references do not establish prose accuracy. Normalization does not independently confirm
          claims.
        </p>
        <p>
          Original proposal: {review.proposalAvailability} · Recorded advisory:{' '}
          {review.advisoryAvailability} · Recorded validation: {review.validationAvailability}
        </p>
        <p>Unique normalized paths: {review.uniqueChangedPathCount}</p>
        <div className="recorded-review-rows" role="table" aria-label="Recorded field comparison">
          <div className="recorded-review-head" role="row">
            <strong role="columnheader">Field</strong>
            <strong role="columnheader">Original model proposal</strong>
            <strong role="columnheader">Recorded advisory</strong>
          </div>
          {review.rows.map((row) => (
            <div className="recorded-review-row" role="row" key={row.path}>
              <div role="rowheader">
                <h3>{row.path}</h3>
                {changes(row.changes)}
              </div>
              <div role="cell">
                <strong className="review-mobile-label">Original model proposal</strong>
                {recorded(row.original, row.path)}
              </div>
              <div role="cell">
                <strong className="review-mobile-label">Recorded advisory</strong>
                {recorded(row.advisory, row.path)}
              </div>
            </div>
          ))}
        </div>
        <section aria-label="Other recorded validation paths">
          <h3>Other recorded validation paths</h3>
          {changes(review.otherChanges)}
        </section>
        <section aria-label="Project review notes">
          <h3>Project review notes</h3>
          <p>
            Evidence-backed project observations; not an independent human audit or automatically
            proven factuality assessment.
          </p>
          {review.projectNotes ? (
            Object.entries(review.projectNotes).map(([category, values]) => (
              <div key={category}>
                <h4>
                  {(
                    {
                      identified: 'What the model identified correctly',
                      overstatements: 'Narrative overstatements',
                      validator_changes: 'What validation changed',
                      unknowns: 'What remains unknown',
                    } as Record<string, string>
                  )[category] ?? category}
                </h4>
                {content(values, category)}
              </div>
            ))
          ) : (
            <p>No project review notes recorded.</p>
          )}
        </section>
        <section aria-label="Playback validation">
          <h3>Playback validation — separate current check</h3>
          <p>
            The recorded advisory remains preserved. This check is separate from recorded validation
            and project review notes.
          </p>
          {review.playbackValidation ? (
            content(review.playbackValidation, 'playback_validation')
          ) : (
            <p>No playback validation available.</p>
          )}
        </section>
      </div>
    </Panel>
  );
}
