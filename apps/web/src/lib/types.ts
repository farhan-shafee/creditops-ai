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
}
export interface Assessment {
  incident_summary: string;
  probable_failure_domain: string;
  confidence: number;
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
  error: string | null;
  usage: Record<string, unknown>;
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
