import type { NextConfig } from 'next';
import path from 'node:path';

const config: NextConfig = {
  output: 'standalone',
  outputFileTracingRoot: path.join(import.meta.dirname, '../..'),
  poweredByHeader: false,
  devIndicators: false,
  async headers() {
    const cacheRevalidation = [{ key: 'Cache-Control', value: 'public, max-age=0, must-revalidate' }];
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
          { key: 'Strict-Transport-Security', value: 'max-age=63072000' },
          {
            key: 'Content-Security-Policy',
            value:
              "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
          },
        ],
      },
      {
        source: '/',
        headers: cacheRevalidation,
      },
      {
        // Next.js prerenders these one-segment views; exclude the /health route
        // so its no-store response is not made cacheable.
        source: '/:view((?!health$)[a-z0-9-]+)',
        headers: cacheRevalidation,
      },
    ];
  },
};
export default config;
