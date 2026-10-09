"""Public contracts; no ground-truth labels are present in operational schemas."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Contract):
    id: str = Field(min_length=1, max_length=96)
    kind: str = Field(min_length=1, max_length=64)
    service: str = Field(max_length=96)
    timestamp: str
    summary: str = Field(max_length=8000)
    data: dict[str, Any]


class TimelineEvent(Contract):
    timestamp: str
    label: str
    evidence_ids: list[str]


class Incident(Contract):
    id: str
    scenario: str
    title: str
    severity: Literal["SEV1", "SEV2", "SEV3"]
    status: Literal["detected", "investigating", "monitoring", "resolved"]
    started_at: str
    affected_services: list[str]
    client_impact: str
    summary: str
    timeline: list[TimelineEvent]
    simulated_elapsed_seconds: int = 0


class Service(Contract):
    id: str
    name: str
    status: Literal["healthy", "degraded", "critical"] = "healthy"
    description: str


class MetricPoint(Contract):
    timestamp: str
    value: float
    evidence_id: str


class MetricSeries(Contract):
    service: str
    metric: str
    unit: str
    points: list[MetricPoint]


class Step(Contract):
    id: str
    action: str
    tool: str
    status: str
    evidence_ids: list[str]
    timestamp: str
    duration_ms: float = Field(ge=0)


class AlternativeHypothesis(Contract):
    domain: str
    reason: str
    evidence_ids: list[str]


class RCA(Contract):
    executive_summary: str
    impact: str
    timeline: list[str]
    observed_evidence: list[str]
    probable_root_cause: str
    contributing_factors: list[str]
    immediate_next_steps: list[str]
    follow_up_work: list[str]


class Assessment(Contract):
    incident_summary: str
    probable_failure_domain: str
    confidence: float = Field(ge=0, le=1)
    supporting_evidence_ids: list[str]
    alternative_hypotheses: list[AlternativeHypothesis]
    recommended_next_steps: list[str]
    relevant_runbooks: list[str]
    similar_incidents: list[str]
    requires_human_review: bool
    limitations: list[str]
    rca: RCA


class Investigation(Contract):
    id: str
    incident_id: str
    mode: Literal["REPLAY", "LIVE_AI"]
    status: str
    provider: str
    created_at: str
    steps: list[Step]
    evidence: list[Evidence]
    assessment: Assessment | None
    error: str | None
    usage: dict[str, Any]


class InvestigationRequest(Contract):
    incident_id: str = Field(min_length=1, max_length=96)
    mode: Literal["REPLAY", "LIVE_AI"] = "REPLAY"


class ToolArguments(Contract):
    incident_id: str | None = Field(default=None, max_length=96)
    service: str | None = Field(default=None, max_length=96)
    q: str | None = Field(default=None, max_length=240)
    limit: int = Field(default=20, ge=1, le=50, strict=True)
    offset: int = Field(default=0, ge=0, le=5000, strict=True)
    severity: Literal["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"] | None = None
    trace_id: str | None = Field(default=None, max_length=96)
    start: str | None = Field(default=None, max_length=40)
    end: str | None = Field(default=None, max_length=40)
    metric: str | None = Field(default=None, max_length=96)
    aggregation: Literal["raw", "avg", "max", "min"] = "raw"
