from notbot.context import Module, Context
from .redis_connection import RedisConnection, get_redis_connection
from notbot.cogs.util import (
    RAID_CONFIG_KEY,
    RAID_MANAGEMENT_ROLES,
    RAID_TIMER_ROLES,
    RAID_COUNTDOWNMESSAGE,
    RAID_REMINDED,
    RAID_RESET,
    RAID_INIT,
    RAID_SPAWN,
    RAID_COOLDOWN,
    RAID_CLAN_ROLES,
)
from .redis import Redis

# from .redis_connection import RedisConnection
# from .redis_connection import get_redis_connection

MODULE_NAME = "raid_dao"


class RaidDao(Module):
    def __init__(self, context: Context):
        self.redis_connection_module = get_redis_connection(context)
        self.redis_connection: Redis = None

    def start(self):
        self.redis_connection = self.redis_connection_module.get_connection()

    def get_name(self):
        return MODULE_NAME

    async def get_raid_configuration(self, guild_id):
        return await self.redis_connection.hgetall(RAID_CONFIG_KEY.format(guild_id))

    async def raid_config_exists(self, guild_id):
        return await self.redis_connection.exists(RAID_CONFIG_KEY.format(guild_id))

    async def get_raid_management_roles(self, guild_id):
        return await self.redis_connection.hget(
            RAID_CONFIG_KEY.format(guild_id), RAID_MANAGEMENT_ROLES
        )

    async def get_raid_timer_roles(self, guild_id):
        return await self.redis_connection.hget(
            RAID_CONFIG_KEY.format(guild_id), RAID_TIMER_ROLES
        )

    async def get_clan_roles(self, guild_id):
        return await self.redis_connection.hget(
            RAID_CONFIG_KEY.format(guild_id), RAID_CLAN_ROLES
        )

    async def set_countdown_message(self, guild_id, msg_id):
        return await self.redis_connection.hset(
            RAID_CONFIG_KEY.format(guild_id), RAID_COUNTDOWNMESSAGE, msg_id
        )

    async def set_cooldown_reminded(self, guild_id):
        return await self.redis_connection.hset(
            RAID_CONFIG_KEY.format(guild_id), RAID_REMINDED, 1
        )

    async def set_raid_reset(self, guild_id, reset):
        return await self.redis_connection.hset(
            RAID_CONFIG_KEY.format(guild_id), RAID_RESET, reset
        )

    async def set_raid_init(self, guild_id):
        return await self.redis_connection.hset(
            RAID_CONFIG_KEY.format(guild_id), RAID_INIT, 1
        )

    async def set_raid_spawn(self, guild_id, spawn):
        return await self.redis_connection.hset(
            RAID_CONFIG_KEY.format(guild_id), RAID_SPAWN, spawn
        )

    async def set_raid_cooldown(self, guild_id, cooldown):
        return await self.redis_connection.hset(
            RAID_CONFIG_KEY.format(guild_id), RAID_COOLDOWN, cooldown
        )

    async def set_key(self, guild_id, key, value):
        return await self.redis_connection.hset(
            RAID_CONFIG_KEY.format(guild_id), key, value
        )

    async def del_key(self, guild_id, key):
        return await self.redis_connection.hdel(RAID_CONFIG_KEY.format(guild_id), key)

    # TODO fix key
    async def add_queue(self, guild_id, queue_name):
        return await self.redis_connection.rpush(f"raid:{guild_id}:queues", queue_name)

    async def remove_queue(self, guild_id, queue_name):
        return await self.redis_connection.lrem(f"raid:{guild_id}:queues", queue_name)


def get_raid_dao(context: Context) -> RaidDao:
    return context.get_or_register_module(MODULE_NAME, lambda: RaidDao(context))
