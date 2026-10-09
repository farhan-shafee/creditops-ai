"""Public contracts; no ground-truth labels are present in operational schemas."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    safe_arguments: dict[str, Any] = Field(default_factory=dict)
    transport: str = "unknown"
    provider: str = "unknown"
    error: str | None = None
    provider_turn: int = 0
    recorded: bool = False


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


class EvidenceClaim(Contract):
    statement: str
    evidence_ids: list[str]


class TriggerHypothesis(EvidenceClaim):
    status: Literal["candidate"] = "candidate"
    reason: str


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
    observations: list[EvidenceClaim] = Field(default_factory=list)
    supported_failure_condition: str | None = None
    possible_triggers: list[TriggerHypothesis] = Field(default_factory=list)
    confirmed_cause: EvidenceClaim | None = None
    unknowns: list[str] = Field(default_factory=list)
    score_kind: Literal["uncalibrated_support"] = "uncalibrated_support"


class Investigation(Contract):
    id: str
    incident_id: str
    mode: Literal["REPLAY", "MCP_DEMO", "LIVE_AI"]
    status: str
    provider: str
    created_at: str
    steps: list[Step]
    evidence: list[Evidence]
    assessment: Assessment | None
    error: str | None
    usage: dict[str, Any]
    provenance: dict[str, Any] = Field(default_factory=dict)
    provider_proposal: dict[str, Any] | None = None
    validation_outcome: dict[str, Any] | None = None
    provider_calls: list[dict[str, Any]] = Field(default_factory=list)


class InvestigationRequest(Contract):
    incident_id: str = Field(min_length=1, max_length=96)
    mode: Literal["REPLAY", "MCP_DEMO", "LIVE_AI"] = "REPLAY"


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
    as_of: str | None = Field(default=None, max_length=40)
    metric: str | None = Field(default=None, max_length=96)
    aggregation: Literal["raw", "avg", "max", "min"] = "raw"


class TimeContract(Contract):
    @field_validator("*", mode="after")
    @classmethod
    def timezone_required(cls, value):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                raise ValueError("Timestamp must include a timezone")
            return value.astimezone(UTC)
        return value


class DecimalContract(TimeContract):
    @field_validator("*", mode="before")
    @classmethod
    def exact_decimal_input(cls, value, info):
        if info.field_name in {"par_amount", "coupon_percent", "clean_price_per_100_par"} and isinstance(
            value, float
        ):
            raise ValueError("Use a decimal string or Decimal, never a binary float")
        return value


class Instrument(DecimalContract):
    id: str
    issuer: str
    currency: Literal["USD"] = "USD"
    coupon_percent: Decimal = Field(ge=0)
    coupon_unit: str = "percent per annum"
    maturity: str
    instrument_type: Literal["CORPORATE_BOND"] = "CORPORATE_BOND"
    fictional: Literal[True] = True


class SyntheticRFQ(DecimalContract):
    id: str
    client_id: str
    instrument_id: str
    side: Literal["BUY", "SELL"]
    par_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: Literal["USD"] = "USD"
    par_unit: str = "currency units of requested face value"
    requested_at: datetime
    expires_at: datetime
    trace_id: str
    status: Literal["OPEN", "COMPLETED", "EXPIRED"] = "OPEN"

    @model_validator(mode="after")
    def valid_expiry(self):
        if self.expires_at <= self.requested_at:
            raise ValueError("RFQ expiry must follow its request timestamp")
        return self


class QuoteState(DecimalContract):
    id: str | None = None
    status: Literal["UNAVAILABLE", "FRESH", "STALE", "EXPIRED", "ACCEPTED"] = "UNAVAILABLE"
    clean_price_per_100_par: Decimal | None = Field(default=None, gt=0)
    price_convention: str = "clean price per 100 units of par; excludes accrued interest"
    source_timestamp: datetime | None = None
    expires_at: datetime | None = None
    accepted_at: datetime | None = None
    freshness_ms: int | None = Field(default=None, ge=0)


class OrderState(TimeContract):
    id: str
    status: Literal["PENDING_ACK", "UNKNOWN", "ACKNOWLEDGED"]
    submitted_at: datetime
    acknowledged_at: datetime | None = None
    trace_id: str
    acknowledgement_meaning: str = "Receipt acknowledgement only; execution is not established"


class AffectedRequest(Contract):
    rfq: SyntheticRFQ
    instrument: Instrument
    processing_state: Literal["RECEIVED", "WAITING_PRICING", "QUOTE_AVAILABLE", "DB_WAIT", "TIMED_OUT"]
    quote: QuoteState
    order: OrderState | None
    affected: bool
    timeline: list[Evidence]
    evidence_ids: list[str]


class ImpactCounters(Contract):
    rfqs_total: int = 0
    rfqs_affected: int = 0
    stale_quotes: int = 0
    unavailable_quotes: int = 0
    expired_rfqs: int = 0
    expired_quotes: int = 0
    processing_timeouts: int = 0
    pending_acknowledgements: int = 0
    unknown_acknowledgements: int = 0


class BusinessImpact(Contract):
    incident_id: str
    as_of: str
    summary: str
    counters: ImpactCounters
    requested_par_by_currency: dict[str, Decimal]
    requests: list[AffectedRequest]
    limitations: list[str]
