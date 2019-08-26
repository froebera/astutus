import asyncio
from .redis import Redis
from context import Module, Context

MODULE_NAME = "redis_connection"


class RedisConnection(Module):
    def __init__(self, redis_config):
        self.connection = None
        self.redis_config = redis_config

    def get_connection(self):
        if not self.connection:
            raise Exception("Redis connection has not been initialized yet")
        return self.connection

    def start(self, context):
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
    return context.get_module(MODULE_NAME)
