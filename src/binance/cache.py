import logging
import redis.asyncio as redis
from src.config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)

redis_pool = redis.ConnectionPool.from_url(settings.get_redis_uri)


async def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=redis_pool)
