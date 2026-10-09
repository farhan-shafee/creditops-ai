# Deployment

The intended production-shaped topology is Vercel for Next.js, a dedicated FastAPI container service on Render/Railway/Fly, and a dedicated Neon PostgreSQL database. All data remains synthetic. Public operation uses `TELEMETRY_MODE=persisted` and checked-in replay artifacts; Kafka and Grafana are unnecessary in the cloud.

At implementation time Vercel and Neon connectors were accessible and searches found no dedicated CreditOps projects. No container-host credentials were available. No external project or paid resource was created, and no cloud URL is claimed. The local stack and deployment configuration are validated separately in `FINAL_REPORT.md`.

## Backend first

1. Create a dedicated Neon project/database for CreditOps AI within an approved plan. Enable pgvector with `CREATE EXTENSION IF NOT EXISTS vector;`. Obtain the connection string through the platform's secret UI; never paste it into Git or the frontend.
2. Use the Render blueprint at `infra/render.yaml` with `infra/docker/api.Dockerfile`. Point it at the existing private GitHub repository and select the dedicated CreditOps service. For Railway, keep the service source at the repository root, set `RAILWAY_DOCKERFILE_PATH=/infra/docker/api.Dockerfile`, and configure health path `/health`, timeout 120 seconds and an on-failure restart policy in the dedicated service settings. These follow [Railway's custom Dockerfile instructions](https://docs.railway.com/builds/dockerfiles). Do not assume the optional `infra/railway.toml` is discovered automatically; its absolute config path must be selected explicitly in a service that supports it. See [Railway's monorepo settings](https://docs.railway.com/deployments/monorepo). Plans/resources need explicit cost review; configuration is not an instruction to purchase a paid plan automatically.
3. Set server-side `DATABASE_URL` using PostgreSQL connection parameters and `DATABASE_REQUIRE_SSL=true`. Set `TELEMETRY_MODE=persisted`, `PUBLIC_DEMO=true`, and configure CORS only for the eventual console origin. Leave provider keys and `ADMIN_API_KEY` unset for public replay. Public demo mode blocks paid query embeddings even if optional embedding settings are present.
4. Run migrations and idempotent seed in the dedicated service environment:

```sh
python -m alembic upgrade head
python scripts/seed.py
```

5. Ensure `data/replay/INC-DEMO-001.json` through `003.json` and `artifacts/eval/latest.json` are included in the image. The committed artifacts are ready for keyless replay. To regenerate, run `python scripts/evaluate.py` in an isolated development/evaluation store and deploy the reviewed artifacts.
6. The container entrypoint honors `PORT`; health check `/health` must return 200 and actual database connectivity.

Optional Railway CLI workflow, run from the repository root after creating and configuring the dedicated service as above:

```sh
railway login
railway link
railway up
# Or use Render's reviewed blueprint from the dashboard.
```

Verify the exact selected project before `railway up`. Do not modify unrelated existing projects. Do not print credentials or commit platform-generated secret files.

## Vercel frontend

Import the existing private repository in Vercel as a dedicated CreditOps project. Set **Root Directory** to `apps/web`, framework Next.js, and keep the repository private. pnpm discovers the workspace lockfile. Configure these settings in the dedicated Vercel project; no `vercel.json` is required.

Set server-side `API_BASE_URL=https://YOUR-DEDICATED-BACKEND` for the deployment environment. No model key or admin key belongs in `NEXT_PUBLIC_*` configuration. Run the following commands from the repository root so the workspace lockfile, overrides and patches remain available, following [Vercel's monorepo CLI instructions](https://vercel.com/docs/monorepos):

```sh
pnpm dlx vercel login
pnpm dlx vercel link
pnpm dlx vercel env add API_BASE_URL production
pnpm dlx vercel deploy --prod
```

Enter the backend URL at the environment prompt. Review the selected scope/project before deploying. A standalone frontend with an unreachable backend is not a completed deployment.

## Verify the actual deployed flow

```sh
curl -fsS https://YOUR-DEDICATED-BACKEND/health
curl -fsS https://YOUR-DEDICATED-BACKEND/api/scenarios
```

Visit the frontend and run all three scenarios, SSE replay completion, evidence clicks and reset. Confirm the replay label and synthetic-data disclaimer. Run Playwright with the project-supported base URL option, and record the real URLs, deployment commit and results. Use provider logs for actual failures; do not infer success from a build alone.

## Protected live mode

Set an unpredictable `ADMIN_API_KEY`, a provider API key and an explicit model only on the API server. Configure investigation/window/timeouts and explicit price variables if desired. Call:

```text
POST /api/investigations
Authorization: Bearer <server-admin-key>
X-Demo-Session: <your-demo-session-uuid>
Content-Type: application/json
{"incident_id":"INC-DEMO-001","mode":"LIVE_AI"}
```

Do not expose unrestricted live model calls in the public console. A shared rate budget and durable workers are required before multiple API replicas. The root deterministic evaluation command makes no model calls; `--provider openai` or `anthropic` does and must be deliberately authorized/configured.

## Institutional changes

This deployment remains a synthetic portfolio demo. Enterprise identity, entitlement-aware diagnostics, durable jobs, distributed rate limiting, retention, independent evaluations and monitored audit controls are required before connecting real institutional data.
