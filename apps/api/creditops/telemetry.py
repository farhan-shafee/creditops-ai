"""Real Redpanda interaction with a persisted synthetic fallback.

Kafka is an optional mirror of the immutable synthetic telemetry catalog. The
session clock remains authoritative for public visibility; broker messages can
never mutate diagnostic evidence or affect external systems.
"""

import asyncio
import json
import logging
import re
from uuid import uuid4

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from .security import sanitize
from .seed import TOPICS, make_seed

LOGGER = logging.getLogger("creditops.telemetry")


def validate_envelope(value: dict) -> dict:
    if not isinstance(value, dict) or value.get("environment") != "synthetic":
        raise ValueError("Only synthetic stream envelopes are accepted")
    identifier = value.get("evidence_id")
    if not isinstance(identifier, str) or not re.fullmatch(r"[A-Z][A-Z0-9_-]{2,95}", identifier):
        raise ValueError("Invalid synthetic evidence identifier")
    if not isinstance(value.get("data"), dict):
        raise ValueError("Envelope data must be an object")
    if len(json.dumps(value)) > 32768:
        raise ValueError("Synthetic envelope exceeded budget")
    return sanitize(value)


class SyntheticTelemetryAdapter:
    def __init__(self, mode: str = "persisted", bootstrap_servers: str = "127.0.0.1:19092"):
        if mode not in {"persisted", "kafka"}:
            raise ValueError("Unsupported telemetry mode")
        self.requested_mode = mode
        self.bootstrap_servers = bootstrap_servers
        self.producer: AIOKafkaProducer | None = None
        self.consumer: AIOKafkaConsumer | None = None
        self.task: asyncio.Task | None = None
        self.connected = False
        self.produced = 0
        self.consumed = 0
        self.rejected = 0
        self.last_error: str | None = None

    async def start(self) -> None:
        if self.requested_mode == "persisted":
            return
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers, request_timeout_ms=3000
            )
            await asyncio.wait_for(self.producer.start(), timeout=5)
            for topic in TOPICS:
                envelope = {
                    "environment": "synthetic",
                    "evidence_id": f"BOOTSTRAP-{topic.upper().replace('.', '-')}",
                    "data": {"topic": topic, "purpose": "CreditOps fictional stream bootstrap"},
                }
                await asyncio.wait_for(
                    self.producer.send_and_wait(topic, json.dumps(envelope).encode()), timeout=5
                )
                self.produced += 1
            self.consumer = AIOKafkaConsumer(
                *TOPICS,
                bootstrap_servers=self.bootstrap_servers,
                group_id=f"creditops-synthetic-{uuid4()}",
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                request_timeout_ms=5000,
            )
            await asyncio.wait_for(self.consumer.start(), timeout=5)
            self.connected = True
            self.task = asyncio.create_task(self._consume())
        except Exception as error:
            self.last_error = type(error).__name__
            LOGGER.warning("synthetic_broker_unavailable_using_persisted_fallback")
            await self.close()

    async def _consume(self) -> None:
        if self.consumer is None:
            raise RuntimeError("Synthetic consumer was not initialized")
        try:
            while True:
                batches = await self.consumer.getmany(timeout_ms=500, max_records=100)
                for messages in batches.values():
                    for message in messages:
                        try:
                            if len(message.value) > 32768:
                                raise ValueError("Envelope exceeded size budget")
                            validate_envelope(json.loads(message.value))
                            self.consumed += 1
                        except (ValueError, TypeError, UnicodeDecodeError):
                            self.rejected += 1
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.connected = False
            self.last_error = type(error).__name__
            LOGGER.warning("synthetic_consumer_failed_using_persisted_fallback")

    async def publish_incident(self, incident_id: str) -> None:
        if not self.connected or self.producer is None:
            return
        topic_by_kind = {
            "kafka": "pricing.updates",
            "fix": "execution.events",
            "database": "rfq.responses",
            "log": "audit.events",
            "metric": "marketdata.updates",
            "incident": "rfq.requests",
        }
        try:
            for record in make_seed()["evidence"]:
                if record["incident_id"] != incident_id:
                    continue
                envelope = validate_envelope(
                    {
                        "environment": "synthetic",
                        "evidence_id": record["id"],
                        "kind": record["kind"],
                        "service": record["service"],
                        "timestamp": record["timestamp"],
                        "data": record["data"],
                    }
                )
                await asyncio.wait_for(
                    self.producer.send_and_wait(
                        topic_by_kind.get(record["kind"], "audit.events"),
                        json.dumps(envelope).encode(),
                        key=record["id"].encode(),
                    ),
                    timeout=3,
                )
                self.produced += 1
        except Exception as error:
            self.connected = False
            self.last_error = type(error).__name__
            LOGGER.warning("synthetic_publication_failed_using_persisted_fallback")

    def health(self) -> dict:
        return {
            "mode": "kafka" if self.connected else "persisted",
            "requested_mode": self.requested_mode,
            "broker_connected": self.connected,
            "produced_messages": self.produced,
            "consumed_messages": self.consumed,
            "rejected_messages": self.rejected,
            "last_error": self.last_error,
            "source": "entirely synthetic persisted catalog",
        }

    async def close(self) -> None:
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
        if self.consumer is not None:
            await self.consumer.stop()
            self.consumer = None
        if self.producer is not None:
            await self.producer.stop()
            self.producer = None
        self.connected = False
