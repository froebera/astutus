import asyncio
from .redis import Redis
from notbot.context import Module, Context
from ..services.config_service import get_config_service
from contextlib import asynccontextmanager

MODULE_NAME = "redis_connection"
CONFIG_KEY = "REDIS"


class RedisConnection(Module):
    def __init__(self, context: Context):
        self.connection: Redis = None
        self.redis_config = None
        self.config_service = get_config_service(context)

    def get_connection(self) -> Redis:
        if not self.connection:
            raise Exception("Redis connection has not been initialized yet")
        return self.connection

    def start(self):
        self.redis_config = self.config_service.get_config(CONFIG_KEY)
        self.connection: Redis = Redis()
        loop = asyncio.get_event_loop()

        loop.run_until_complete(
            self.connection.connect_pool(
                self.redis_config["host"],
                self.redis_config["port"],
                pw=self.redis_config.get("password", None),
            )
        )

    async def multi(self):
        await self.connection.connection_pool.execute("MULTI")

    async def exec(self):
        await self.connection.connection_pool.execute("EXEC")

    async def discard(self):
        await self.connection.connection_pool.execute("DISCARD")

    @asynccontextmanager
    async def with_transaction(self):
        pool = self.connection.connection_pool
        await self.multi()
        try:
            yield pool
        except Exception as error:
            await self.discard()
            raise

        await self.exec()

    def get_name(self):
        return MODULE_NAME


def get_redis_connection(context: Context) -> RedisConnection:
    return context.get_or_register_module(MODULE_NAME, lambda: RedisConnection(context))

