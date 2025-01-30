import logging
from asyncio import CancelledError, sleep
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError
from fastapi import APIRouter
from pymongo.errors import PyMongoError
from redis import RedisError
from src.binance.monitoring import errors, latency
from src.config import get_settings
from src.dependencies import MongoDBDep, RedisDep

binance_router = APIRouter(
    prefix="/binance",
    tags=["binance"],
)

logger = logging.getLogger(__name__)

settings = get_settings()


@binance_router.get("/health")
async def health_check(db: MongoDBDep, r: RedisDep):
    try:
        await db.command("ping")

        await r.ping()

        consumer = AIOKafkaConsumer(bootstrap_servers=settings.kafka.bootstrap_servers)
        await consumer.start()

        # small delay to ensure Kafka consumer is ready
        await sleep(0.2)

        await consumer.stop()

        return {"status": "OK"}
    except (RedisError, KafkaConnectionError, PyMongoError, CancelledError) as e:
        errors.labels(type='health_check').inc()
        return {"status": "DOWN", "error": str(e)}, 503