"""
Kafka-based event streaming for multi-store scaling.
Fallback to Redis Streams if Kafka unavailable.
"""

import json
import logging
from typing import Optional
import threading

logger = logging.getLogger(__name__)

class KafkaEventEmitter:
    def __init__(self, bootstrap_servers: str = "localhost:9092", topic: str = "store-events"):
        """
        Args:
            bootstrap_servers: Kafka broker addresses
            topic: Kafka topic to publish to
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer = None
        self.use_redis_fallback = False
        self.redis_client = None
        self._init_kafka()
    
    def _init_kafka(self) -> None:
        try:
            from kafka import KafkaProducer
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',  # Wait for all replicas
                retries=3,
            )
            logger.info("kafka_producer_initialized brokers=%s", self.bootstrap_servers)
        except Exception as e:
            logger.warning("kafka_init_failed error=%s falling_back_to_redis", e)
            self._init_redis_fallback()
    
    def _init_redis_fallback(self) -> None:
        try:
            import redis
            self.redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
            self.redis_client.ping()
            self.use_redis_fallback = True
            logger.info("redis_streams_fallback_initialized")
        except Exception as e:
            logger.error("redis_init_failed error=%s", e)
    
    def emit(self, event: dict) -> None:
        """Publish event to Kafka/Redis."""
        if self.producer and not self.use_redis_fallback:
            try:
                future = self.producer.send(self.topic, event)
                future.get(timeout=5)
            except Exception as e:
                logger.warning("kafka_send_failed error=%s trying_redis", e)
                self._fallback_to_redis(event)
        elif self.use_redis_fallback:
            self._fallback_to_redis(event)
    
    def _fallback_to_redis(self, event: dict) -> None:
        if self.redis_client:
            try:
                self.redis_client.xadd(f"events:{event['store_id']}", '*', json.dumps(event))
            except Exception as e:
                logger.error("redis_emit_failed error=%s", e)
    
    def flush(self) -> None:
        if self.producer:
            self.producer.flush()
    
    def close(self) -> None:
        if self.producer:
            self.producer.close()
        if self.redis_client:
            self.redis_client.close()
