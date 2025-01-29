import logging
import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorDatabase
from tenacity import retry, stop_after_attempt, wait_exponential
from src.binance.crud import check_crossover, save_price_update_to_db, save_order_to_db
from src.config import get_settings
import ccxt.async_support as ccxt


settings = get_settings()
logger = logging.getLogger(__name__)


async def handle_price_update(price: float, db: AsyncIOMotorDatabase, r: redis.Redis):
    try:
        await check_crossover(r, price)
        await save_price_update_to_db(db, price)
    except Exception as e:
        logger.error(f"Price update failed: {e}")


async def handle_signals(signal: str, db: AsyncIOMotorDatabase):
    try:
        order = await place_order(signal)
        await save_order_to_db(db, order)
    except Exception as e:
        logger.error(f"Order processing failed: {e}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=lambda _: logger.warning("Retrying order...")
)
async def place_order(signal: str):
    exchange = ccxt.binance({
        'apiKey': settings.binance.api_key,
        'secret': settings.binance.secret_key,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'spot',
        },
    })

    exchange.set_sandbox_mode(True)
    try:
        order = await exchange.create_market_order(
            symbol='BTC/USDT',
            side='buy' if signal == "BUY" else 'sell',
            amount=0.001
        )
        await exchange.close()
        logging.info(f"Order placed: {order}")
        return order
    except Exception as e:
        logger.error(f"Final order failure: {e}")
        raise
