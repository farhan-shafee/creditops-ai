"""Opt-in official embeddings + pgvector retrieval; absence falls back to lexical.

Index creation is an explicit offline operation. Public retrieval never builds an
index, changes records, or exposes model credentials. Query embeddings require
EMBEDDINGS_ENABLED, an explicit model name, and a server-side API key.
"""

import json
import logging
import math

from openai import AsyncOpenAI
from sqlalchemy import text

from .settings import get_settings

LOGGER = logging.getLogger("creditops.embeddings")


def vector_literal(vector: list[float]) -> str:
    if len(vector) != 1536 or any(
        not isinstance(value, (int, float)) or not math.isfinite(value) for value in vector
    ):
        raise ValueError("Embedding must contain 1536 finite numeric values")
    return json.dumps(vector, separators=(",", ":"))


async def query_references(store, kind: str, q: str, limit: int = 10) -> list[tuple[str, float]]:
    settings = get_settings()
    if (
        settings.public_demo
        or not settings.embeddings_enabled
        or not settings.embedding_model
        or not settings.openai_api_key
        or not store.database_url.startswith("postgresql")
    ):
        return []
    if settings.embedding_dimensions != 1536:
        raise ValueError("The current pgvector migration indexes 1536 dimensions")
    try:
        async with store.sessions() as session:
            has_index = await session.scalar(text("SELECT to_regclass('reference_embeddings') IS NOT NULL"))
            if not has_index:
                return []
            available = await session.scalar(
                text("SELECT count(*) FROM reference_embeddings WHERE kind=:kind AND model=:model"),
                {"kind": kind, "model": settings.embedding_model},
            )
            if not available:
                return []
        async with AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(), timeout=5, max_retries=0
        ) as client:
            response = await client.embeddings.create(
                model=settings.embedding_model, input=q[:240], dimensions=1536
            )
        literal = vector_literal(response.data[0].embedding)
        async with store.sessions() as session:
            rows = await session.execute(
                text(
                    "SELECT evidence_id, 1 - (embedding <=> CAST(:vector AS vector)) AS similarity "
                    "FROM reference_embeddings WHERE kind=:kind AND model=:model "
                    "ORDER BY embedding <=> CAST(:vector AS vector) LIMIT :limit"
                ),
                {"vector": literal, "kind": kind, "model": settings.embedding_model, "limit": min(limit, 50)},
            )
            return [(row.evidence_id, float(row.similarity)) for row in rows]
    except Exception:
        LOGGER.warning("optional_vector_retrieval_unavailable_using_lexical")
        return []


async def index_references(store) -> int:
    settings = get_settings()
    if settings.public_demo:
        raise ValueError("Embedding indexing is disabled in the public demo")
    if (
        not settings.openai_api_key
        or not settings.embedding_model
        or not store.database_url.startswith("postgresql")
    ):
        raise ValueError(
            "Indexing requires PostgreSQL, OPENAI_API_KEY and an explicitly configured EMBEDDING_MODEL"
        )
    if settings.embedding_dimensions != 1536:
        raise ValueError("The current pgvector migration indexes 1536 dimensions")
    records = [
        *await store.evidence("embedding-index", kind="runbook"),
        *await store.evidence("embedding-index", kind="history"),
    ]
    async with AsyncOpenAI(
        api_key=settings.openai_api_key.get_secret_value(), timeout=30, max_retries=0
    ) as client:
        response = await client.embeddings.create(
            model=settings.embedding_model,
            input=[(record.summary + "\n" + json.dumps(record.data))[:12000] for record in records],
            dimensions=1536,
        )
    async with store.sessions.begin() as session:
        for record, embedding in zip(records, response.data, strict=True):
            await session.execute(
                text(
                    "INSERT INTO reference_embeddings(evidence_id,kind,model,embedding) "
                    "VALUES (:id,:kind,:model,CAST(:vector AS vector)) "
                    "ON CONFLICT(evidence_id) DO UPDATE SET embedding=EXCLUDED.embedding,model=EXCLUDED.model,created_at=CURRENT_TIMESTAMP"
                ),
                {
                    "id": record.id,
                    "kind": record.kind,
                    "model": settings.embedding_model,
                    "vector": vector_literal(embedding.embedding),
                },
            )
    return len(records)
