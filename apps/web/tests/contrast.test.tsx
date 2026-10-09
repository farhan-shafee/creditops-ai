import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

function luminance(hex: string): number {
  const channels = hex
    .match(/../g)!
    .map((value) => parseInt(value, 16) / 255)
    .map((value) => (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4));
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}
test('muted operational labels meet the 4.5:1 small-text contrast threshold', () => {
  const css = readFileSync(new URL('../src/app/globals.css', import.meta.url), 'utf8');
  const token = (name: string) => css.match(new RegExp(`--${name}:\\s*#([0-9a-f]{6})`))![1];
  for (const name of ['muted', 'quiet']) {
    const ratio = (luminance(token(name)) + 0.05) / (luminance(token('panel')) + 0.05);
    assert.ok(ratio >= 4.5, `${name} contrast ${ratio.toFixed(2)}:1 is below 4.5:1`);
  }
});
