import logging
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from src.binance.monitoring import price_updates, signals, errors
from src.binance.services import handle_price_update, handle_signals
from src.config import get_settings
from src.dependencies import MongoDBDep, RedisDep


settings = get_settings()
logger = logging.getLogger(__name__)

async def publish_price_update(price: float):
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka.bootstrap_servers)
    await producer.start()
    await producer.send('price_updates', str(price).encode())
    await producer.stop()

async def consume_price_updates(db: MongoDBDep, redis: RedisDep):
    try:
        consumer = AIOKafkaConsumer('price_updates', bootstrap_servers=settings.kafka.bootstrap_servers)
        await consumer.start()
        async for msg in consumer:
            price = float(msg.value.decode())
            price_updates.labels(topic='price_updates').inc()
            await handle_price_update(price, db, redis)
    except Exception as e:
        errors.labels(type='kafka_price_updates').inc()
        logger.error(f"Price update consumer failed: {e}")

async def publish_signal(signal: str):
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka.bootstrap_servers)
    await producer.start()
    await producer.send('signals', signal.encode())
    await producer.stop()

async def consume_signals(db: MongoDBDep):
    try:
        consumer = AIOKafkaConsumer('signals', bootstrap_servers=settings.kafka.bootstrap_servers)
        await consumer.start()
        async for msg in consumer:
            signals.labels(topic='signals').inc()
            await handle_signals(msg.value.decode(), db)
    except Exception as e:
        errors.labels(type='kafka_signals').inc()
        logger.error(f"Signal consumer failed: {e}")

async def get_signal_from_queue():
    consumer = AIOKafkaConsumer(
        "signals",  # Kafka topic
        bootstrap_servers=settings.kafka.bootstrap_servers,
    )
    await consumer.start()
    try:
        async for msg in consumer:
            yield msg.value.decode()
    finally:
        await consumer.stop()