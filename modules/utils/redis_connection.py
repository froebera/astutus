from .redis import Redis
import asyncio


class RedisConnection:
    def __init__(self):
        self.pool = None

    def get_or_create_redis_connection(self, redis_config):
        if not self.pool:
            self.pool = Redis()
            loop = asyncio.get_event_loop()

            loop.run_until_complete(
                self.pool.connect_pool(
                    redis_config["host"],
                    redis_config["port"],
                    pw=redis_config.get("password", None),
                )
            )
        return self.pool

    def get_redis_connection(self):
        if not self.pool:
            raise Exception("Redis connection is not initialized yet")
        return self.pool


con = RedisConnection()


def get_redis_connection():
    return con.get_redis_connection()

