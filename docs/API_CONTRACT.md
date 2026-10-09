# Integration contract

API prefix `/api`. Next.js proxies `/api/*` and `/health` to `API_BASE_URL` (default http://127.0.0.1:8000). Browser sends `X-Demo-Session` UUID persisted in localStorage. All run/investigation state is scoped to that session. MCP may use a dedicated fixed synthetic session. No secrets in NEXT_PUBLIC variables.

## Shapes
Evidence: `{id, kind, service, timestamp, summary, data}`. `data` is a JSON object. IDs stable per seed case. Incident: `{id, scenario, title, severity, status, started_at, affected_services, client_impact, summary, timeline:[{timestamp,label,evidence_ids}], simulated_elapsed_seconds}`. Scenario IDs: `kafka-pricing-lag`, `fix-connectivity`, `db-pool-exhaustion`. Incident IDs stable `INC-DEMO-001` through `003`. Service: `{id,name,status,description}`. Dependency: `{source,target}`. Metric series: `{service,metric,unit,points:[{timestamp,value,evidence_id}]}`.

## Endpoints
- GET `/api/overview`: `{services,active_incidents,kafka,fix,database,investigation_count,clock:{label,scale},telemetry_mode}`.
- GET `/api/scenarios`: `[{id,title,description,incident_id}]`.
- POST `/api/demo/scenarios/{scenario}/run` and `/reset`: return Incident (reset may return `{status:"reset"}`). Running creates session-scoped incident and progressively exposes persisted telemetry based on monotonic elapsed time; UI polls.
- GET `/api/incidents`: Incident[]. GET `/api/incidents/{id}`: Incident.
- GET `/api/logs/search`: `{items:Evidence[],total,next_offset}`; params service, severity, trace_id, q, start, end, limit, offset, incident_id.
- GET `/api/metrics/query`: MetricSeries[]; params service, metric, start, end, aggregation, incident_id.
- GET `/api/services/topology`: `{services,dependencies}`.
- GET `/api/telemetry/kafka`, `/fix`, `/database`, `/deployments`: Evidence[]. Optional incident_id.
- GET `/api/evidence/{id}`: Evidence.
- GET `/api/runbooks`: Evidence[] (`data.content` Markdown). GET `/api/history`: Evidence[].
- GET `/api/evaluations/latest`: generated JSON or `{status:"not_generated"}`.
- GET `/api/instruments`: three fictional corporate bonds with coupon percent, maturity, currency and synthetic IDs.
- GET `/api/incidents/{id}/business-impact`: `{incident_id,as_of,summary,counters,requested_par_by_currency,requests:[{rfq,instrument,processing_state,quote,order,timeline:Evidence[],evidence_ids}],limitations}`. Values derive from available events; exact Decimal amounts are JSON strings.
- POST `/api/investigations`: body `{incident_id,mode:"REPLAY"|"MCP_DEMO"|"LIVE_AI"}`. Response Investigation. MCP_DEMO is keyless adaptive deterministic execution over real stdio. LIVE_AI requires Authorization Bearer admin key, server credentials, model and spend settings.
- GET `/api/investigations/{id}`: Investigation.
- GET `/api/investigations/{id}/events`: SSE `event: step`, data Step JSON; final `event: complete`, data Investigation JSON; `event: error`, data `{message}`. Supports already-completed traces.

Investigation: `{id,incident_id,mode,status,provider,created_at,steps:Step[],evidence:Evidence[],assessment:Assessment|null,error:string|null,usage:object}`.
Step: `{id,action,tool,status,evidence_ids,timestamp,duration_ms,safe_arguments,transport,provider,provider_turn,recorded,error}`. Additive provenance distinguishes recorded steps, fresh MCP calls and local validation. Investigation provenance includes workflow, transport, provider, model_called, snapshot_kind, snapshot_cutoff and schema verification; replay includes original transport, artifact version/generation time.
Assessment: `{incident_summary,probable_failure_domain,confidence,supporting_evidence_ids,alternative_hypotheses:[{domain,reason,evidence_ids}],recommended_next_steps:string[],relevant_runbooks:string[],similar_incidents:string[],requires_human_review,limitations:string[],rca:{executive_summary,impact,timeline:string[],observed_evidence:string[],probable_root_cause,contributing_factors:string[],immediate_next_steps:string[],follow_up_work:string[]}}`.

Assessment adds `observations:[{statement,evidence_ids}]`, `supported_failure_condition`, `possible_triggers:[{statement,evidence_ids,status:"candidate",reason}]`, nullable `confirmed_cause`, `unknowns` and `score_kind:"uncalibrated_support"`. Legacy `confidence` is retained for compatibility and rendered as support points, not probability. All current drafts require human review.

Python diagnostic-client interface uses async context management and `call(name, safe_filters)`. `DirectDiagnosticClient` explicitly serves offline evaluation; `MCPDiagnosticClient` uses the official SDK and owned stdio process. Both bind incident/session/cutoff outside provider control. The ten-tool allowlist remains get_incident, search_logs, query_metrics, get_service_topology, get_recent_deployments, find_similar_incidents, search_runbooks, inspect_kafka_lag, inspect_fix_session and inspect_database_health. `get_incident` and `search_logs` include relevant business-event evidence. Tool arguments support bounded filters, fixed incident_id, limit (1..50) and application-bound as_of. Tools never see scoring labels. Store `freeze_snapshot(session_id,id)` establishes the common cutoff.
