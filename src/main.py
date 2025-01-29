import asyncio
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from src.binance.cache import get_redis, redis_pool
from src.binance.kafka import consume_price_updates, consume_signals
from src.binance.router import binance_router
from src.binance.websocket import binance_websocket
from src.config import get_settings
from src.db import sessionmanager, get_db
import logging

settings = get_settings()

logging.basicConfig(level=settings.app.log_level, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = []
    try:
        # 1. Connect to database
        await sessionmanager.connect()
        logger.info("Database ready")

        # 2. Start WebSocket connection
        ws_task = asyncio.create_task(binance_websocket())
        tasks.append(ws_task)

        # 3. Prepare connections
        r = await get_redis()
        db = await get_db()

        # 4. Clear cache
        await r.flushdb()

        # 5. Start Kafka consumers
        kafka_price_task = asyncio.create_task(consume_price_updates(db=db, r=r))
        kafka_signal_task = asyncio.create_task(consume_signals(db=db))

        tasks.extend([kafka_price_task, kafka_signal_task])
        logger.info("Kafka consumers started")
        yield

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    finally:
        logger.info("Shutting down...")
        for task in reversed(tasks):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.debug(f"Task {task.get_name()} cancelled")
                except Exception as e:
                    logger.warning(f"Task shutdown error: {e}")

        await sessionmanager.close()
        logger.info("Database closed")
        await redis_pool.disconnect()
        logger.info("Redis pool closed")
app = FastAPI(lifespan=lifespan)
# Prometheus metrics
Instrumentator().instrument(app).expose(app)

app.include_router(binance_router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app.host,
        port=settings.app.port,
        workers=4,
        reload=False,
    )
