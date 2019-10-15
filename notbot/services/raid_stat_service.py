import logging
import asyncio
from ..context import Context, Module
from ..db import get_raid_postgres_dao
from notbot.models import Raid, RaidPlayerAttack
from typing import List

MODULE_NAME = "raid_stat_service"
logger = logging.getLogger(__name__)


class RaidStatService(Module):
    def __init__(self, context: Context):
        self.raid_postgres_dao = get_raid_postgres_dao(context)

    def get_name(self):
        return MODULE_NAME

    async def get_uncompleted_raids(self, guild_id):
        return await self.raid_postgres_dao.get_uncompleted_raids(guild_id)

    async def get_last_completed_raids(self, guild_id):
        return await self.raid_postgres_dao.get_last_completed_raids(guild_id)

    async def save_raid_player_attacks(self, attacks: List[RaidPlayerAttack]):
        return await self.raid_postgres_dao.save_raid_player_attacks(attacks)

    async def check_if_attacks_exist(self, guild_id, raid_id):
        return await self.raid_postgres_dao.check_if_attacks_exist(guild_id, raid_id)

    async def has_raid_permission_and_raid_exists(self, guild_id, raid_id):
        return await self.raid_postgres_dao.has_raid_permission_and_raid_exists(
            guild_id, raid_id
        )

    async def get_raid_list(self, guild_id):
        """
            returns the last 10 completed last 10 uncompleted raids
        """

        return await asyncio.gather(
            self.get_uncompleted_raids(guild_id),
            self.get_last_completed_raids(guild_id),
            return_exceptions=True,
        )


def get_raid_stat_service(context: Context) -> RaidStatService:
    return context.get_or_register_module(MODULE_NAME, lambda: RaidStatService(context))
