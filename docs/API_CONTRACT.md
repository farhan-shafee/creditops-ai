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
- POST `/api/investigations`: body `{incident_id,mode:"REPLAY"|"LIVE_AI"}`. Response Investigation. LIVE_AI requires Authorization Bearer admin key.
- GET `/api/investigations/{id}`: Investigation.
- GET `/api/investigations/{id}/events`: SSE `event: step`, data Step JSON; final `event: complete`, data Investigation JSON; `event: error`, data `{message}`. Supports already-completed traces.

Investigation: `{id,incident_id,mode,status,provider,created_at,steps:Step[],evidence:Evidence[],assessment:Assessment|null,error:string|null,usage:object}`.
Step: `{id,action,tool,status,evidence_ids,timestamp,duration_ms}`.
Assessment: `{incident_summary,probable_failure_domain,confidence,supporting_evidence_ids,alternative_hypotheses:[{domain,reason,evidence_ids}],recommended_next_steps:string[],relevant_runbooks:string[],similar_incidents:string[],requires_human_review,limitations:string[],rca:{executive_summary,impact,timeline:string[],observed_evidence:string[],probable_root_cause,contributing_factors:string[],immediate_next_steps:string[],follow_up_work:string[]}}`.

Python diagnostic interface `DiagnosticTools(store, session_id)`, async `call(name: str, arguments: dict) -> list[Evidence]`. Exposes exact read-only allowlist: get_incident, search_logs, query_metrics, get_service_topology, get_recent_deployments, find_similar_incidents, search_runbooks, inspect_kafka_lag, inspect_fix_session, inspect_database_health. Arguments support incident_id, service, q, limit (1..50), plus bounded filters. Tools must never see ground-truth evaluation labels. Store uses async `initialize()`, `get_incident(session_id,id)`, `list_incidents(session_id)`, `save_investigation(session_id,dict)`, `get_investigation(session_id,id)`; agent will coordinate further exact method signatures.
