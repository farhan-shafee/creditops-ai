import type { Evidence } from './types';
import type { RecordingIdentity } from './recorded-evidence';
export type PersonalState = { note: string; pinnedIds: readonly string[] };
export type NotesScope = RecordingIdentity & { sessionId: string };
export type NotesStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem' | 'key' | 'length'>;
export type NotesResult = {
  state: PersonalState;
  status: 'stored' | 'empty' | 'memory-only' | 'invalid';
  message: string | null;
};
export const INCIDENT_NOTES_CLEARED_EVENT = 'creditops-workspace:incident-notes-cleared';
const namespace = 'creditops-workspace:v1:';
const empty = (): PersonalState => ({ note: '', pinnedIds: [] });
const warning =
  'Tab storage is unavailable. Personal edits remain in memory and will be lost on refresh or when this record closes.';
export function browserNotesStorage(): NotesStorage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}
export function notesKey(scope: NotesScope): string {
  const parts = [scope.sessionId, scope.incidentId, scope.sourceSha256, scope.exportedAt];
  if (parts.some((part) => typeof part !== 'string' || !part.trim())) return '';
  try {
    return namespace + parts.map(encodeURIComponent).join(':');
  } catch {
    return '';
  }
}
function valid(value: unknown, sources: ReadonlyMap<string, Evidence>): value is PersonalState {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const state = value as PersonalState;
  return (
    Object.keys(value).length === 2 &&
    typeof state.note === 'string' &&
    state.note.length <= 4000 &&
    Array.isArray(state.pinnedIds) &&
    state.pinnedIds.length <= 20 &&
    state.pinnedIds.every((id) => typeof id === 'string' && sources.has(id)) &&
    new Set(state.pinnedIds).size === state.pinnedIds.length
  );
}
export function loadNotes(
  storage: NotesStorage | null,
  scope: NotesScope,
  sources: ReadonlyMap<string, Evidence>,
): NotesResult {
  const key = notesKey(scope);
  if (!storage || !key) return { state: empty(), status: 'memory-only', message: warning };
  let raw: string | null;
  try {
    raw = storage.getItem(key);
  } catch {
    return { state: empty(), status: 'memory-only', message: warning };
  }
  if (raw === null) return { state: empty(), status: 'empty', message: null };
  try {
    const state: unknown = JSON.parse(raw);
    if (!valid(state, sources)) throw Error('Invalid entry');
    return { state, status: 'stored', message: null };
  } catch {
    return {
      state: empty(),
      status: 'invalid',
      message:
        'This stored entry is invalid. Clear the current record before editing; it has not been truncated or repaired.',
    };
  }
}
export function saveNotes(
  storage: NotesStorage | null,
  scope: NotesScope,
  state: PersonalState,
  sources: ReadonlyMap<string, Evidence>,
): NotesResult {
  if (!valid(state, sources))
    return {
      state: empty(),
      status: 'invalid',
      message: 'Personal state exceeds its bounds or contains unavailable or duplicate sources.',
    };
  const retained = { note: state.note, pinnedIds: [...state.pinnedIds] };
  const key = notesKey(scope);
  if (storage && key) {
    try {
      storage.setItem(key, JSON.stringify(retained));
      return { state: retained, status: 'stored', message: null };
    } catch {}
  }
  return { state: retained, status: 'memory-only', message: warning };
}
export function clearNotes(storage: NotesStorage | null, scope: NotesScope): boolean {
  const key = notesKey(scope);
  if (!storage || !key) return false;
  try {
    storage.removeItem(key);
    return true;
  } catch {
    return false;
  }
}
export function clearIncidentNotes(
  storage: NotesStorage | null,
  sessionId: string,
  incidentId: string,
): boolean {
  if (!storage || !sessionId.trim() || !incidentId.trim()) return false;
  try {
    const matches: string[] = [];
    for (let index = 0; index < storage.length; index++) {
      const key = storage.key(index);
      if (!key?.startsWith(namespace)) continue;
      const parts = key.slice(namespace.length).split(':');
      if (parts.length !== 4) continue;
      let decoded: string[];
      try {
        decoded = parts.map(decodeURIComponent);
      } catch {
        continue;
      }
      const scope = {
        sessionId: decoded[0],
        incidentId: decoded[1],
        sourceSha256: decoded[2],
        exportedAt: decoded[3],
      };
      if (
        notesKey(scope) === key &&
        scope.sessionId === sessionId &&
        scope.incidentId === incidentId
      )
        matches.push(key);
    }
    for (const key of matches) storage.removeItem(key);
    return true;
  } catch {
    return false;
  }
}
