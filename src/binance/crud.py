import logging
import time
from datetime import datetime
from typing import Union
import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorDatabase
from redis import RedisError

from src.binance.monitoring import errors

logger = logging.getLogger(__name__)


async def save_price_update_to_db(db: AsyncIOMotorDatabase, price: float):
    try:
        price_updates_collection = db.get_collection("price_updates")
        await price_updates_collection.insert_one({
            "price": price,
            "timestamp": datetime.utcnow(),
            "symbol": "BTC/USDT"
        })
        logger.info(f"Price saved to db: {price}")
    except Exception as e:
        errors.labels(type='save_price_update_to_db').inc()
        logger.error(f"Price save to db failed: {e}")


async def save_order_to_db(db: AsyncIOMotorDatabase, order_data: dict):
    try:
        orders_collection = db.get_collection("orders")
        await orders_collection.update_one(
            {"order_id": order_data["id"]},
            {"$set": {
                "status": order_data["status"],
                "filled": order_data["filled"],
                "timestamp": datetime.utcnow()
            }},
            upsert=True
        )
        logger.info(f"Order saved to db with id: {order_data['id']}")
    except Exception as e:
        errors.labels(type='save_order_to_db').inc()
        logger.error(f"Order save to db failed: {e}")


async def update_redis_window(r: redis.Redis, price: float):
    try:
        t = str(round(time.time() * 1000))
        async with r.pipeline(transaction=True) as pipe:
            await pipe.zadd("price_window", {t: str(price)})
            await pipe.zremrangebyrank("price_window", 0, -201)
            await pipe.execute()
        logger.info("Redis window updated")
    except RedisError as e:
        errors.labels(type='update_redis_window').inc()
        logger.error(f"Redis update failed: {e}")


async def check_crossover(r: redis.Redis, price: float) -> Union[str, None]:
    try:
        prev_sma50, prev_sma200 = await get_previous_sma(r)
        if prev_sma50 is None or prev_sma200 is None:
            await update_redis_window(r, price)
            sma50 = await calculate_sma(50, r)
            sma200 = await calculate_sma(200, r)
        else:
            sma50, sma200 = await calculate_incremental_sma(r, price, prev_sma50, prev_sma200)
            await update_redis_window(r, price)

        if sma50 is None or sma200 is None:
            logger.warning("Insufficient data for SMA calculation. Skipping crossover check.")
            return None
        elif prev_sma50 is None or prev_sma200 is None:
            await store_sma_state(sma50, sma200, r)
            logger.info("Necessary state saved for future incremental SMA calculations.")
            return None

        await store_sma_state(sma50, sma200, r)

        signal = None

        if prev_sma50 < prev_sma200 and sma50 > sma200:
            signal = "BUY"
        elif prev_sma50 > prev_sma200 and sma50 < sma200:
            signal = "SELL"

        if signal:
            from src.binance.kafka import publish_signal
            logger.info(f"Signal detected: {signal}")
            await publish_signal(signal)
    except Exception as e:
        errors.labels(type='check_crossover').inc()
        logger.error(f"Crossover check failed: {e}")
        return None


async def calculate_sma(window: int, r: redis.Redis) -> Union[float, None]:
    try:
        price_values = await r.zrevrange("price_window", 0, window - 1, withscores=True)
        if len(price_values) < window:
            logger.warning(
                f"Not enough data to calculate SMA for window {window}. Required: {window}, Found: {len(price_values)}")
            return None
        return sum(float(price) for _, price in price_values) / window

    except RedisError as e:
        errors.labels(type='calculate_sma').inc()
        logger.error(f"SMA calculation failed: {e}")
        return None


async def calculate_incremental_sma(r: redis.Redis, price: float, prev_sma50: float, prev_sma200: float):
    oldest_values = await r.zrange("price_window", 0, 0, withscores=True)
    _, oldest_price = oldest_values[0]

    sma50 = prev_sma50 + (price - float(oldest_price)) / 50
    sma200 = prev_sma200 + (price - float(oldest_price)) / 200

    return sma50, sma200


async def store_sma_state(sma50: float, sma200: float, r: redis.Redis):
    try:
        await r.hset("sma_state", mapping={"sma50": sma50, "sma200": sma200})
    except RedisError as e:
        errors.labels(type='store_sma_state').inc()
        logger.error(f"State save failed: {e}")


async def get_previous_sma(r: redis.Redis):
    try:
        values = await r.hmget("sma_state", ["sma50", "sma200"])
        return float(values[0] if values[0] else 0) or None, float(values[1] if values[1] else 0) or None
    except RedisError as e:
        errors.labels(type='get_previous_sma').inc()
        logger.error(f"State load failed: {e}")
        return None, None
