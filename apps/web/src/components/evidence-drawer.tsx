import { useEffect, useRef } from 'react';
import { X, FileSearch } from 'lucide-react';
import type { Evidence } from '@/lib/types';
import { Badge, Spinner } from './primitives';

export function EvidenceDrawer({
  id,
  evidence,
  error,
  onClose,
}: {
  id: string;
  evidence: Evidence | null;
  error: string | null;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const prior = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key === 'Tab') {
        const items = drawerRef.current?.querySelectorAll<HTMLElement>(
          'button, a, input, summary, [tabindex="0"]',
        );
        if (!items?.length) return;
        const first = items[0],
          last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
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
      prior?.focus();
    };
  }, [onClose]);
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
