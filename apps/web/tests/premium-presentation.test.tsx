import assert from 'node:assert/strict';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { ScenarioPreview } from '../src/components/scenario-preview';
const scenario = {
  id: 'db-pool-exhaustion',
  incident_id: 'INC-DEMO-003',
  title: 'Existing database scenario',
  description: 'Existing scenario metadata only.',
};
test('unloaded preview uses selected metadata and never a previous incident diagnosis', () => {
  const html = renderToStaticMarkup(
    <ScenarioPreview scenario={scenario} fallbackTitle="Selected scenario" state="unloaded" />,
  );
  assert.match(html, /INC-DEMO-003/);
  assert.match(html, /Existing scenario metadata only/);
  assert.match(html, /not loaded/);
  assert.doesNotMatch(html, /INC-DEMO-001|assessment|confidence|healthy telemetry/i);
});
test('preview keeps loading and restoring explicit without fabricating metadata', () => {
  for (const state of ['loading', 'restoring'] as const) {
    const html = renderToStaticMarkup(
      <ScenarioPreview fallbackTitle="Selected scenario" state={state} />,
    );
    assert.match(
      html,
      state === 'loading' ? /Loading selected recording/ : /Restoring selected recording/,
    );
    assert.match(html, /metadata unavailable/i);
    assert.doesNotMatch(html, /INC-DEMO-/);
  }
});
test('preview treats scenario text as inert display content', () => {
  const html = renderToStaticMarkup(
    <ScenarioPreview
      scenario={{
        ...scenario,
        title: '<img src=x onerror=alert(1)>',
        description: '<script>bad()</script>',
      }}
      fallbackTitle="Selected"
      state="unloaded"
    />,
  );
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>|<img src=x/);
});
