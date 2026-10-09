"""Optional pgvector reference embeddings; lexical retrieval remains available.

Revision ID: 20261009_pgvector
Revises: ec996f05f400
"""

import logging

from alembic import op
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

revision = "20261009_pgvector"
down_revision = "ec996f05f400"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return
    available = connection.execute(
        text("SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name='vector')")
    ).scalar()
    if not available:
        return
    try:
        with connection.begin_nested():
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except SQLAlchemyError:
        logging.getLogger("alembic").warning(
            "pgvector extension could not be enabled; lexical retrieval remains active"
        )
        return
    op.execute("""CREATE TABLE reference_embeddings (
        evidence_id VARCHAR(96) PRIMARY KEY REFERENCES evidence(id),
        kind VARCHAR(32) NOT NULL, model VARCHAR(96) NOT NULL,
        embedding vector(1536) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    op.execute("CREATE INDEX ix_reference_embeddings_kind ON reference_embeddings(kind)")
    op.execute(
        "CREATE INDEX ix_reference_embeddings_cosine ON reference_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TABLE IF EXISTS reference_embeddings")
