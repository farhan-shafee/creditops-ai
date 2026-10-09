"""Portable relational persistence; PostgreSQL is the full-stack deployment target."""

from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ServiceRow(Base):
    __tablename__ = "services"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    name: Mapped[str] = mapped_column(String(96), unique=True)
    description: Mapped[str] = mapped_column(Text)


class DependencyRow(Base):
    __tablename__ = "service_dependencies"
    source: Mapped[str] = mapped_column(ForeignKey("services.id"), primary_key=True)
    target: Mapped[str] = mapped_column(ForeignKey("services.id"), primary_key=True)


class IncidentRow(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    scenario: Mapped[str] = mapped_column(String(96), unique=True)
    severity: Mapped[str] = mapped_column(String(8), index=True)
    started_at: Mapped[str] = mapped_column(String(40), index=True)
    interactive: Mapped[bool]
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class IncidentEventRow(Base):
    __tablename__ = "incident_events"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    timestamp: Mapped[str] = mapped_column(String(40))
    reveal_seconds: Mapped[int]
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class DemoRunRow(Base):
    __tablename__ = "demo_runs"
    session_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), primary_key=True)
    started_wall: Mapped[float] = mapped_column(Float)
    fixed_elapsed: Mapped[float | None] = mapped_column(Float, nullable=True)
    __table_args__ = (Index("ix_demo_runs_wall", "started_wall"),)


class EvidenceRow(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    service: Mapped[str] = mapped_column(String(96), index=True)
    timestamp: Mapped[str] = mapped_column(String(40), index=True)
    summary: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"), nullable=True, index=True)
    reveal_seconds: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (Index("ix_evidence_incident_kind_time", "incident_id", "kind", "timestamp"),)


class LogRow(Base):
    __tablename__ = "logs"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    trace_id: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    message: Mapped[str] = mapped_column(Text)


class InstrumentRow(Base):
    __tablename__ = "synthetic_instruments"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class RFQRow(Base):
    __tablename__ = "synthetic_rfqs"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("synthetic_instruments.id"), index=True)
    trace_id: Mapped[str] = mapped_column(String(96), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class BusinessEventRow(Base):
    __tablename__ = "synthetic_business_events"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    rfq_id: Mapped[str] = mapped_column(ForeignKey("synthetic_rfqs.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)


class MetricRow(Base):
    __tablename__ = "metric_samples"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    metric: Mapped[str] = mapped_column(String(96), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))


class KafkaTopicRow(Base):
    __tablename__ = "kafka_topics"
    name: Mapped[str] = mapped_column(String(96), primary_key=True)
    partitions: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)


class KafkaGroupRow(Base):
    __tablename__ = "kafka_consumer_groups"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    topic: Mapped[str] = mapped_column(ForeignKey("kafka_topics.name"), index=True)
    consumer_group: Mapped[str] = mapped_column(String(96), index=True)
    consumer_lag: Mapped[int] = mapped_column(Integer)


class FixSessionRow(Base):
    __tablename__ = "fix_sessions"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(96), index=True)
    connected: Mapped[bool]
    sender_seq_num: Mapped[int]
    target_seq_num: Mapped[int]
    reconnect_count: Mapped[int]
    sequence_gaps: Mapped[int]


class DatabaseHealthRow(Base):
    __tablename__ = "database_health"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    pool_utilization: Mapped[float] = mapped_column(Float)
    query_latency_ms: Mapped[float] = mapped_column(Float)
    wait_ms: Mapped[float] = mapped_column(Float)


class DeploymentRow(Base):
    __tablename__ = "deployments"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    version: Mapped[str] = mapped_column(String(96))
    deployed_at: Mapped[str] = mapped_column(String(40), index=True)
    change: Mapped[str] = mapped_column(Text)


class RunbookRow(Base):
    __tablename__ = "runbooks"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    title: Mapped[str] = mapped_column(String(240))
    content: Mapped[str] = mapped_column(Text)
    search_text: Mapped[str] = mapped_column(Text)


class HistoricalIncidentRow(Base):
    __tablename__ = "historical_incidents"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    title: Mapped[str] = mapped_column(String(240))
    symptoms: Mapped[str] = mapped_column(Text)
    resolution: Mapped[str] = mapped_column(Text)


class InvestigationRow(Base):
    __tablename__ = "investigations"
    session_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(96), index=True)
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class InvestigationStepRow(Base):
    __tablename__ = "investigation_steps"
    session_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    position: Mapped[int]
    tool: Mapped[str] = mapped_column(String(96))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "investigation_id"],
            ["investigations.session_id", "investigations.id"],
            ondelete="CASCADE",
        ),
    )


class EvaluationCaseRow(Base):
    __tablename__ = "evaluation_cases"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class EvaluationRunRow(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
