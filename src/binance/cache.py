import logging
import redis.asyncio as redis
from src.config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)


redis_pool = redis.ConnectionPool(
        host=settings.cache.host,
        port=settings.cache.port,
        db=settings.cache.db,
        max_connections=100,
        decode_responses=True,
    )

async def get_redis():
    redis_client = redis.Redis(connection_pool=redis_pool)
    return redis_client


