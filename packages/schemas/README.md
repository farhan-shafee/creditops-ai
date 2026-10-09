# Shared JSON contracts

`python scripts/export_schemas.py` exports the actual Pydantic Evidence, Incident, Investigation and Assessment schemas here. These are language-neutral contracts for MCP/API consumers. FastAPI's `/openapi.json` remains the route contract. Frontend types match `docs/API_CONTRACT.md` and are verified by real E2E requests.

Schema generation is deterministic. No credentials, evaluation ground-truth labels or private model reasoning are included.
