import { focusRecordedSource, type RecordedSourceControls } from './recorded-incident-workspace';
import { useEffect, useRef } from 'react';
import { X, FileSearch } from 'lucide-react';
import type { Evidence } from '@/lib/types';
import { Badge, Spinner } from './primitives';

export function EvidenceDrawer({
  id,
  evidence,
  error,
  onClose,
  recordedControls,
}: {
  id: string;
  evidence: Evidence | null;
  error: string | null;
  onClose: () => void;
  recordedControls?: RecordedSourceControls;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLDivElement>(null);
  const revealedRef = useRef(false);
  useEffect(() => {
    const prior = document.activeElement as HTMLElement | null;
    revealedRef.current = false;
    closeRef.current?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key === 'Tab') {
        const items = drawerRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a, input:not([disabled]), summary, [tabindex="0"]',
        );
        if (!items?.length) return;
        const first = items[0],
          last = items[items.length - 1];
        if (!drawerRef.current?.contains(document.activeElement)) {
          event.preventDefault();
          (event.shiftKey ? last : first).focus();
        } else if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', handler);
    const original = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handler);
      document.body.style.overflow = original;
      // Evidence Reveal returns to the exact source; ordinary close keeps its trigger.
      const restoredSource = revealedRef.current && focusRecordedSource(id);
      if (!restoredSource) {
        if (prior?.isConnected) prior.focus();
        else document.querySelector<HTMLElement>('[data-testid="personal-clear"]')?.focus();
      }
    };
  }, [onClose, id]);
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div
        className="evidence-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Evidence details"
        ref={drawerRef}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="drawer-head">
          <div>
            <span className="eyebrow">
              <FileSearch size={14} /> Evidence inspection
            </span>
            <h2>{id}</h2>
          </div>
          <button
            className="icon-button"
            ref={closeRef}
            aria-label="Close evidence"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        {recordedControls && (
          <div className="recorded-source-controls">
            <p>
              {recordedControls.hiddenByFilters
                ? 'Hidden by filters'
                : 'Visible in recorded evidence'}
            </p>
            {recordedControls.hiddenByFilters && (
              <button
                className="button secondary"
                onClick={() => {
                  // Reveal removes this control; retain focus on a stable modal action.
                  closeRef.current?.focus();
                  revealedRef.current = true;
                  recordedControls.onReveal();
                }}
              >
                Reveal source
              </button>
            )}
            <button
              className="button secondary"
              disabled={recordedControls.pinDisabled}
              title={recordedControls.pinMessage ?? undefined}
              onClick={() => {
                closeRef.current?.focus();
                recordedControls.onTogglePin();
              }}
            >
              {recordedControls.pinned ? 'Unpin source' : 'Pin source'}
            </button>
            {recordedControls.pinMessage && <p role="status">{recordedControls.pinMessage}</p>}
          </div>
        )}
        {error ? (
          <p className="error-banner">{error}</p>
        ) : !evidence ? (
          <div className="loading-row">
            <Spinner /> Retrieving persisted evidence…
          </div>
        ) : (
          <>
            <div className="drawer-meta">
              <Badge tone="teal">{evidence.kind}</Badge>
              <span>{evidence.service}</span>
            </div>
            <p className="evidence-summary">{evidence.summary}</p>
            <p className="mono muted">{evidence.timestamp} · UTC</p>
            <div className="safety-note">
              <FileSearch size={16} />
              <span>
                Immutable synthetic source record. Telemetry is untrusted data, never an
                instruction.
              </span>
            </div>
            {typeof evidence.data.content === 'string' && (
              <pre className="runbook-content">{evidence.data.content}</pre>
            )}
            <h3>Structured source</h3>
            <pre className="json-source">{JSON.stringify(evidence.data, null, 2)}</pre>
          </>
        )}
      </div>
    </div>
  );
}
