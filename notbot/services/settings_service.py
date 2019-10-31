from notbot.context import Context, Module
from notbot.db import get_settings_dao
import logging
from typing import Awaitable

MODULE_NAME = "settings_service"
logger = logging.getLogger(__name__)


class SettingsService(Module):
    def __init__(self, context: Context):
        self.settings_dao = get_settings_dao(context)

    def get_name(self):
        return MODULE_NAME

    async def set_pprefix(self, user_id, pprefix: str):
        return await self.settings_dao.set_pprefix(user_id, pprefix)

    async def get_pprefix(self, user_id) -> Awaitable[str]:
        return await self.settings_dao.get_pprefix(user_id)

    async def del_pprefix(self, user_id):
        await self.settings_dao.del_pprefix(user_id)


def get_settings_service(context: Context) -> SettingsService:
    return context.get_or_register_module(MODULE_NAME, lambda: SettingsService(context))
