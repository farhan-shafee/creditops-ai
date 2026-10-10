export interface Evidence {
  id: string;
  kind: string;
  service: string;
  timestamp: string;
  summary: string;
  data: Record<string, unknown>;
}
export interface Service {
  id: string;
  name: string;
  status: string;
  description: string;
}
export interface Topology {
  services: Service[];
  dependencies: { source: string; target: string }[];
}
export interface Incident {
  id: string;
  scenario: string;
  title: string;
  severity: string;
  status: string;
  started_at: string;
  affected_services: string[];
  client_impact: string;
  summary: string;
  simulated_elapsed_seconds: number;
  timeline: { timestamp: string; label: string; evidence_ids: string[] }[];
}
export interface Scenario {
  id: string;
  title: string;
  description: string;
  incident_id: string;
}
export interface MetricSeries {
  service: string;
  metric: string;
  unit: string;
  points: { timestamp: string; value: number; evidence_id: string }[];
}
export interface Step {
  id: string;
  action: string;
  tool: string;
  status: string;
  evidence_ids: string[];
  timestamp: string;
  duration_ms: number;
  safe_arguments?: Record<string, unknown>;
  transport?: string;
  provider?: string;
  error?: string | null;
  provider_turn?: number;
  recorded?: boolean;
  selected_by?:
    'application_runbook' | 'model' | 'deterministic' | 'scripted_provider' | 'validator' | null;
}
export interface EvidenceClaim {
  statement: string;
  evidence_ids: string[];
}
export interface Assessment {
  incident_summary: string;
  probable_failure_domain: string;
  confidence: number;
  observations?: EvidenceClaim[];
  supported_failure_condition?: string | null;
  possible_triggers?: (EvidenceClaim & { status: 'candidate'; reason: string })[];
  confirmed_cause?: EvidenceClaim | null;
  unknowns?: string[];
  score_kind?: 'uncalibrated_support';
  supporting_evidence_ids: string[];
  alternative_hypotheses: { domain: string; reason: string; evidence_ids: string[] }[];
  recommended_next_steps: string[];
  relevant_runbooks: string[];
  similar_incidents: string[];
  requires_human_review: boolean;
  limitations: string[];
  rca: {
    executive_summary: string;
    impact: string;
    timeline: string[];
    observed_evidence: string[];
    probable_root_cause: string;
    contributing_factors: string[];
    immediate_next_steps: string[];
    follow_up_work: string[];
  };
}
export interface Investigation {
  id: string;
  incident_id: string;
  mode: string;
  status: string;
  provider: string;
  created_at: string;
  steps: Step[];
  evidence: Evidence[];
  assessment: Assessment | null;
  provider_proposal?: Record<string, unknown> | null;
  validation_outcome?: {
    status: string;
    changed_fields?: Record<string, unknown>[];
    rejected_fields?: Record<string, unknown>[];
    [key: string]: unknown;
  } | null;
  error: string | null;
  usage: Record<string, unknown>;
  provenance?: {
    transport?: string;
    workflow?: string;
    original_workflow?: string;
    provider?: string;
    model_called?: boolean;
    assessment_source?: {
      kind: string;
      provider: string;
      reason?: string;
    } | null;
    snapshot_cutoff?: string | null;
    snapshot_kind?: string;
    tool_schema_verified?: boolean;
    recorded?: boolean;
    original_transport?: string;
    [key: string]: unknown;
  };
}
export type InvestigationMode = 'REPLAY' | 'MCP_DEMO';
export interface BusinessImpactRequest {
  rfq: {
    id: string;
    client_id: string;
    instrument_id: string;
    side: string;
    par_amount: string;
    currency: string;
    par_unit: string;
    requested_at: string;
    expires_at: string;
    trace_id: string;
    status: 'OPEN' | 'COMPLETED' | 'EXPIRED';
  };
  instrument: {
    id: string;
    issuer: string;
    currency: string;
    coupon_percent: string;
    maturity: string;
    instrument_type: string;
  };
  processing_state: 'RECEIVED' | 'WAITING_PRICING' | 'QUOTE_AVAILABLE' | 'DB_WAIT' | 'TIMED_OUT';
  quote: {
    id: string | null;
    status: 'UNAVAILABLE' | 'FRESH' | 'STALE' | 'EXPIRED' | 'ACCEPTED';
    clean_price_per_100_par: string | null;
    source_timestamp: string | null;
    expires_at: string | null;
    accepted_at: string | null;
    freshness_ms: number | null;
  };
  order: {
    id: string;
    status: 'PENDING_ACK' | 'UNKNOWN' | 'ACKNOWLEDGED';
    submitted_at: string;
    acknowledged_at: string | null;
    trace_id: string;
  } | null;
  timeline: Evidence[];
  evidence_ids: string[];
}
export interface BusinessImpact {
  incident_id: string;
  as_of: string;
  summary: string;
  counters: {
    rfqs_total: number;
    rfqs_affected: number;
    stale_quotes: number;
    unavailable_quotes: number;
    expired_rfqs: number;
    expired_quotes: number;
    processing_timeouts: number;
    pending_acknowledgements: number;
    unknown_acknowledgements: number;
  };
  requested_par_by_currency: Record<string, string>;
  requests: BusinessImpactRequest[];
  limitations: string[];
}
export interface Overview {
  services: Service[];
  active_incidents: Incident[];
  kafka: Record<string, unknown>;
  fix: Record<string, unknown>;
  database: Record<string, unknown>;
  investigation_count: number;
  clock: { label: string; scale: number };
  telemetry_mode: string;
}
export interface EvalAlgorithm {
  name: string;
  provider: string;
  cases: number;
  top1_accuracy: number;
  top3_accuracy: number;
  required_evidence_recall: number;
  invalid_evidence_citations: number;
  hallucinated_evidence_count: number;
  correct_abstention_rate: number;
  tool_error_rate: number;
  mean_latency_ms: number;
  total_tokens: number | null;
  estimated_cost_usd: number | null;
}
export interface Evaluation {
  status?: string;
  generated_at?: string;
  algorithms?: EvalAlgorithm[];
  methodology?: string | Record<string, unknown>;
  cases?: Record<string, unknown>[];
  [key: string]: unknown;
}
