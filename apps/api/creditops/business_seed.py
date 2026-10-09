"""Fictional, immutable lifecycle observations; money is always an exact decimal string."""

from .seed import timestamp


def make_business_seed() -> dict:
    instruments = [
        {
            "id": "BOND-DEMO-001",
            "issuer": "Demo Aster Manufacturing",
            "coupon_percent": "4.250",
            "maturity": "2029-06-15",
        },
        {
            "id": "BOND-DEMO-002",
            "issuer": "Demo Meridian Logistics",
            "coupon_percent": "5.125",
            "maturity": "2031-09-30",
        },
        {
            "id": "BOND-DEMO-003",
            "issuer": "Demo Cedar Utilities",
            "coupon_percent": "3.875",
            "maturity": "2033-03-01",
        },
    ]
    rfqs, events = [], []
    for case in range(1, 4):
        incident = f"INC-DEMO-{case:03}"
        sequence = 0
        for index, par in enumerate(["1000000.00", "750000.00"], start=1):
            start = (index - 1) * 12
            rfq_id, trace = f"RFQ-DEMO-{case:03}-{index:03}", f"TRACE-DEMO-{case:03}-RFQ-{index:03}"
            expiry = 120 if index == 1 else 144
            rfq = {
                "id": rfq_id,
                "client_id": f"CLIENT-DEMO-{index:03}",
                "instrument_id": f"BOND-DEMO-{case:03}",
                "side": "BUY" if index == 1 else "SELL",
                "par_amount": par,
                "currency": "USD",
                "requested_at": timestamp(start),
                "expires_at": timestamp(expiry),
                "trace_id": trace,
            }
            rfqs.append({"incident_id": incident, "payload": rfq})

            def add(
                kind,
                seconds,
                service,
                *,
                case=case,
                rfq_id=rfq_id,
                rfq=rfq,
                par=par,
                trace=trace,
                incident=incident,
                **details,
            ):
                nonlocal sequence
                sequence += 1
                evidence_id = f"BUSINESS-{case:03}-{sequence:03}"
                data = {
                    "event_type": kind,
                    "rfq_id": rfq_id,
                    "client_id": rfq["client_id"],
                    "instrument_id": rfq["instrument_id"],
                    "side": rfq["side"],
                    "par_amount": par,
                    "currency": "USD",
                    "par_unit": "currency units of requested face value",
                    "requested_at": rfq["requested_at"],
                    "rfq_expires_at": rfq["expires_at"],
                    "trace_id": trace,
                    "severity": "WARN"
                    if kind
                    in {
                        "QUOTE_STALE",
                        "QUOTE_EXPIRED",
                        "QUOTE_UNAVAILABLE",
                        "ACK_UNCERTAIN",
                        "PROCESSING_TIMEOUT",
                    }
                    else "INFO",
                    **details,
                }
                summary = f"Fictional {rfq_id}: {kind.replace('_', ' ').lower()}"
                data["message"] = summary
                events.append(
                    {
                        "id": evidence_id,
                        "kind": "business_event",
                        "service": service,
                        "timestamp": timestamp(seconds),
                        "summary": summary,
                        "data": data,
                        "incident_id": incident,
                        "reveal_seconds": seconds // 12,
                    }
                )

            add("RFQ_REQUESTED", start, "rfq-gateway")
            add("PROCESSING_STARTED", start + 12, "rfq-gateway")
            quote_id = f"QUOTE-DEMO-{case:03}-{index:03}"
            if case == 1:
                if index == 1:
                    add(
                        "QUOTE_PUBLISHED",
                        24,
                        "quote-service",
                        quote_id=quote_id,
                        clean_price_per_100_par="99.875",
                        source_timestamp=timestamp(24),
                        quote_expires_at=timestamp(72),
                    )
                    add("QUOTE_STALE", 60, "quote-service", quote_id=quote_id)
                    add("QUOTE_EXPIRED", 72, "quote-service", quote_id=quote_id)
                else:
                    add("WAITING_PRICING", 36, "pricing-service", processing_stage="WAITING_PRICING")
                    add("QUOTE_UNAVAILABLE", 60, "quote-service", processing_stage="WAITING_PRICING")
                add("RFQ_EXPIRED", expiry, "rfq-gateway")
            elif case == 2:
                add(
                    "QUOTE_PUBLISHED",
                    start + 12,
                    "quote-service",
                    quote_id=quote_id,
                    clean_price_per_100_par="101.125",
                    source_timestamp=timestamp(start + 12),
                    quote_expires_at=timestamp(start + 72),
                )
                add("QUOTE_ACCEPTED", start + 24, "quote-service", quote_id=quote_id)
                order_id = f"ORDER-DEMO-{case:03}-{index:03}"
                add("ORDER_SUBMITTED", start + 36, "execution-service", order_id=order_id, quote_id=quote_id)
                add("ACK_PENDING", start + 48, "execution-service", order_id=order_id)
                add("ACK_UNCERTAIN", start + 84, "fix-gateway", order_id=order_id)
                add(
                    "FIX_RETRANSMISSION",
                    start + 96,
                    "fix-gateway",
                    order_id=order_id,
                    retransmission=True,
                    economic_order_id=order_id,
                )
            else:
                add("DB_WAIT", start + 36, "quote-service", processing_stage="DB_WAIT")
                add("PROCESSING_TIMEOUT", start + 84, "quote-service", processing_stage="DB_WAIT")
                add("RFQ_EXPIRED", expiry, "rfq-gateway")
    return {"instruments": instruments, "rfqs": rfqs, "events": events}
