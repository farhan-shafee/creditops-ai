import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { RecordedRecording } from '@/lib/recorded-evidence';
import {
  INCIDENT_NOTES_CLEARED_EVENT,
  browserNotesStorage,
  clearNotes,
  loadNotes,
  notesKey,
  saveNotes,
  type NotesResult,
  type PersonalState,
  type NotesScope,
} from '@/lib/workspace-notes';
import { Citation, Panel } from './primitives';
const initial: NotesResult = { state: { note: '', pinnedIds: [] }, status: 'empty', message: null };
export function useWorkspaceNotes(recording: RecordedRecording, sessionId: string | null) {
  const scope = useMemo<NotesScope>(
    () => ({
      incidentId: recording.identity?.incidentId ?? recording.incident.id,
      sourceSha256: recording.identity?.sourceSha256 ?? '',
      exportedAt: recording.identity?.exportedAt ?? '',
      sessionId: sessionId ?? '',
    }),
    [
      recording.identity?.incidentId,
      recording.identity?.sourceSha256,
      recording.identity?.exportedAt,
      recording.incident.id,
      sessionId,
    ],
  );
  const [result, setResult] = useState<NotesResult>(initial);
  const [ready, setReady] = useState(false);
  const sourcesRef = useRef(recording.sources);
  useEffect(() => {
    sourcesRef.current = recording.sources;
  }, [recording.sources]);
  useEffect(() => {
    const timer = setTimeout(() => {
      setResult(loadNotes(browserNotesStorage(), scope, sourcesRef.current));
      setReady(true);
    }, 0);
    return () => clearTimeout(timer);
  }, [scope]);
  useEffect(() => {
    const onCleared = (event: Event) => {
      const detail = (event as CustomEvent<{ sessionId?: unknown; incidentId?: unknown }>).detail;
      if (detail?.sessionId === scope.sessionId && detail.incidentId === scope.incidentId)
        setResult(initial);
    };
    window.addEventListener(INCIDENT_NOTES_CLEARED_EVENT, onCleared);
    return () => window.removeEventListener(INCIDENT_NOTES_CLEARED_EVENT, onCleared);
  }, [scope.sessionId, scope.incidentId]);
  const update = useCallback(
    (state: PersonalState) => {
      if (!ready || result.status === 'invalid') return;
      setResult(saveNotes(browserNotesStorage(), scope, state, recording.sources));
    },
    [ready, result.status, scope, recording.sources],
  );
  const togglePin = useCallback(
    (id: string) => {
      if (!recording.sources.has(id)) return;
      const pinned = result.state.pinnedIds.includes(id);
      if (!pinned && result.state.pinnedIds.length >= 20) return;
      update({
        ...result.state,
        pinnedIds: pinned
          ? result.state.pinnedIds.filter((value) => value !== id)
          : [...result.state.pinnedIds, id],
      });
    },
    [recording.sources, result.state, update],
  );
  const clear = () => {
    if (clearNotes(browserNotesStorage(), scope)) setResult(initial);
    else if (result.status === 'memory-only')
      setResult({
        state: { note: '', pinnedIds: [] },
        status: 'memory-only',
        message: notesKey(scope)
          ? 'Notes and pins cleared in memory. The stored entry could not be removed and may reappear after refresh. Tab storage remains unavailable; new edits will be lost on refresh.'
          : 'Notes and pins cleared in memory. Durable recording identity is unavailable; new edits will be lost on refresh.',
      });
    else
      setResult({
        ...result,
        status: result.status === 'invalid' ? 'invalid' : 'memory-only',
        message:
          result.status === 'invalid'
            ? 'Invalid stored entry could not be removed. Editing remains locked; retry Clear when tab storage is available.'
            : 'Could not clear the stored entry. Current personal state is retained; edits may be lost on refresh.',
      });
  };
  return { result, ready, update, togglePin, clear };
}
export function PersonalWorkspacePanel({
  notes,
  onEvidence,
}: {
  notes: ReturnType<typeof useWorkspaceNotes>;
  onEvidence: (id: string) => void;
}) {
  const { result, ready } = notes;
  return (
    <div data-testid="personal-workspace">
      <Panel title="Personal workspace" eyebrow="Tab-local · Unverified">
        <div className="padded personal-workspace-body">
          <p>
            Plain-text notes and returned-source pins are personal, unverified and local to this tab
            and recording. They are excluded from investigations and exports.
          </p>
          <label htmlFor="personal-note">Personal note</label>
          <textarea
            id="personal-note"
            maxLength={4000}
            rows={5}
            value={result.state.note}
            disabled={!ready || result.status === 'invalid'}
            onChange={(event) => notes.update({ ...result.state, note: event.target.value })}
          />
          <p>
            {result.state.note.length} / 4,000 characters · {result.state.pinnedIds.length} / 20
            pinned sources
          </p>
          <p role="status">
            {result.message ??
              (result.status === 'stored'
                ? 'Saved in this tab for this recording.'
                : 'No personal state saved for this recording.')}
          </p>
          <ul className="personal-pins">
            {result.state.pinnedIds.map((id) => (
              <li key={id}>
                <Citation id={id} onEvidence={onEvidence} />
                <button
                  className="button secondary"
                  onClick={() => notes.togglePin(id)}
                  aria-label={'Unpin ' + id}
                >
                  Unpin
                </button>
              </li>
            ))}
          </ul>
          <button
            data-testid="personal-clear"
            className="button secondary"
            onClick={notes.clear}
            disabled={!ready}
          >
            Clear current record notes and pins
          </button>
        </div>
      </Panel>
    </div>
  );
}
