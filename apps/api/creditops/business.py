"""Read-only reconstruction of a tiny fictional RFQ/quote/order lifecycle."""

from datetime import UTC, datetime

from .models import OrderState, QuoteState, SyntheticRFQ


def observation_time(value: str | datetime) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        raise ValueError("Observation timestamp must include a timezone")
    return parsed.astimezone(UTC)


def reduce_request(rfq: SyntheticRFQ, events: list[dict], as_of: datetime) -> dict:
    """Apply observed transitions only. No clock-implied expiry or execution inference."""
    rfq = rfq.model_copy(deep=True)
    quote = QuoteState()
    order = None
    processing = "RECEIVED"
    seen = False
    kinds = set()
    impact_events = {
        "QUOTE_STALE",
        "QUOTE_UNAVAILABLE",
        "QUOTE_EXPIRED",
        "RFQ_EXPIRED",
        "PROCESSING_TIMEOUT",
        "ACK_PENDING",
        "ACK_UNCERTAIN",
    }
    for event in sorted(events, key=lambda item: (observation_time(item["timestamp"]), item["id"])):
        at = observation_time(event["timestamp"])
        if at > as_of:
            continue
        kind, data = event["event_type"], event["data"]
        if not seen and kind != "RFQ_REQUESTED":
            raise ValueError("Lifecycle must begin with RFQ_REQUESTED")
        if kind == "RFQ_REQUESTED":
            if seen:
                raise ValueError("Duplicate RFQ_REQUESTED")
            seen = True
        elif kind in {"PROCESSING_STARTED", "WAITING_PRICING", "DB_WAIT"}:
            if rfq.status != "OPEN" or processing == "TIMED_OUT":
                raise ValueError("Processing transition requires an open RFQ")
            processing = "DB_WAIT" if kind == "DB_WAIT" else "WAITING_PRICING"
        elif kind == "QUOTE_PUBLISHED":
            if rfq.status != "OPEN" or at >= rfq.expires_at:
                raise ValueError("Cannot publish for an expired RFQ")
            source, expiry = (
                observation_time(data["source_timestamp"]),
                observation_time(data["quote_expires_at"]),
            )
            if source > at or expiry <= at:
                raise ValueError("Quote publication has invalid source or expiry time")
            quote = QuoteState(
                id=data["quote_id"],
                status="FRESH",
                clean_price_per_100_par=data["clean_price_per_100_par"],
                source_timestamp=source,
                expires_at=expiry,
                freshness_ms=int((at - source).total_seconds() * 1000),
            )
            processing = "QUOTE_AVAILABLE"
        elif kind in {"QUOTE_STALE", "QUOTE_EXPIRED"}:
            if quote.status not in {"FRESH", "STALE"}:
                raise ValueError("Quote observation requires an available unaccepted quote")
            if data.get("quote_id") != quote.id:
                raise ValueError("Quote identity does not match")
            if kind == "QUOTE_EXPIRED" and at < quote.expires_at:
                raise ValueError("Premature quote expiry")
            quote.status = "STALE" if kind == "QUOTE_STALE" else "EXPIRED"
            quote.freshness_ms = int((at - quote.source_timestamp).total_seconds() * 1000)
        elif kind == "QUOTE_UNAVAILABLE":
            if quote.id is not None or rfq.status != "OPEN":
                raise ValueError("Unavailable quote transition is invalid")
        elif kind == "QUOTE_ACCEPTED":
            if quote.expires_at is not None and at >= quote.expires_at:
                raise ValueError("Cannot accept an expired quote")
            if quote.status != "FRESH" or data.get("quote_id") != quote.id:
                raise ValueError("Acceptance requires the matching fresh quote")
            if rfq.status != "OPEN" or at >= rfq.expires_at:
                raise ValueError("Cannot accept for an expired RFQ")
            quote.status, quote.accepted_at, rfq.status = "ACCEPTED", at, "COMPLETED"
        elif kind == "RFQ_EXPIRED":
            if rfq.status != "OPEN" or at < rfq.expires_at:
                raise ValueError("RFQ expiry transition is invalid")
            rfq.status = "EXPIRED"
        elif kind == "PROCESSING_TIMEOUT":
            if rfq.status != "OPEN" or processing not in {"WAITING_PRICING", "DB_WAIT"}:
                raise ValueError("Timeout requires waiting processing")
            processing = "TIMED_OUT"
        elif kind == "ORDER_SUBMITTED":
            if quote.status != "ACCEPTED" or order is not None:
                raise ValueError("One economic order requires a valid quote acceptance")
            if data.get("quote_id") != quote.id:
                raise ValueError("Order submission quote identity must match the accepted quote")
            order = OrderState(
                id=data["order_id"], status="PENDING_ACK", submitted_at=at, trace_id=rfq.trace_id
            )
        elif kind in {"ACK_PENDING", "ACK_UNCERTAIN", "ACK_CONFIRMED", "FIX_RETRANSMISSION"}:
            if order is None or data.get("order_id") != order.id:
                raise ValueError("Order identity does not match; retransmission cannot create an order")
            if kind == "ACK_CONFIRMED":
                order.status, order.acknowledged_at = "ACKNOWLEDGED", at
            elif kind in {"ACK_PENDING", "ACK_UNCERTAIN"}:
                if order.status == "ACKNOWLEDGED":
                    raise ValueError("Cannot erase a received acknowledgement")
                order.status = "PENDING_ACK" if kind == "ACK_PENDING" else "UNKNOWN"
        else:
            raise ValueError("Unknown business lifecycle transition")
        kinds.add(kind)
    if quote.source_timestamp is not None:
        # Current age is derived at the frozen observation cutoff. Recorded quote
        # status and acceptance time remain the separate event-derived facts.
        quote.freshness_ms = int((as_of - quote.source_timestamp).total_seconds() * 1000)
    return {
        "rfq": rfq,
        "quote": quote,
        "order": order,
        "processing_state": processing,
        "affected": bool(kinds & impact_events),
        "event_types": kinds,
    }
