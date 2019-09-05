from notbot.context import Module, Context
from .redis_connection import RedisConnection, get_redis_connection

from notbot.cogs.util import (
    QUEUE_CONFIG_KEY,
    QUEUE_ACTIVE,
    QUEUE_KEY,
    QUEUE_PROGRESS,
    QUEUE_CURRENT_USERS,
    QUEUE_SIZE,
    QUEUE_NAME,
)

import asyncio

# from .redis_connection import RedisConnection
# from .redis_connection import get_redis_connection

MODULE_NAME = "queue_dao"


class QueueDao(Module):
    def __init__(self, context: Context):
        self.connection: get_redis_connection(context)

    def get_name(self):
        return MODULE_NAME

    async def get_queue_configuration(self, guild_id, queue_name):
        return await self.connection.hgetall(
            QUEUE_CONFIG_KEY.format(guild_id, queue_name)
        )

    async def get_all_queues(self, guild_id: str):
        return await self.connection.lrange(f"raid:{guild_id}:queues")

    async def get_queued_users(self, guild_id, queue_name):
        return await self.connection.lrange(QUEUE_KEY.format(guild_id, queue_name))

    async def set_queue_active(self, guild_id, queue_name, active=1):
        return await self.connection.hset(
            QUEUE_CONFIG_KEY.format(guild_id, queue_name), QUEUE_ACTIVE, active
        )

    async def get_queue_active(self, guild_id, queue_name):
        return await self.connection.hget(
            QUEUE_CONFIG_KEY.format(guild_id, queue_name), QUEUE_ACTIVE
        )

    async def set_queue_progress(self, guild_id, queue_name, progress=1):
        return await self.connection.hset(
            QUEUE_CONFIG_KEY.format(guild_id, queue_name), QUEUE_PROGRESS, progress
        )

    async def reset_queue(self, guild_id, queue_name):
        return await asyncio.gather(
            self.connection.hdel(
                QUEUE_CONFIG_KEY.format(guild_id, queue_name), QUEUE_PROGRESS
            ),
            self.connection.hdel(
                QUEUE_CONFIG_KEY.format(guild_id, queue_name), QUEUE_ACTIVE
            ),
            self.delete_current_users(guild_id, queue_name),
            self.delete_queued_users(guild_id, queue_name),
            return_exceptions=True,
        )

    async def remove_user_from_queued_users(self, guild_id, queue_name, user_id):
        return await self.connection.lrem(
            QUEUE_KEY.format(guild_id, queue_name), user_id
        )

    async def delete_current_users(self, guild_id, queue_name):
        return await self.connection.hdel(
            QUEUE_CONFIG_KEY.format(guild_id, queue_name), QUEUE_CURRENT_USERS
        )

    async def delete_queued_users(self, guild_id, queue_name):
        return await self.connection.delete(QUEUE_KEY.format(guild_id, queue_name))

    async def remove_current_and_queued_users_from_queue(self, guild_id, queue_name):
        return await asyncio.gather(
            self.delete_queued_users(guild_id, queue_name),
            self.delete_current_users(guild_id, queue_name),
            return_exceptions=True,
        )

    async def set_current_users(self, guild_id, queue_name, user_ids):
        return await self.connection.hset(
            QUEUE_CONFIG_KEY.format(guild_id, queue_name), QUEUE_CURRENT_USERS, user_ids
        )

    async def add_user_to_queued_users(self, guild_id, queue_name, user_id):
        return await self.connection.rpush(
            QUEUE_KEY.format(guild_id, queue_name), user_id
        )

    async def set_queue_name(self, guild_id, queue_name, name):
        return await self.connection.hset(
            QUEUE_CONFIG_KEY.format(guild_id, queue_name), QUEUE_NAME, name
        )

    async def set_queue_size(self, guild_id, queue_name, size: int):
        return await self.connection.hset(
            QUEUE_CONFIG_KEY.format(guild_id, queue_name), QUEUE_SIZE, size
        )

    async def set_key(self, guild_id, queue_name, key, value):
        return await self.connection.hset(
            QUEUE_CONFIG_KEY.format(guild_id, queue_name), key, value
        )

    async def del_key(self, guild_id, queue_name, key):
        return await self.connection.hdel(
            QUEUE_CONFIG_KEY.format(guild_id, queue_name), key
        )

    async def delete_queue_configuration(self, guild_id, queue_name):
        return await self.connection.delete(
            QUEUE_CONFIG_KEY.format(guild_id, queue_name)
        )


def get_queue_dao(context: Context) -> QueueDao:
    return context.get_or_register_module(MODULE_NAME, lambda: QueueDao(context))

