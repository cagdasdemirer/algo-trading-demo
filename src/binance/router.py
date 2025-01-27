import logging
import time
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError
from fastapi import APIRouter
from fastapi.websockets import WebSocket
from pymongo.errors import PyMongoError
from redis import RedisError
from fastapi.websockets import WebSocketDisconnect
from src.binance.kafka import get_signal_from_queue
from src.binance.monitoring import errors, latency
from src.config import get_settings
from src.dependencies import MongoDBDep, RedisDep

binance_router = APIRouter(
    prefix="/binance",
    tags=["binance"],
)

logger = logging.getLogger(__name__)

settings = get_settings()

@binance_router.websocket("/signals")
async def signal_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        async for signal in get_signal_from_queue():
            with latency.labels(operation='websocket_send').time():
                await websocket.send_json({"signal": signal, "timestamp": time.time()})
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        errors.labels(type='websocket').inc()
        logger.error(f"WebSocket error: {e}")


@binance_router.get("/health")
async def health_check(db: MongoDBDep, r: RedisDep):
    try:
        await db.command("ping")

        await r.ping()

        consumer = AIOKafkaConsumer(bootstrap_servers=settings.kafka.bootstrap_servers)
        await consumer.start()
        await consumer.stop()

        return {"status": "OK"}
    except (RedisError, KafkaConnectionError, PyMongoError) as e:
        return {"status": "DOWN", "error": str(e)}, 503