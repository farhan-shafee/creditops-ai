"""Known-domain diagnostic conditions and explicitly deterministic assessment."""

import json
import math
from datetime import UTC, datetime, timedelta
from typing import Any

from .models import Assessment
from .security import sanitize

KAFKA_DOMAIN = "pricing-service / Kafka consumer backlog"
FIX_DOMAIN = "FIX connectivity/session instability"
DB_DOMAIN = "database connection pool exhaustion"
MARKET_DOMAIN = "market-data-service / stale market data"
RISK_DOMAIN = "risk-service / upstream dependency timeout"
CPU_DOMAIN = "quote-service / CPU saturation"
ABSTAIN_DOMAIN = "insufficient evidence"


def as_dict(value: Any) -> dict[str, Any]:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def number(data: dict[str, Any], *names: str) -> float:
    for name in names:
        value = data.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if data.get("metric") == name or data.get("name") == name:
            value = data.get("value")
            if isinstance(value, (int, float)):
                return float(value)
    return 0.0


def utilization_percent(data: dict[str, Any], *names: str) -> float | None:
    """Normalize utilization only when source units are known and consistent.

    Percent field names and explicit percent units describe 0..100 values.
    Only known raw fraction fields or explicit ratio units describe 0..1.
    Ambiguous, conflicting and out-of-range telemetry cannot prove saturation.
    """
    for name in names:
        raw_field = name in data
        metric_field = data.get("metric", data.get("name")) == name
        if not raw_field and not metric_field:
            continue
        value = data.get(name) if raw_field else data.get("value")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            return None
        value = float(value)
        unit = data.get("unit")
        if unit is not None and not isinstance(unit, str):
            return None
        unit = unit.strip().lower() if isinstance(unit, str) else unit
        percent_name = name.endswith(("_percent", "_pct"))
        percent_unit, ratio_unit = unit in {"%", "percent"}, unit in {"ratio", "fraction"}
        if unit is not None and not percent_unit and not ratio_unit:
            return None
        if percent_name and ratio_unit:
            return None
        if percent_name or percent_unit:
            return value if 0 <= value <= 100 else None
        if ratio_unit or (raw_field and name in {"pool_utilization", "cpu_utilization"}):
            return value * 100 if 0 <= value <= 1 else None
        return None
    return None


def database_signal_types(item: dict[str, Any]) -> set[str]:
    """Shared anomaly predicates for current corroboration and historical onset."""
    if item["kind"] not in ("metric", "database", "log"):
        return set()
    data = item.get("data", {})
    text = (item.get("summary", "") + " " + str(data.get("message", ""))).lower()
    signals = set()
    pool = utilization_percent(
        data,
        "pool_utilization",
        "pool_utilization_pct",
        "db_pool_utilization",
        "db_pool_utilization_pct",
        "connection_pool_utilization",
    )
    if pool is not None and pool >= 95:
        signals.add("pool")
    if (
        number(data, "wait_time_ms", "pool_wait_ms", "db_wait_ms", "db_query_latency_ms", "query_latency_ms")
        >= 500
        or number(data, "waiters", "pool_waiters", "waiting_connections") >= 1
        or item["kind"] == "log"
        and (
            "pool timeout" in text
            or "pool exhausted" in text
            or "connection pool" in text
            and "timeout" in text
        )
    ):
        signals.add("wait")
    return signals


def diagnose(evidence: list[dict[str, Any]]) -> tuple[str, list[str], float]:
    """Require corroboration; incident names and evaluation labels are never inputs."""
    rows = [as_dict(item) for item in evidence]

    def series_key(item: dict) -> tuple | None:
        if item["kind"] not in ("metric", "database", "kafka", "fix"):
            return None
        data = item.get("data", {})
        return (
            item["kind"],
            item.get("service", ""),
            data.get("metric"),
            data.get("topic"),
            data.get("session_id"),
        )

    latest: dict[tuple, datetime] = {}
    for item in rows:
        key = series_key(item)
        if key is not None:
            when = observation_time(item["timestamp"])
            latest[key] = max(when, latest.get(key, when))
    current = [
        item
        for item in rows
        if series_key(item) is None or observation_time(item["timestamp"]) == latest[series_key(item)]
    ]
    signals: dict[str, dict[str, list[str]]] = {
        domain: {} for domain in (KAFKA_DOMAIN, FIX_DOMAIN, DB_DOMAIN, MARKET_DOMAIN, RISK_DOMAIN, CPU_DOMAIN)
    }

    def add(domain: str, signal: str, identifier: str) -> None:
        signals[domain].setdefault(signal, []).append(identifier)

    for raw in current:
        item = as_dict(raw)
        kind, service, data = item["kind"], item.get("service", ""), item.get("data", {})
        if kind in ("incident", "runbook", "historical_incident", "history", "topology"):
            continue
        text = (item.get("summary", "") + " " + str(data.get("message", ""))).lower()
        identifier = item["id"]
        if number(data, "consumer_lag", "consumer_lag_messages", "lag", "kafka_consumer_lag") >= 1000 and (
            service == "pricing-service" or kind == "kafka"
        ):
            add(KAFKA_DOMAIN, "lag", identifier)
        if number(data, "quote_age_ms", "quote_age", "stale_price_count") >= 500 or (
            kind == "log"
            and service == "pricing-service"
            and any(
                term in text
                for term in (
                    "stale pricing",
                    "consumer backlog",
                    "consumer processing backlog",
                    "stale price",
                )
            )
        ):
            add(KAFKA_DOMAIN, "freshness", identifier)
        if number(data, "reconnect_count", "reconnects", "fix_reconnect_count") >= 2 or (
            kind in ("fix", "log")
            and service == "fix-gateway"
            and ("disconnect" in text or "reconnect" in text)
        ):
            add(FIX_DOMAIN, "reconnect", identifier)
        if number(data, "sequence_gaps", "sequence_gap_count", "fix_sequence_gaps") >= 1 or (
            kind in ("fix", "log")
            and ("heartbeat" in text or "sequence gap" in text)
            and service == "fix-gateway"
        ):
            add(FIX_DOMAIN, "session", identifier)
        for signal in sorted(database_signal_types(item)):
            add(DB_DOMAIN, signal, identifier)
        if service == "market-data-service":
            if (
                number(data, "price_age_ms", "market_data_age_ms", "quote_age_ms", "stale_price_count")
                >= 1000
            ):
                add(MARKET_DOMAIN, "age", identifier)
            if kind == "log" and ("stale" in text or "feed stalled" in text):
                add(MARKET_DOMAIN, "feed", identifier)
        if service == "risk-service":
            if (
                number(
                    data,
                    "p95_latency_ms",
                    "request_latency_p95",
                    "request_latency_p95_ms",
                    "latency_p95_ms",
                    "dependency_latency_ms",
                )
                >= 1500
            ):
                add(RISK_DOMAIN, "latency", identifier)
            if kind == "log" and ("timeout" in text or "deadline" in text):
                add(RISK_DOMAIN, "timeout", identifier)
        if service == "quote-service":
            cpu = utilization_percent(data, "cpu_percent", "cpu_pct", "cpu_utilization")
            if cpu is not None and cpu >= 90 or kind == "log" and "cpu saturation" in text:
                add(CPU_DOMAIN, "cpu", identifier)
            if (
                number(
                    data, "p95_latency_ms", "request_latency_p95", "request_latency_p95_ms", "latency_p95_ms"
                )
                >= 500
            ):
                add(CPU_DOMAIN, "latency", identifier)

    by_id = {item["id"]: item for item in current}
    db_signals = signals[DB_DOMAIN]
    pool_services = {by_id[identifier].get("service") for identifier in db_signals.get("pool", [])}
    wait_services = {by_id[identifier].get("service") for identifier in db_signals.get("wait", [])}
    qualified = [
        (domain, sigs)
        for domain, sigs in signals.items()
        if len(sigs) >= 2 and (domain != DB_DOMAIN or bool(pool_services & wait_services))
    ]
    if len(qualified) != 1:
        return (
            ABSTAIN_DOMAIN,
            [
                as_dict(item)["id"]
                for item in evidence
                if as_dict(item)["kind"] in ("metric", "kafka", "fix", "database", "log")
            ][:12],
            0.35,
        )
    domain, selected = qualified[0]
    identifiers = list(dict.fromkeys(identifier for values in selected.values() for identifier in values))
    if domain == FIX_DOMAIN:
        identifiers.extend(
            as_dict(item)["id"]
            for item in evidence
            if number(as_dict(item).get("data", {}), "execution_ack_latency_ms", "ack_latency_ms") >= 1000
            and as_dict(item)["id"] not in identifiers
        )
    return domain, identifiers, min(0.92, 0.72 + 0.06 * len(selected))


def observed_claim(item: dict[str, Any]) -> dict[str, Any]:
    data = item.get("data", {})
    detail = (
        f"{data.get('metric', 'metric')}={data.get('value')} {data.get('unit', '')}"
        if item["kind"] == "metric"
        else f"Source-reported {item['kind']} observation: {json.dumps(sanitize(item.get('summary', '')), ensure_ascii=False)}"
    )
    return {"statement": f"{item.get('service', 'unknown')}: {detail}", "evidence_ids": [item["id"]]}


def observation_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Observation timestamps must include a timezone")
    return parsed.astimezone(UTC)


def candidate_triggers(domain: str, support: list[dict], evidence: list[dict]) -> list[dict]:
    """A narrow temporal/service association; never a causal proof."""
    if domain != DB_DOMAIN or not support:
        return []
    service_signals: dict[str, set[str]] = {}
    for item in support:
        service = item.get("service", "")
        service_signals.setdefault(service, set()).update(database_signal_types(item))
    qualified_services = {
        service for service, signals in service_signals.items() if {"pool", "wait"} <= signals
    }
    by_service: dict[str, datetime] = {}
    # Current-state support chooses latest samples, but onset must retain older
    # returned anomalies. A later deployment cannot precede a known earlier fault.
    for item in evidence:
        service = item.get("service", "")
        if service in qualified_services and database_signal_types(item):
            when = observation_time(item["timestamp"])
            by_service[service] = min(when, by_service.get(service, when))
    triggers = []
    for item in evidence:
        if item["kind"] != "deployment" or item.get("service") not in by_service:
            continue
        onset = by_service[item["service"]]
        when = observation_time(item["timestamp"])
        if onset - timedelta(hours=1) <= when < onset:
            triggers.append(
                {
                    "statement": f"A deployment to {item['service']} preceded the observed failure condition.",
                    "evidence_ids": [item["id"]],
                    "status": "candidate",
                    "reason": "Same corroborated service, within one hour before its earliest returned anomalous observation. This establishes temporal association only; causation is unconfirmed.",
                }
            )
    return triggers


def build_assessment(
    incident: dict[str, Any], evidence: list[dict[str, Any]]
) -> tuple[Assessment, dict[str, Any]]:
    rows = [as_dict(item) for item in evidence]
    domain, identifiers, confidence = diagnose(rows)
    selected = [item for item in rows if item["id"] in identifiers]
    query = {
        KAFKA_DOMAIN: "kafka consumer",
        FIX_DOMAIN: "fix session",
        DB_DOMAIN: "connection pool",
        MARKET_DOMAIN: "market data",
        RISK_DOMAIN: "dependency timeout",
        CPU_DOMAIN: "quote latency",
    }.get(domain, "dependency timeout")
    runbooks = [
        item["id"]
        for item in rows
        if item["kind"] == "runbook"
        and any(
            token in (item["summary"] + str(item["data"].get("title", ""))).lower() for token in query.split()
        )
    ][:2]
    histories = [
        item["id"]
        for item in rows
        if item["kind"] in ("history", "historical_incident")
        and any(token in item["summary"].lower() for token in query.split())
    ][:2]
    citation = ", ".join(identifiers[:4]) or "no corroborating diagnostic evidence returned"
    # Scenario titles and static impact descriptions are not diagnostic evidence.
    title = "Synthetic operational observations"
    business = [item for item in rows if item["kind"] == "business_event"]
    impact = (
        "Returned synthetic RFQ/order events are available for human inspection; event states do not establish financial loss or confirmed execution."
        if business
        else "No RFQ/order event evidence was returned. Affected requests and missed deadlines remain unverified."
    )
    abstained = domain == ABSTAIN_DOMAIN
    cause = (
        f"Insufficient independent signals to isolate a failure domain [{citation}]."
        if abstained
        else f"Supported failure condition: {domain} [{citation}]. The initiating cause is unconfirmed."
    )
    steps = [
        "Compare the affected service time window with its upstream and downstream dependencies.",
        "Have a human engineer verify the evidence and review the relevant diagnostic runbook.",
        "Escalate to the owning service team before considering any configuration change.",
    ]
    if domain == FIX_DOMAIN:
        steps.insert(
            0,
            "Reconcile the existing economic order identity and acknowledgement state with the owning team; do not blindly resubmit a new order. FIX retransmission is not a new economic order.",
        )
    observations = [observed_claim(item) for item in selected]
    triggers = candidate_triggers(domain, selected, rows)
    unknowns = [
        "The initiating cause has not been established by these observations.",
        "Historical similarity and runbooks are investigation aids, not proof of the current cause.",
    ]
    if domain == DB_DOMAIN:
        unknowns.append(
            "A relevant preceding deployment is only a candidate trigger; code-path, connection ownership and causal evidence need human investigation."
        )
    if domain == KAFKA_DOMAIN:
        unknowns.append(
            "Backlog does not establish why consumption slowed; producer volume, consumer errors and resource constraints need separate checks."
        )
    if domain == FIX_DOMAIN:
        unknowns.append(
            "A missing or delayed acknowledgement leaves order outcome PENDING or UNKNOWN, not FAILED or EXECUTED."
        )
    if not business:
        unknowns.append("No request-event evidence establishes the claimed business impact.")
    alternatives = []
    for item in rows:
        if item["kind"] in ("database", "fix", "kafka") and item["id"] not in identifiers:
            alternatives.append(
                {
                    "domain": f"{item['kind']} subsystem",
                    "reason": f"Considered separately; returned health snapshot [{item['id']}] does not establish the primary failure.",
                    "evidence_ids": [item["id"]],
                }
            )
    result = Assessment.model_validate(
        {
            "incident_summary": f"{title}. {cause}",
            "probable_failure_domain": domain,
            "confidence": confidence,
            "supporting_evidence_ids": identifiers,
            "alternative_hypotheses": alternatives[:2],
            "recommended_next_steps": steps,
            "relevant_runbooks": runbooks,
            "similar_incidents": histories,
            "requires_human_review": True,
            "observations": observations,
            "supported_failure_condition": None if abstained else domain,
            "possible_triggers": triggers,
            "confirmed_cause": None,
            "unknowns": unknowns,
            "limitations": [
                "Deterministic evidence assessment; no language model was called.",
                "Synthetic fixtures cover a bounded set of failure modes; confidence is a rule score, not a calibrated probability.",
                "Draft — human review required. Correlation does not establish a definitive root cause.",
            ],
            "rca": {
                "executive_summary": f"Draft — human review required. {cause}",
                "impact": impact,
                "timeline": [
                    f"{item['timestamp']}: {observed_claim(item)['statement']} [{item['id']}]"
                    for item in selected[:5]
                ],
                "observed_evidence": [
                    f"{claim['statement']} [{', '.join(claim['evidence_ids'])}]" for claim in observations
                ],
                "probable_root_cause": cause,
                "contributing_factors": [
                    f"Service dependency propagation needs human confirmation [{citation}]."
                ],
                "immediate_next_steps": steps,
                "follow_up_work": [
                    "Validate alert coverage and collect a longer diagnostic window.",
                    "Check relevant preceding changes and capacity assumptions without assuming causation.",
                    "Add the verified incident outcome to the synthetic regression dataset.",
                ],
            },
        }
    )
    return result, {
        "total_tokens": None,
        "input_tokens": None,
        "output_tokens": None,
        "estimated_cost_usd": None,
    }
