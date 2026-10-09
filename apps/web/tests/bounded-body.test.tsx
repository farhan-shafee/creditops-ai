import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readBoundedBody, RequestBodyTooLargeError } from '../src/lib/bounded-body';

test('the proxy rejects and cancels an oversized streamed body without relying on content-length', async () => {
  let cancelled = false;
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new Uint8Array(6));
      controller.enqueue(new Uint8Array(6));
    },
    cancel() {
      cancelled = true;
    },
  });
  await assert.rejects(readBoundedBody(body, 8), RequestBodyTooLargeError);
  assert.equal(cancelled, true);
});

test('the proxy preserves valid streamed payload bytes up to the exact bound', async () => {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode('{"ok":'));
      controller.enqueue(encoder.encode('true}'));
      controller.close();
    },
  });
  assert.equal(new TextDecoder().decode(await readBoundedBody(body, 11)), '{"ok":true}');
});

test('an empty body remains empty', async () => {
  assert.equal((await readBoundedBody(null)).byteLength, 0);
});
