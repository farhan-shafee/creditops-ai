import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import {
  notesKey,
  loadNotes,
  saveNotes,
  clearNotes,
  clearIncidentNotes,
  type NotesStorage,
} from '../src/lib/workspace-notes';
import { loadRecordedFixture } from './recorded-fixtures';
const sources = new Map(loadRecordedFixture('INC-DEMO-001').evidence.map((e) => [e.id, e]));
const scope = {
  sessionId: 's:/%',
  incidentId: 'INC-DEMO-001',
  sourceSha256: 'sha',
  exportedAt: 'time',
};
function storage(): NotesStorage {
  const data = new Map<string, string>();
  return {
    get length() {
      return data.size;
    },
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => {
      data.set(k, v);
    },
    removeItem: (k) => {
      data.delete(k);
    },
    key: (i) => [...data.keys()][i] ?? null,
  };
}
test('notes_scope_bounds_and_storage_failure', () => {
  const db = storage(),
    ids = [...sources.keys()].slice(0, 20),
    state = { note: '<img src=x onerror=alert(1)>', pinnedIds: ids };
  const versions = [
    scope,
    { ...scope, sessionId: 'other' },
    { ...scope, incidentId: 'other' },
    { ...scope, sourceSha256: 'other' },
    { ...scope, exportedAt: 'other' },
  ];
  assert.equal(new Set(versions.map(notesKey)).size, 5);
  assert.equal(notesKey({ ...scope, sourceSha256: '' }), '');
  assert.equal(loadNotes(db, scope, sources).status, 'empty');
  assert.equal(saveNotes(db, scope, state, sources).status, 'stored');
  assert.deepEqual(loadNotes(db, scope, sources).state, state);
  for (const other of versions.slice(1))
    assert.equal(loadNotes(db, other, sources).status, 'empty');
  assert.equal(
    saveNotes(db, scope, { note: 'x'.repeat(4000), pinnedIds: ids }, sources).status,
    'stored',
  );
  for (const bad of [
    { note: 'x'.repeat(4001), pinnedIds: [] },
    { note: '', pinnedIds: ['absent'] },
    { note: '', pinnedIds: [ids[0], ids[0]] },
    { note: '', pinnedIds: Array(21).fill(ids[0]) },
  ])
    assert.equal(saveNotes(db, scope, bad, sources).status, 'invalid');
  assert.equal(saveNotes(null, scope, state, sources).status, 'memory-only');
  const denied = {
    ...db,
    getItem() {
      throw Error('denied');
    },
    setItem() {
      throw Error('full');
    },
  };
  assert.equal(loadNotes(denied, scope, sources).status, 'memory-only');
  for (const error of [new SyntaxError('denied'), new Error('Invalid entry')])
    assert.equal(
      loadNotes(
        {
          ...denied,
          getItem() {
            throw error;
          },
        },
        scope,
        sources,
      ).status,
      'memory-only',
    );
  assert.deepEqual(saveNotes(denied, scope, state, sources).state, state);
  assert.match(saveNotes(denied, scope, state, sources).message!, /refresh/i);
  for (const bad of [
    '{',
    'null',
    JSON.stringify({ note: 12, pinnedIds: [] }),
    JSON.stringify({ note: 'x', pinnedIds: ['other-record'] }),
  ]) {
    db.setItem(notesKey(scope), bad);
    assert.equal(loadNotes(db, scope, sources).status, 'invalid');
    assert.equal(clearNotes(db, scope), true);
    assert.equal(loadNotes(db, scope, sources).status, 'empty');
  }
});
test('notes_reset_is_captured_and_success_only', () => {
  const db = storage(),
    state = { note: 'keep', pinnedIds: [] };
  for (const version of [
    scope,
    { ...scope, exportedAt: 'v2' },
    { ...scope, sessionId: 'other' },
    { ...scope, incidentId: 'other' },
  ])
    saveNotes(db, version, state, sources);
  db.setItem(notesKey(scope) + ':extra', 'unrelated');
  db.setItem('creditops-workspace:v2:' + notesKey(scope), 'unrelated');
  assert.equal(clearIncidentNotes(db, scope.sessionId, scope.incidentId), true);
  assert.equal(loadNotes(db, scope, sources).status, 'empty');
  assert.equal(loadNotes(db, { ...scope, exportedAt: 'v2' }, sources).status, 'empty');
  assert.equal(loadNotes(db, { ...scope, sessionId: 'other' }, sources).status, 'stored');
  assert.equal(loadNotes(db, { ...scope, incidentId: 'other' }, sources).status, 'stored');
  assert.equal(db.getItem(notesKey(scope) + ':extra'), 'unrelated');
  assert.equal(clearIncidentNotes(null, scope.sessionId, scope.incidentId), false);
  const code = readFileSync(new URL('../src/components/console.tsx', import.meta.url), 'utf8');
  const reset = code.slice(
    code.indexOf('const reset = async'),
    code.indexOf('const investigate = async'),
  );
  assert.ok(reset.indexOf('const resetting') < reset.indexOf('stopInvestigation('));
  assert.ok(reset.indexOf('const resetSession') < reset.indexOf('stopInvestigation('));
  assert.ok(reset.indexOf('cleanPersonalScope') > reset.indexOf("method: 'POST'"));
});
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { PersonalWorkspacePanel } from '../src/components/personal-workspace-panel';
import { EvidenceDrawer } from '../src/components/evidence-drawer';
test('personal_note_and_hostile_log_are_escaped_plain_text', () => {
  const hostile = '<script>alert("untrusted")</script>';
  const notes = {
    result: { state: { note: hostile, pinnedIds: [] }, status: 'stored' as const, message: null },
    ready: true,
    update: () => {},
    togglePin: () => {},
    clear: () => {},
  };
  const html = renderToStaticMarkup(<PersonalWorkspacePanel notes={notes} onEvidence={() => {}} />);
  assert.ok(html.includes('&lt;script&gt;'));
  assert.ok(!html.includes('<script>'));
  const source = {
    ...sources.values().next().value!,
    summary: hostile,
    data: { content: hostile },
  };
  const drawer = renderToStaticMarkup(
    <EvidenceDrawer id={source.id} evidence={source} error={null} onClose={() => {}} />,
  );
  assert.ok(drawer.includes('&lt;script&gt;'));
  assert.ok(!drawer.includes('<script>'));
});
test('notes_removal_denial_retains_scope_for_safe_retry', () => {
  const db = storage(),
    state = { note: 'retained', pinnedIds: [...sources.keys()].slice(0, 1) };
  const other = { ...scope, incidentId: 'unrelated' };
  saveNotes(db, scope, state, sources);
  saveNotes(db, { ...scope, exportedAt: 'version-two' }, state, sources);
  saveNotes(db, other, state, sources);
  const denied = {
    ...db,
    removeItem() {
      throw Error('denied');
    },
  };
  assert.equal(clearIncidentNotes(denied, scope.sessionId, scope.incidentId), false);
  assert.deepEqual(loadNotes(db, scope, sources).state, state);
  assert.equal(clearIncidentNotes(db, scope.sessionId, scope.incidentId), true);
  assert.equal(loadNotes(db, scope, sources).status, 'empty');
  assert.equal(loadNotes(db, { ...scope, exportedAt: 'version-two' }, sources).status, 'empty');
  assert.deepEqual(loadNotes(db, other, sources).state, state);
});
