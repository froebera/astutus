import asyncio
from .redis import Redis
from notbot.context import Module, Context
from ..services.config_service import get_config_service

MODULE_NAME = "redis_connection"
CONFIG_KEY = "REDIS"


class RedisConnection(Module):
    def __init__(self, context: Context):
        self.connection = None
        self.redis_config = None
        self.config_service = get_config_service(context)

    def get_connection(self) -> Redis:
        if not self.connection:
            raise Exception("Redis connection has not been initialized yet")
        return self.connection

    def start(self):
        self.redis_config = self.config_service.get_config(CONFIG_KEY)
        self.connection = Redis()
        loop = asyncio.get_event_loop()

        loop.run_until_complete(
            self.connection.connect_pool(
                self.redis_config["host"],
                self.redis_config["port"],
                pw=self.redis_config.get("password", None),
            )
        )

    def get_name(self):
        return MODULE_NAME


def get_redis_connection(context: Context) -> RedisConnection:
    return context.get_or_register_module(MODULE_NAME, lambda: RedisConnection(context))

