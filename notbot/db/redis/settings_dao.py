from notbot.cogs.util import PPREFIX
from notbot.context import Context, Module

from .redis import Redis
from .redis_connection import get_redis_connection

MODULE_NAME = "settings_dao"


class SettingsDao(Module):
    def __init__(self, context: Context):
        self.redis_connection_module = get_redis_connection(context)
        self.connection: Redis = None

    def start(self):
        self.connection = self.redis_connection_module.get_connection()

    def get_name(self):
        return MODULE_NAME

    async def get_pprefix(self, user_id):
        return await self.connection.hget(PPREFIX, user_id)

    async def set_pprefix(self, user_id, pprefix: str):
        return await self.connection.hset(PPREFIX, user_id, pprefix)

    async def del_pprefix(self, user_id):
        return await self.connection.hdel(PPREFIX, user_id)


def get_settings_dao(context: Context) -> SettingsDao:
    return context.get_or_register_module(MODULE_NAME, lambda: SettingsDao(context))
