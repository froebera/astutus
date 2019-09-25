from notbot.context import Context, Module
from .postgres_dao_base import PostgresDaoBase

MODULE_NAME = "raid_stats_dao"


class RaidStatsDao(PostgresDaoBase, Module):
    async def test_transaction_1(self):
        pass

    async def test_transaction_2(self):
        pass


def get_raid_stats_dao(context: Context):
    return context.get_or_register_module(MODULE_NAME, lambda: RaidStatsDao(context))
