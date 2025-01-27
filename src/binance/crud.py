import logging
import time
from datetime import datetime

import redis

from src.dependencies import MongoDBDep, RedisDep

logger = logging.getLogger(__name__)


async def save_price_update_to_db(db: MongoDBDep, price: float):
    try:
        await db.price_updates.insert_one({
            "price": price,
            "timestamp": datetime.utcnow(),
            "symbol": "BTC/USDT"
        })
    except Exception as e:
        logger.error(f"Price save failed: {e}")


async def save_order_to_db(db: MongoDBDep, order_data: dict):
    try:
        await db.orders.update_one(
            {"order_id": order_data["id"]},
            {"$set": {
                "status": order_data["status"],
                "filled": order_data["filled"],
                "timestamp": datetime.utcnow()
            }},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Order save failed: {e}")


async def store_sma_state(sma50: float, sma200: float, r: RedisDep):
    try:
        await r.hset("sma_state",
                     mapping={"sma50": sma50, "sma200": sma200}
                     )
    except redis.RedisError as e:
        logger.error(f"State save failed: {e}")


async def get_previous_sma(r: RedisDep):
    try:
        values = await r.hmget("sma_state", ["sma50", "sma200"])
        return float(values[0] or 0), float(values[1] or 0)
    except redis.RedisError as e:
        logger.error(f"State load failed: {e}")
        return 0.0, 0.0


async def update_redis_window(price: float, r: RedisDep):
    try:
        async with r.pipeline(transaction=True) as pipe:
            pipe.zadd("price_window", {str(price): time.time()})
            pipe.zremrangebyrank("price_window", 0, -200)
            await pipe.execute()
    except redis.RedisError as e:
        logger.error(f"Redis update failed: {e}")


async def batch_update(prices: list[float], r: RedisDep):
    async with r.pipeline() as pipe:
        for price in prices:
            pipe.zadd("price_window", {str(price): time.time()})
        await pipe.execute()
