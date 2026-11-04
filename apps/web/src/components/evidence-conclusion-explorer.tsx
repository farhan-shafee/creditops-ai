import { useId, useState } from 'react';
import type { Evidence, Investigation } from '@/lib/types';
import {
  projectRecordedConclusions,
  type ConclusionReference,
  type ConclusionStage,
} from '@/lib/recorded-conclusions';

function References({
  items,
  onEvidence,
}: {
  items: readonly ConclusionReference[];
  onEvidence: (id: string) => void;
}) {
  return items.length ? (
    <ul className="conclusion-explorer-references">
      {items.map((reference, index) => (
        <li key={reference.id + ':' + index}>
          {reference.available ? (
            <button className="citation" onClick={() => onEvidence(reference.id)}>
              {reference.id}
            </button>
          ) : (
            <span>{reference.id} — unavailable</span>
          )}
        </li>
      ))}
    </ul>
  ) : (
    <p className="muted">No explicit source references recorded.</p>
  );
}
function OriginStage({
  stage,
  title,
  origin,
  onEvidence,
}: {
  stage: ConclusionStage;
  title: string;
  origin: 'original' | 'advisory';
  onEvidence: (id: string) => void;
}) {
  const selectorId = useId();
  const [selectedPath, setSelectedPath] = useState(stage.claims[0]?.path ?? '');
  const claim = stage.claims.find((item) => item.path === selectedPath) ?? stage.claims[0];
  return (
    <section className="conclusion-explorer-stage guided-region" aria-label={title}>
      <h3 id={'guided-region-' + (origin === 'original' ? 'proposal' : 'advisory')} tabIndex={-1}>
        {title}
      </h3>
      <p className="conclusion-explorer-availability">
        {stage.availability === 'available'
          ? 'Recorded material available'
          : 'Recorded material unavailable'}
      </p>
      <p>
        {stage.causeState === 'null'
          ? 'Explicit null cause: initiating cause unconfirmed.'
          : stage.causeState === 'missing'
            ? 'Cause status not recorded.'
            : 'Cause field recorded; any readable claim is available in the selector and requires human verification.'}
      </p>
      {claim ? (
        <>
          <div className="conclusion-explorer-selection">
            <label htmlFor={selectorId}>{title} claim</label>
            <select
              id={selectorId}
              value={claim.path}
              onChange={(event) => setSelectedPath(event.target.value)}
            >
              {stage.claims.map((item) => (
                <option key={item.path} value={item.path}>
                  {item.label} · {item.path}
                </option>
              ))}
            </select>
          </div>
          <article className="conclusion-explorer-claim" aria-label={title + ' selected claim'}>
            <h4>{claim.label}</h4>
            <p className="conclusion-explorer-path mono">{claim.path}</p>
            <p className="recorded-verbatim">{claim.statement}</p>
            {claim.reason !== null && (
              <p className="recorded-verbatim">Recorded reason: {claim.reason}</p>
            )}
            <References items={claim.references} onEvidence={onEvidence} />
          </article>
        </>
      ) : (
        <p>
          No readable explicit claims recorded. Other recorded fields remain available in the
          complete comparison below.
        </p>
      )}
      <details className="conclusion-explorer-context">
        <summary>Recorded context · no individual claim references</summary>
        {stage.uncitedFields.length ? (
          <dl>
            {stage.uncitedFields.map((field) => (
              <div key={field.path}>
                <dt>{field.label}</dt>
                <dd className="recorded-verbatim">{field.text}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p>No readable context fields recorded.</p>
        )}
        <p>Assessment-wide references are separate from support for any individual field.</p>
      </details>
      <details className="conclusion-explorer-assessment-references">
        <summary>
          Assessment-wide references · {stage.assessmentReferences.length} recorded
          {stage.assessmentReferences.some((item) => !item.available)
            ? ' · unavailable references present'
            : ''}
        </summary>
        <References items={stage.assessmentReferences} onEvidence={onEvidence} />
      </details>
    </section>
  );
}
export function EvidenceConclusionExplorer({
  investigation,
  sources,
  onEvidence,
}: {
  investigation: Investigation;
  sources: ReadonlyMap<string, Evidence>;
  onEvidence: (id: string) => void;
}) {
  const projection = projectRecordedConclusions(investigation, sources);
  return (
    <section className="conclusion-explorer" aria-label="Evidence to conclusion explorer">
      <div className="conclusion-explorer-heading">
        <span className="eyebrow">Follow the recorded references</span>
        <h2>Evidence to conclusion</h2>
        <p>
          Choose a recorded claim and inspect its explicit references across the full returned
          recording. References show what was cited; they do not independently verify a claim or
          establish causality. Scores remain uncalibrated.
        </p>
      </div>
      <div className="conclusion-explorer-stages">
        <OriginStage
          stage={projection.original}
          title="Original model proposal"
          origin="original"
          onEvidence={onEvidence}
        />
        <OriginStage
          stage={projection.advisory}
          title="Recorded advisory"
          origin="advisory"
          onEvidence={onEvidence}
        />
      </div>
      <p className="conclusion-explorer-boundary">
        Recorded limitations, unknowns, validation reasons and project review notes remain separate
        in the complete comparison below. Missing references are unavailable; current evidence is
        never substituted.
      </p>
    </section>
  );
}
