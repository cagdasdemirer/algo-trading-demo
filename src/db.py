from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
import logging
import asyncio

from src.binance.monitoring import errors
from src.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class MongoDBSessionManager:
    def __init__(self, uri: str, db_name: str, **client_kwargs):
        if not uri or not db_name:
            raise ValueError("Both MongoDB URI and database name are required.")
        self.uri = uri
        self.db_name = db_name
        self.client_kwargs = client_kwargs
        self.client: Optional[AsyncIOMotorClient] = None

    async def connect(self, retries: int = 3, delay: int = 5):
        for attempt in range(retries):
            try:
                if not self.client:
                    self.client = AsyncIOMotorClient(
                        self.uri,
                        maxPoolSize=100,
                        minPoolSize=10,
                        waitQueueTimeoutMS=30000,
                        socketTimeoutMS=30000,
                        connectTimeoutMS=5000,
                        **self.client_kwargs
                    )
                await self.client.admin.command("ping")
                logger.info("MongoDB connection established.")
                return
            except Exception as e:
                errors.labels(type='db_connect').inc()
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                self.client = None  # Reset client for clean retries
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError("Failed to connect to MongoDB after multiple retries.")

    def get_db(self):
        if not self.client:
            raise RuntimeError("MongoDB client is not connected. Call `connect()` first.")
        return self.client[self.db_name]

    async def close(self):
        if self.client:
            self.client.close()
            self.client = None
            logger.info("MongoDB connection closed.")

    async def __aenter__(self):
        await self.connect()
        return self.get_db()

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()


sessionmanager = MongoDBSessionManager(
    uri=settings.get_db_uri,
    db_name=settings.db.name
)


async def get_db():
    if not sessionmanager.client:
        await sessionmanager.connect()
    return sessionmanager.get_db()
