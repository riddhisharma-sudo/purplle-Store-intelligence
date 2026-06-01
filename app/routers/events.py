"""
app/routers/events.py
─────────────────────
FastAPI ingestion endpoint with:
  • Kafka as primary message bus (aiokafka)
  • Redis Streams as fallback when the Kafka broker is unavailable (aioredis)
  • Exponential-backoff retry loop (max 3 attempts) before falling back
  • Idempotency via event_id uniqueness check in PostgreSQL
  • Structured error handling throughout
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import StoreEvent
from app.schemas import EventBatch, EventResponse

# ── aiokafka (async Kafka client) ──────────────────────────────────────────────
try:
    from aiokafka import AIOKafkaProducer
    from aiokafka.errors import KafkaConnectionError, KafkaError
    KAFKA_AVAILABLE = True
except ImportError:  # pragma: no cover
    KAFKA_AVAILABLE = False

# ── aioredis (async Redis client) ─────────────────────────────────────────────
try:
    import aioredis
    REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["events"])

# ── Config from environment ────────────────────────────────────────────────────
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC     = os.getenv("KAFKA_TOPIC", "store_events")
REDIS_URL       = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_STREAM    = os.getenv("REDIS_STREAM_KEY", "store_events_fallback")

MAX_KAFKA_RETRIES  = 3
BACKOFF_BASE_SECS  = 0.5   # 0.5 → 1.0 → 2.0 s


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

async def _get_kafka_producer() -> "AIOKafkaProducer | None":
    """
    Attempt to create and start a Kafka producer.
    Returns None if Kafka is not importable or the broker is unreachable.
    """
    if not KAFKA_AVAILABLE:
        return None
    try:
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            request_timeout_ms=3000,
        )
        await producer.start()
        return producer
    except Exception as exc:  # noqa: BLE001
        logger.warning("Kafka producer startup failed: %s", exc)
        return None


async def _send_to_kafka(
    producer: "AIOKafkaProducer",
    events: List[dict],
) -> None:
    """
    Send all events to Kafka with exponential-backoff retries.
    Raises KafkaError after MAX_KAFKA_RETRIES exhausted.
    """
    for attempt in range(1, MAX_KAFKA_RETRIES + 1):
        try:
            for event in events:
                await producer.send_and_wait(KAFKA_TOPIC, event)
            logger.info("Kafka: sent %d events (attempt %d)", len(events), attempt)
            return
        except (KafkaConnectionError, KafkaError) as exc:
            wait = BACKOFF_BASE_SECS * (2 ** (attempt - 1))
            logger.warning(
                "Kafka send failed (attempt %d/%d): %s — retrying in %.1fs",
                attempt, MAX_KAFKA_RETRIES, exc, wait,
            )
            if attempt == MAX_KAFKA_RETRIES:
                raise
            await asyncio.sleep(wait)


async def _send_to_redis_fallback(events: List[dict]) -> None:
    """
    Write events to a Redis Stream when Kafka is unavailable.
    Each event becomes one XADD entry keyed by its event_id.
    """
    if not REDIS_AVAILABLE:
        logger.error("Redis fallback requested but aioredis is not installed.")
        raise RuntimeError("No message bus available (Kafka down, aioredis missing).")

    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        pipe = redis.pipeline()
        for event in events:
            pipe.xadd(
                REDIS_STREAM,
                {"payload": json.dumps(event), "event_id": event.get("event_id", "")},
                id="*",  # auto-generated monotonic stream ID
            )
        await pipe.execute()
        logger.info("Redis fallback: wrote %d events to stream '%s'", len(events), REDIS_STREAM)
    finally:
        await redis.close()


async def _deduplicate(
    db: AsyncSession,
    events: List[dict],
) -> List[dict]:
    """
    Filter out events whose event_id already exists in PostgreSQL.
    Returns only the novel events that should be persisted.
    """
    incoming_ids = [e["event_id"] for e in events if "event_id" in e]
    if not incoming_ids:
        return events

    result = await db.execute(
        select(StoreEvent.event_id).where(StoreEvent.event_id.in_(incoming_ids))
    )
    existing_ids = {row[0] for row in result.fetchall()}

    novel = [e for e in events if e.get("event_id") not in existing_ids]
    duplicate_count = len(events) - len(novel)
    if duplicate_count:
        logger.info("Deduplication: skipped %d duplicate event(s)", duplicate_count)
    return novel


# ══════════════════════════════════════════════════════════════════════════════
# Route
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/ingest",
    response_model=EventResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a batch of store events (Kafka primary, Redis fallback)",
)
async def ingest_events(
    payload: EventBatch,
    db: AsyncSession = Depends(get_db),
) -> EventResponse:
    """
    Accepts up to 500 events per request.

    Processing order
    ────────────────
    1. Deduplicate against PostgreSQL by event_id.
    2. Attempt to publish novel events to Kafka (with exponential-backoff retry).
    3. On Kafka failure, fall back to Redis Streams.
    4. Persist novel events to PostgreSQL regardless of bus outcome.
    """
    raw_events: List[dict] = [e.dict() for e in payload.events]

    if not raw_events:
        return EventResponse(accepted=0, duplicates=0, bus="none", message="Empty batch.")

    # ── 1. Deduplication ──────────────────────────────────────────────────────
    novel_events = await _deduplicate(db, raw_events)
    duplicate_count = len(raw_events) - len(novel_events)

    if not novel_events:
        return EventResponse(
            accepted=0,
            duplicates=duplicate_count,
            bus="none",
            message="All events were duplicates; nothing ingested.",
        )

    # ── 2. Publish to Kafka (primary) ─────────────────────────────────────────
    bus_used = "kafka"
    producer = await _get_kafka_producer()
    try:
        if producer is None:
            raise RuntimeError("Kafka producer unavailable")
        await _send_to_kafka(producer, novel_events)
    except Exception as kafka_exc:  # noqa: BLE001
        logger.warning("Kafka unavailable (%s) — switching to Redis fallback.", kafka_exc)
        bus_used = "redis"
        try:
            await _send_to_redis_fallback(novel_events)
        except Exception as redis_exc:
            logger.error("Both Kafka and Redis fallback failed: %s", redis_exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Message bus unavailable (Kafka and Redis both failed).",
            ) from redis_exc
    finally:
        if producer is not None:
            try:
                await producer.stop()
            except Exception:  # noqa: BLE001
                pass

    # ── 3. Persist to PostgreSQL ──────────────────────────────────────────────
    try:
        db_objects = [StoreEvent(**e) for e in novel_events]
        db.add_all(db_objects)
        await db.commit()
    except Exception as db_exc:
        await db.rollback()
        logger.error("Database persist failed after bus write: %s", db_exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Events published to message bus but database persist failed.",
        ) from db_exc

    logger.info(
        "Ingested %d events via %s (skipped %d duplicates).",
        len(novel_events), bus_used, duplicate_count,
    )
    return EventResponse(
        accepted=len(novel_events),
        duplicates=duplicate_count,
        bus=bus_used,
        message=f"Accepted {len(novel_events)} event(s) via {bus_used}.",
    )
