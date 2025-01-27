import websockets
import asyncio
from fastapi.websockets import WebSocketDisconnect
from src.binance.kafka import publish_price_update
from src.config import get_settings

settings = get_settings()

async def binance_websocket():
    uri = settings.binance.websocket_uri
    while True:
        try:
            async with websockets.connect(uri) as ws:
                while True:
                    data = await ws.recv()
                    price = (float(data['bids'][0][0]) + float(data['asks'][0][0])) / 2
                    await publish_price_update(price)
        except (WebSocketDisconnect, ConnectionError):
            await asyncio.sleep(5)


