from functools import lru_cache
from dotenv import find_dotenv, load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path)

class AdminSettings(BaseSettings):
    email: str
    name: str

    model_config = SettingsConfigDict(env_prefix="ADMIN_")

class AppSettings(BaseSettings):
    name: str = "algotrading-api"
    version: str = "1.0.0"
    port: int = 8000
    host: str = "localhost"
    log_level: str = "INFO"

    class Config:
        env_prefix = "APP_"

class CacheSettings(BaseSettings):
    host: str
    port: int
    db: int

    model_config = SettingsConfigDict(env_prefix="CACHE_")

class KafkaSettings(BaseSettings):
    bootstrap_servers: str

    model_config = SettingsConfigDict(env_prefix="KAFKA_")

class DatabaseSettings(BaseSettings):
    host: str
    port: int
    name: str
    username: str
    password: str

    model_config = SettingsConfigDict(env_prefix="DB_")

class BinanceSettings(BaseSettings):
    api_key: str
    secret_key: str
    websocket_uri: str

    model_config = SettingsConfigDict(env_prefix="BINANCE_")

class Settings(BaseSettings):
    admin: AdminSettings
    app: AppSettings
    cache: CacheSettings
    db: DatabaseSettings
    binance: BinanceSettings
    kafka: KafkaSettings

    model_config = SettingsConfigDict(env_file=dotenv_path if dotenv_path else None)

    @property
    def get_db_uri(self) -> str:
        return f"mongodb://{self.db.username}:{self.db.password}@{self.db.host}:{self.db.port}"

    @property
    def get_redis_uri(self) -> str:
        return f"redis://{self.cache.host}:{self.cache.port}"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        **{
            "admin": AdminSettings().model_dump(),
            "app": AppSettings().model_dump(),
            "cache": CacheSettings().model_dump(),
            "db": DatabaseSettings().model_dump(),
            "binance": BinanceSettings().model_dump(),
            "kafka": KafkaSettings().model_dump()
        }
    )