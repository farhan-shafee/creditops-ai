"""No external embeddings are called in unit tests."""

import pytest
from creditops.embeddings import query_references, vector_literal


@pytest.mark.parametrize("vector", [[], [0.0] * 1535, [float("nan")] * 1536, [float("inf")] * 1536])
def test_invalid_embedding_vectors_are_rejected_before_sql(vector):
    with pytest.raises(ValueError, match="1536 finite"):
        vector_literal(vector)


async def test_unconfigured_embeddings_use_lexical_without_external_calls():
    class SQLiteStore:
        database_url = "sqlite+aiosqlite:///:memory:"

    assert await query_references(SQLiteStore(), "runbook", "Kafka backlog") == []


async def test_public_demo_never_opens_embedding_index_or_external_sdk(monkeypatch):
    from creditops import embeddings
    from creditops.settings import Settings

    settings = Settings(
        public_demo=True,
        embeddings_enabled=True,
        embedding_model="synthetic-test-model",
        openai_api_key="synthetic-test-key",
    )
    monkeypatch.setattr(embeddings, "get_settings", lambda: settings)

    class RestrictedStore:
        database_url = "postgresql+asyncpg://synthetic"
        index_reads = 0

        def sessions(self):
            self.index_reads += 1
            raise RuntimeError("Public retrieval must not open the paid embedding query path")

    store = RestrictedStore()
    assert await query_references(store, "runbook", "consumer lag") == []
    assert store.index_reads == 0
