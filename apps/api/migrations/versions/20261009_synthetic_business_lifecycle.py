"""Persist the minimal fictional instrument/RFQ lifecycle.

Revision ID: 20261009_business
Revises: 20261009_pgvector
"""

import sqlalchemy as sa
from alembic import op

revision = "20261009_business"
down_revision = "20261009_pgvector"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "synthetic_instruments",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "synthetic_rfqs",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("incident_id", sa.String(96), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("instrument_id", sa.String(96), sa.ForeignKey("synthetic_instruments.id"), nullable=False),
        sa.Column("trace_id", sa.String(96), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    for field in ("incident_id", "instrument_id", "trace_id"):
        op.create_index(f"ix_synthetic_rfqs_{field}", "synthetic_rfqs", [field])
    op.create_table(
        "synthetic_business_events",
        sa.Column("evidence_id", sa.String(96), sa.ForeignKey("evidence.id"), primary_key=True),
        sa.Column("rfq_id", sa.String(96), sa.ForeignKey("synthetic_rfqs.id"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
    )
    for field in ("rfq_id", "event_type"):
        op.create_index(f"ix_synthetic_business_events_{field}", "synthetic_business_events", [field])


def downgrade():
    op.drop_table("synthetic_business_events")
    op.drop_table("synthetic_rfqs")
    op.drop_table("synthetic_instruments")
