# Deployment handoff — approval required, no deployment performed

The intended topology remains a dedicated Next.js frontend on Vercel, a dedicated FastAPI container service on Render/Railway/Fly and a dedicated Neon PostgreSQL database. All data is synthetic. This handoff packages the three reviewed recordings in `data/showcase`; it does not create hosting resources, deploy, change DNS or claim a public URL.

The next owner decision is **which dedicated hosting accounts, resources and plans to approve, with explicit cost limits**. Required access is the private-repository integration for the selected hosts, API-host credentials and a dedicated database connection secret. No current hosting prices, free-tier availability, sleeping-service behavior or plan capacity have been verified in this milestone. The Render blueprint deliberately omits a plan selection; review the current plan and operating costs before creating anything. Original estimated model usage is not hosting cost or confirmed billing.

## Reviewed package and local smoke check

Run from the repository root after installing dependencies as described in `README.md`:

```sh
pnpm showcase
```

Open `http://127.0.0.1:3000`. The launcher uses the existing development process cleanup, selects `data/showcase`, initializes `artifacts/runtime/showcase.db`, sets persisted telemetry, disables dotenv with `CREDITOPS_ENV_FILE=''`, removes inherited provider/admin keys and forces the public profile. It neither reads the original local receipt directory nor regenerates any assessment.

The committed files are `data/showcase/INC-DEMO-001.json`, `INC-DEMO-002.json`, `INC-DEMO-003.json` and `manifest.json`. The manifest records the allowlisted original receipt, source SHA-256, source commit, export version/time and documented redactions for each derivative. Receipt hashes are provenance/integrity values, not credential fingerprints. Original proposals, validation, assessments, evidence IDs and observation times stay separate and intact.

The owner-only exporter is `python scripts/export_showcase.py`; its defaults are `--source-directory artifacts/live-verification --output-directory data/showcase`. Visitors and deployed services need only the packaged derivatives. Do not run `scripts/evaluate.py` to regenerate these recordings: that command produces the separate deterministic benchmark/replay series.

## Dedicated API image

Build from the repository root:

```sh
docker build -f infra/docker/api.Dockerfile -t creditops-ai-api:showcase .
```

The image copies committed `data`, including the exact showcase directory at `/app/data/showcase`, plus historical evaluation/robustness artifacts. It excludes local raw receipts and approvals, test outputs, runtime databases and dotenv files. The image defaults to `REPLAY_DIR=/app/data/showcase`, `PUBLIC_DEMO=true`, `EMBEDDINGS_ENABLED=false`, `TELEMETRY_MODE=persisted` and `CREDITOPS_ENV_FILE=''`.

The container's exact start command is:

```sh
python -m alembic upgrade head && exec python -m uvicorn creditops.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

App startup initializes the existing synthetic fixtures. Migrations and startup must target only the dedicated CreditOps database. Use `infra/render.yaml` or the existing `infra/railway.toml` as reviewed configuration after the resource/plan decision; verify the chosen host actually selects `infra/docker/api.Dockerfile` with repository-root build context and `/health` as the health path.

| API configuration | Required value / handling |
|---|---|
| `DATABASE_URL` | Secret async PostgreSQL URL for the dedicated database; provide through the host's secret UI |
| `DATABASE_REQUIRE_SSL` | `true` for the hosted dedicated PostgreSQL connection |
| `REPLAY_DIR` | `/app/data/showcase` |
| `PUBLIC_DEMO` | `true`; API denies paid `LIVE_AI` and query embeddings even if an accidental credential is present |
| `EMBEDDINGS_ENABLED` | `false` |
| `TELEMETRY_MODE` | `persisted`; cloud Kafka/Grafana are unnecessary for replay |
| `CREDITOPS_ENV_FILE` | Explicitly empty; never upload the owner's `.env` |
| `CORS_ORIGINS` | Only the eventual dedicated frontend HTTPS origin |
| `PORT` | Host-supplied port, default `8000` |
| Provider API keys / `ADMIN_API_KEY` | Absent from the public showcase |

The database must be a dedicated CreditOps schema/database, with a dedicated application login and TLS. The existing local PostgreSQL initializer includes pgvector; paid embedding queries remain disabled. No public MCP endpoint or remote shell capability is needed. The API has a read-only diagnostic allowlist, request limits and UUID-scoped synthetic sessions. Its in-memory rate limiter needs a shared store and durable job design before multiple replicas.

## Dedicated frontend

Use a separate Vercel project connected to the existing **private** repository, with project root `apps/web` and the workspace lockfile available. Build/install commands run from the repository root:

```sh
pnpm install --frozen-lockfile
pnpm --filter @creditops/web build
```

Set only server-side `API_BASE_URL=https://YOUR-DEDICATED-BACKEND` for the intended environment. Never put a database, model or admin secret in `NEXT_PUBLIC_*`. The ordinary Node start command is `pnpm --filter @creditops/web start`; the existing standalone frontend image starts with `node apps/web/server.js`. The API and frontend must both be reachable for the demo to work.

Private GitHub source access is optional for a visitor to understand the eventual hosted demo. Label any repository link **Private source — access required**. Do not present it as a publicly readable code link or change repository visibility.

## Post-deployment smoke checks, after separate owner approval

Record the deployment commit, actual API/frontend URLs and observed checks; a local build does not establish cloud success.

```sh
curl -fsS https://YOUR-DEDICATED-BACKEND/health
curl -fsS https://YOUR-DEDICATED-BACKEND/api/scenarios
```

Then verify all three **View recorded investigation** choices in a fresh browser session:

1. Pricing backlog, FIX session instability and database pool exhaustion load their matching source/provenance, complete playback and keep their original proposal, validation and assessment distinct.
2. Evidence links open the recorded object with the original timestamp; the complete recorded snapshot and sample coverage are visible. Samples ending at 14:02:24 UTC do not establish health at the 15:00 UTC cutoff.
3. Refresh, completion and reset work; two independent sessions do not overwrite one another. Desktop and mobile views keep the main action, business state and review notes usable.
4. Direct `POST /api/investigations` requests using `mode=LIVE_AI` are denied under `PUBLIC_DEMO=true`, including a fake credential canary; query embeddings are disabled. Confirm playback does not construct a model client or invoke fresh MCP diagnostics.
5. Missing/malformed showcase artifacts fail visibly and do not substitute a deterministic recording. Confirm synthetic/recorded/human-review labels, original versus playback durations and separate model/rule scores.

Keep the existing 15-case benchmark and 13-case developer-authored robustness outputs separate from these selected recordings. Institutional use would require enterprise identity and entitlements, tenant-aware diagnostics, durable jobs, shared budgets/rate limits, audit monitoring, retention and independently held-out evaluation. No provider or cloud mutation is authorized by this handoff.
