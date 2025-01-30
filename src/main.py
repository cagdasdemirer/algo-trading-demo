import asyncio
from contextlib import asynccontextmanager

import psutil
import uvicorn
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from fastapi.middleware.cors import CORSMiddleware

from src.binance import monitoring
from src.binance.cache import get_redis, redis_pool
from src.binance.kafka import consume_price_updates, consume_signals
from src.binance.monitoring import errors
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

        # 6. Start background task for system resource monitoring
        monitor_task = asyncio.create_task(monitor_system_resources())
        tasks.append(monitor_task)
        yield
    except Exception as e:
        errors.labels(type='startup').inc()
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


async def monitor_system_resources():
    while True:
        # Get CPU usage (as a percentage)
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_info = psutil.virtual_memory()

        monitoring.cpu_usage.set(cpu_percent)  # Update the CPU usage gauge
        monitoring.memory_usage.set(memory_info.used)  # Update memory usage in bytes

        await asyncio.sleep(60)
app = FastAPI(
    lifespan=lifespan,
    title = settings.app.name,
    version = settings.app.version,
    contact = {"name": settings.admin.name, "email": settings.admin.email},
    swagger_ui_parameters = {"defaultModelsExpandDepth": -1},
    description = "This API provides insights on Algorithmic Trading Signals and Price Updates for Binance.",
    docs_url = "/",
)

# Initialize Prometheus
prom = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_instrument_requests_inprogress=True
)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = "/api/v1"
app.include_router(prefix=api_prefix, router=binance_router)
prom.expose(app, endpoint=api_prefix+"/metrics/prometheus")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=False,
    )
