# Local infrastructure and deployment configuration

This environment is dedicated to synthetic CreditOps AI data. Every exposed Compose port binds to loopback. No broker, trading venue, financial institution or production system is connected.

```sh
docker compose -f infra/docker/compose.yml up -d --build
docker compose -f infra/docker/compose.yml ps
docker compose -f infra/docker/compose.yml logs api
```

| Component | Local endpoint | Purpose |
| --- | --- | --- |
| Next.js | http://127.0.0.1:13000 | Operations UI, proxied API |
| FastAPI | http://127.0.0.1:18000/docs | OpenAPI and diagnostic application |
| PostgreSQL | 127.0.0.1:15432 | Synthetic evidence, runs and pgvector extension |
| Redpanda Kafka | 127.0.0.1:19092 | Real local synthetic publication and consumption |
| Redpanda metrics | http://127.0.0.1:19644/public_metrics | Real broker measurements |
| Prometheus | http://127.0.0.1:19090 | API and Redpanda scrape targets |
| Grafana | http://127.0.0.1:13001 | Provisioned synthetic operations dashboard |

The API receives `TELEMETRY_MODE=kafka` and the internal `redpanda:9092` address. The public demo instead uses persisted synthetic telemetry with `TELEMETRY_MODE=persisted`; no paid Kafka service is required. Incident metrics represent the explicit simulated clock. API process, HTTP request and broker metrics measure the real local processes. The Grafana panel labels distinguish those measurements.

Compose's database/dashboard passwords are deliberately recognizable local-only defaults. They are not deployment credentials. The Grafana anonymous user has Viewer access and the login form is disabled. Never expose these disposable local services publicly.

The PostgreSQL initializer enables `vector` and provisions `creditops_diagnostics` as a NOLOGIN, SELECT-only role with read-only transactions. This role can be granted to a dedicated diagnostic login when adapting the project to institutional infrastructure. The application writer role persists demo runs; the MCP bridge has no database credentials and calls only allowlisted GET diagnostics.

`docker compose -f infra/docker/compose.yml down` stops this project's containers and preserves its volumes. Removing volumes resets the dedicated synthetic environment and loses its local demo records; use that only when you intend to reset this checkout's disposable database.

Docker is optional. The root `pnpm dev` launcher starts the Python API and Next.js on ports 8000/3000 using a SQLite development database. You can also run only the base services in Compose and point a host API at PostgreSQL/Redpanda with environment variables.

Deployment configuration is supplied as `infra/render.yaml` (Render blueprint) and `infra/railway.toml` (Railway configuration). Both use `infra/docker/api.Dockerfile`; it binds to the host's `PORT` environment variable. The frontend is a separate Vercel monorepo project rooted at `apps/web`. Configure its server-only `API_BASE_URL` to the dedicated API HTTPS URL. Neon uses an async PostgreSQL `DATABASE_URL`; external API credentials and the admin key stay only on the backend.

Deploying any template is a separate authorized external action and may incur provider charges. No cloud resource is created by these configuration files or local startup commands. See the root deployment documentation for the credential boundary and exact deployment steps.
