import logging
import redis.asyncio as redis
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from motor.motor_asyncio import AsyncIOMotorDatabase
from src.binance.monitoring import price_updates, signals, errors
from src.binance.services import handle_price_update, handle_signals
from src.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


async def publish_price_update(price: str):
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka.bootstrap_servers)
    await producer.start()
    await producer.send('price_updates', price.encode())
    await producer.stop()


async def consume_price_updates(db: AsyncIOMotorDatabase, r: redis.Redis):
    consumer = AIOKafkaConsumer('price_updates', bootstrap_servers=settings.kafka.bootstrap_servers)
    await consumer.start()
    try:
        async for msg in consumer:
            price = float(msg.value.decode())
            price_updates.labels(topic='price_updates').inc()
            logger.info(f"Received price update: {price}")
            await handle_price_update(price, db, r)
    except Exception as e:
        errors.labels(type='kafka_price_updates').inc()
        logger.error(f"Price update consumer failed: {e}")
    finally:
        await consumer.stop()  # Explicitly stop the consumer
        logger.info("Kafka consumer price_updates stopped")


async def publish_signal(signal: str):
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka.bootstrap_servers)
    await producer.start()
    await producer.send('signals', signal.encode())
    await producer.stop()


async def consume_signals(db: AsyncIOMotorDatabase):
    consumer = AIOKafkaConsumer('signals', bootstrap_servers=settings.kafka.bootstrap_servers)
    await consumer.start()
    try:
        async for msg in consumer:
            signals.labels(topic='signals').inc()
            logger.info(f"Received signal: {msg.value.decode()}")
            await handle_signals(msg.value.decode(), db)
    except Exception as e:
        errors.labels(type='kafka_signals').inc()
        logger.error(f"Signal consumer failed: {e}")
    finally:
        await consumer.stop()
        logger.info("Kafka consumer signals stopped")
