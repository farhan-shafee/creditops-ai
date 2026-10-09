import type { Investigation, Step } from './types';
import { readStorage, writeStorage } from './storage';

let cachedSession: string | undefined;

export function sessionId(): string {
  if (cachedSession) return cachedSession;
  const key = 'creditops-demo-session';
  const existing = readStorage(key);
  if (existing && /^[0-9a-f-]{36}$/i.test(existing)) {
    cachedSession = existing;
    return existing;
  }
  const id = crypto.randomUUID();
  cachedSession = id;
  writeStorage(key, id);
  return id;
}

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Demo-Session': sessionId(),
      ...options?.headers,
    },
    cache: 'no-store',
  });
  if (!response.ok) {
    const payload = await response
      .json()
      .catch(() => ({ detail: `Request failed (${response.status})` }));
    throw new Error(
      typeof payload.detail === 'string' ? payload.detail : `Request failed (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}

export async function streamInvestigation(
  id: string,
  onStep: (step: Step) => void,
  onComplete: (value: Investigation) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(`/api/investigations/${encodeURIComponent(id)}/events`, {
    headers: { 'X-Demo-Session': sessionId() },
    signal,
  });
  if (!response.ok || !response.body)
    throw new Error(`Investigation stream unavailable (${response.status})`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let completed = false;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
    let boundary: number;
    while ((boundary = buffer.indexOf('\n\n')) >= 0) {
      const event = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const name = event
        .split('\n')
        .find((line) => line.startsWith('event:'))
        ?.slice(6)
        .trim();
      const data = event
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trim())
        .join('\n');
      if (!data) continue;
      if (name === 'step') onStep(JSON.parse(data) as Step);
      if (name === 'complete') {
        completed = true;
        onComplete(JSON.parse(data) as Investigation);
      }
      if (name === 'error') throw new Error((JSON.parse(data) as { message: string }).message);
    }
  }
  if (!completed && !signal.aborted)
    throw new Error('Investigation stream ended before completion. Try again.');
}
