from typing import Annotated
import redis
from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from src.binance.cache import get_redis
from src.db import get_db

MongoDBDep = Annotated[AsyncIOMotorDatabase, Depends(get_db)]

RedisDep = Annotated[redis.Redis, Depends(get_redis)]
