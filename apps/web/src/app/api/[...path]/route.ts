import { NextRequest } from 'next/server';
import { readBoundedBody, RequestBodyTooLargeError } from '@/lib/bounded-body';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 120;

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const allowed = new Set([
    'overview',
    'scenarios',
    'demo',
    'incidents',
    'logs',
    'metrics',
    'services',
    'telemetry',
    'evidence',
    'runbooks',
    'history',
    'evaluations',
    'investigations',
  ]);
  if (!allowed.has(path[0]) || path.some((segment) => segment === '..' || segment.includes('/')))
    return Response.json({ detail: 'Unknown API route' }, { status: 404 });
  const target = new URL(
    `/api/${path.map(encodeURIComponent).join('/')}`,
    process.env.API_BASE_URL ?? 'http://127.0.0.1:8000',
  );
  target.search = request.nextUrl.search;
  const headers = new Headers();
  for (const name of ['content-type', 'x-demo-session', 'authorization']) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  let body: ArrayBuffer | undefined;
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    const length = Number(request.headers.get('content-length'));
    if (length > 65_536)
      return Response.json({ detail: 'Request exceeds 64 KiB' }, { status: 413 });
    try {
      body = await readBoundedBody(request.body);
    } catch (error) {
      if (error instanceof RequestBodyTooLargeError)
        return Response.json({ detail: error.message }, { status: 413 });
      return Response.json({ detail: 'Unable to read request body' }, { status: 400 });
    }
  }
  const deadline = AbortSignal.timeout(105_000);
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
      cache: 'no-store',
      signal: AbortSignal.any([request.signal, deadline]),
    });
    const responseHeaders = new Headers({
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
    });
    for (const name of ['content-type', 'retry-after', 'x-accel-buffering']) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch {
    if (deadline.aborted)
      return Response.json(
        { detail: 'The diagnostic API request timed out. Retry the investigation.' },
        { status: 504 },
      );
    return Response.json(
      { detail: 'The diagnostic API is unavailable. Start the API service and retry.' },
      { status: 503 },
    );
  }
}
export const GET = proxy;
export const POST = proxy;
