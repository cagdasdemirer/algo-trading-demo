import json
import logging
import websockets
import asyncio
from fastapi.websockets import WebSocketDisconnect
from src.binance.kafka import publish_price_update
from src.binance.monitoring import errors
from src.config import get_settings


settings = get_settings()
logger = logging.getLogger(__name__)

async def binance_websocket():
    stream = settings.binance.websocket_stream
    symbol = 'btcusdt'
    interval = '1s'
    uri = f"{stream}{symbol}@kline_{interval}"
    while True:
        try:
            logger.info(f"Connecting to {uri}")
            async with websockets.connect(uri) as ws:
                while True:
                    data = await ws.recv()
                    data = json.loads(data)
                    await publish_price_update(data['k']['c'])
        except (WebSocketDisconnect, ConnectionError):
            errors.labels(type='binance_websocket').inc()
            logger.error("Connection error. Retrying...")
            await asyncio.sleep(5)