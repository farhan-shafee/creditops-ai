import { useEffect, useRef, useState } from 'react';
import type { RecordedRecording } from '@/lib/recorded-evidence';
import type { RecordedReview } from '@/lib/recorded-review';
import {
  prepareHandoff,
  handoffMarkdown,
  type HandoffDraft,
  type HandoffTemplate,
} from '@/lib/incident-handoff';
import { Citation, Panel } from './primitives';

export function HandoffPreview({
  draft,
  onEvidence,
}: {
  draft: HandoffDraft;
  onEvidence: (id: string) => void;
}) {
  const reference = (id: string) =>
    draft.sources.some((s) => s.id === id) ? (
      <span key={id}>
        <span className="handoff-print-id">{id}</span>
        <span className="handoff-screen-citation">
          <Citation id={id} onEvidence={onEvidence} />
        </span>
      </span>
    ) : (
      <span key={id}>{id} — unavailable</span>
    );
  return (
    <article
      className="handoff-preview"
      data-testid="handoff-preview"
      aria-label="Prepared handoff draft"
    >
      <h2>{draft.template === 'technical' ? 'Technical handoff' : 'Stakeholder handoff'}</h2>
      <p>{draft.labels.join(' · ')}</p>
      <p>Incident: {draft.incidentId}</p>
      <p>
        Prepared at:{' '}
        <time data-prepared-at dateTime={draft.preparedAt}>
          {draft.preparedAt}
        </time>
      </p>
      {draft.sections.map((section) => (
        <section key={section.heading}>
          <h3>{section.heading}</h3>
          {section.paragraphs.map((text, index) => (
            <p key={index}>{text}</p>
          ))}
          {section.evidenceIds.length > 0 && (
            <div className="handoff-references">
              <p>Source IDs (see appendix):</p>
              {section.evidenceIds.map(reference)}
            </div>
          )}
        </section>
      ))}
      {draft.pinnedSourceIds.length > 0 && (
        <section>
          <h3>Pinned source highlights — optional personal selection</h3>
          <p>These highlights do not narrow the full recording.</p>
          <div className="handoff-references">{draft.pinnedSourceIds.map(reference)}</div>
        </section>
      )}
      {draft.unavailableSourceIds.length > 0 && (
        <section>
          <h3>Unavailable source references</h3>
          <ul>
            {draft.unavailableSourceIds.map((id) => (
              <li key={id}>{id} — unavailable</li>
            ))}
          </ul>
        </section>
      )}
      <section>
        <h3>Source appendix — full returned recording</h3>
        <ol className="handoff-sources">
          {draft.sources.map((source) => (
            <li key={source.id} data-source-id={source.id}>
              {reference(source.id)}
              <p>
                {source.kind} · {source.service} · {source.timestamp}
              </p>
              <p>{source.detail}</p>
            </li>
          ))}
        </ol>
      </section>
    </article>
  );
}
export function IncidentHandoff({
  recording,
  review,
  pinnedIds,
  onEvidence,
}: {
  recording: RecordedRecording;
  review: RecordedReview;
  pinnedIds: readonly string[];
  onEvidence: (id: string) => void;
}) {
  const [template, setTemplate] = useState<HandoffTemplate>('technical');
  const [includePinned, setIncludePinned] = useState(false);
  const [draft, setDraft] = useState<HandoffDraft | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const markdownArea = useRef<HTMLTextAreaElement>(null);
  const active = useRef(true);
  const currentDraft = useRef(draft);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);

  const markdown = draft ? handoffMarkdown(draft) : '';
  const prepare = () => {
    try {
      const next = prepareHandoff(recording, review, {
        template,
        preparedAt: new Date().toISOString(),
        pinnedIds,
        includePinnedAppendix: includePinned,
      });
      currentDraft.current = next;
      setDraft(next);
      setMessage(null);
      setError(null);
    } catch {
      setError(
        'Safe recording identity and preparation time are required. Draft preparation is unavailable.',
      );
    }
  };
  const copy = async () => {
    if (!draft) return;
    const captured = draft;
    try {
      await navigator.clipboard.writeText(markdown);
      if (active.current && currentDraft.current === captured)
        setMessage('Markdown copied. Draft remains unverified and requires human review.');
    } catch {
      if (!active.current || currentDraft.current !== captured) return;
      setMessage('Clipboard unavailable. Select and copy the identical prepared Markdown below.');
      markdownArea.current?.focus();
      markdownArea.current?.select();
    }
  };
  return (
    <Panel
      title="Draft handoff"
      eyebrow="Local preparation · Human review required"
      className="incident-handoff"
    >
      <div className="handoff-controls padded">
        <p>
          Prepare a draft from the full returned recording. Review it before sharing. Preparation,
          copy and print are local actions.
        </p>
        <label>
          Handoff template
          <select value={template} onChange={(e) => setTemplate(e.target.value as HandoffTemplate)}>
            <option value="technical">Technical</option>
            <option value="stakeholder">Stakeholder</option>
          </select>
        </label>
        <label className="handoff-pin-choice">
          <input
            type="checkbox"
            checked={includePinned}
            onChange={(e) => setIncludePinned(e.target.checked)}
          />
          Include pinned source highlights
        </label>
        <div className="handoff-actions">
          <button className="button primary" onClick={prepare}>
            {draft ? 'Reprepare draft' : 'Prepare draft'}
          </button>
          <button className="button secondary" disabled={!draft} onClick={() => void copy()}>
            Copy Markdown
          </button>
          <button className="button secondary" disabled={!draft} onClick={() => window.print()}>
            Print draft
          </button>
        </div>
        {draft && (
          <p>
            Template or highlight changes apply only when you reprepare. Preview, copy and print use
            the captured draft.
          </p>
        )}
        {message && <p role="status">{message}</p>}
        {error && <p role="alert">{error}</p>}
      </div>
      {draft ? (
        <>
          <HandoffPreview draft={draft} onEvidence={onEvidence} />
          <div className="handoff-markdown padded">
            <label>
              Prepared Markdown
              <textarea ref={markdownArea} readOnly value={markdown} rows={12} spellCheck={false} />
            </label>
          </div>
        </>
      ) : (
        <p className="padded">No draft prepared.</p>
      )}
    </Panel>
  );
}
