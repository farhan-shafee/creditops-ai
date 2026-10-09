export async function GET() {
  try {
    const response = await fetch(
      new URL('/health', process.env.API_BASE_URL ?? 'http://127.0.0.1:8000'),
      { cache: 'no-store', signal: AbortSignal.timeout(5000) },
    );
    return new Response(response.body, {
      status: response.status,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
    });
  } catch {
    return Response.json({ status: 'unavailable', service: 'api' }, { status: 503 });
  }
}
