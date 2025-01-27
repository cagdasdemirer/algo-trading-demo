import logging
import redis
from tenacity import retry, stop_after_attempt, wait_exponential
from src.binance.crud import save_price_update_to_db, save_order_to_db, get_previous_sma, store_sma_state, update_redis_window
from src.config import get_settings
import ccxt.async_support as ccxt
from src.dependencies import MongoDBDep, RedisDep

settings = get_settings()
logger = logging.getLogger(__name__)

exchange = ccxt.binance({
    'apiKey': settings.binance.api_key,
    'secret': settings.binance.secret_key,
    'enableRateLimit': True
})


async def handle_price_update(price: float, db: MongoDBDep, r: RedisDep):
    from src.binance.kafka import publish_signal
    try:
        await save_price_update_to_db(db, price)
        await update_redis_window(price, r)
        signal = await check_crossover()
        if signal:
            await publish_signal(signal)
    except Exception as e:
        logger.error(f"Price update failed: {e}")


async def handle_signals(signal: str, db: MongoDBDep):
    from src.binance.kafka import publish_signal
    try:
        order = await place_order(signal, db)
        await publish_signal(order)
    except Exception as e:
        logger.error(f"Order processing failed: {e}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=lambda _: logger.warning("Retrying order...")
)
async def place_order(signal: str, db: MongoDBDep):
    try:
        order = await exchange.create_market_order(
            symbol='BTC/USDT',
            side='buy' if signal == "BUY" else 'sell',
            amount=0.001
        )
        await save_order_to_db(db, order)
        return order
    except Exception as e:
        logger.error(f"Final order failure: {e}")
        raise


async def calculate_sma(window: int, r: RedisDep) -> float:
    try:
        prices = await r.zrevrange("price_window", 0, window - 1)
        if len(prices) < window:
            return 0.0
        return sum(float(price) for price in prices) / window
    except redis.RedisError as e:
        logger.error(f"SMA calculation failed: {e}")
        return 0.0


async def check_crossover():
    try:
        sma50 = await calculate_sma(50,RedisDep)
        sma200 = await calculate_sma(200,RedisDep)
        prev_sma50, prev_sma200 = await get_previous_sma(RedisDep)

        signal = None
        if prev_sma50 < prev_sma200 and sma50 > sma200:
            signal = "BUY"
        elif prev_sma50 > prev_sma200 and sma50 < sma200:
            signal = "SELL"

        if signal:
            await store_sma_state(sma50, sma200, RedisDep)

        return signal
    except Exception as e:
        logger.error(f"Crossover check failed: {e}")
        return None





