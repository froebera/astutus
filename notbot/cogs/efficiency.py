import logging
from discord.ext import commands
from ..services import get_efficiency_service
from .util import num_to_hum
from csv import DictReader
from ..models import RaidPlayerAttack, RaidPlayerStat
from ..services import get_raid_stat_service

logger = logging.getLogger(__name__)

from ..context import Context, Module

MODULE_NAME = "efficiency_module"


class EfficiencyModule(commands.Cog, Module):
    def __init__(self, context: Context):
        self.bot = context.get_bot()
        self.efficiency_service = get_efficiency_service(context)
        self.raid_stat_service = get_raid_stat_service(context)

    def get_name(self):
        return MODULE_NAME

    @commands.command(
        name="estimate",
        brief="Calculates your estimated average damage based on your PRL and TCL",
        description="Calculates your estimated average damage based on your PRL and TCL",
    )
    async def calculate_estimated_damage(
        self, ctx, player_raid_level: int, total_card_levels: int
    ):
        estimated_damage = self.efficiency_service.calculate_estimated_damage(
            player_raid_level, total_card_levels
        )

        estimated_damage_hum = num_to_hum(estimated_damage)
        await ctx.send(
            f"The estimated average damage for raid level **{player_raid_level}** and total card levels **{total_card_levels}** is **{estimated_damage_hum}**"
        )

    """
    Raid stat suff:
    
    new raid created on raid in ( with start time )
    raid marked as cleared on raid clear ( cleared_at set )
    last open raid will be deleted on raid cancel

    manually create raid to uplaod old data
    edit for existing raid ? ( if sb fks up raid in or clears an actual active raid )

    provide stat upload for a specific raid ( or default to last cleared )
    reupload stats ( to fix upsies )
    """

    @commands.command(name="upload_test")
    async def upload_test(self, ctx, *, stuff):
        result = []
        for row in DictReader(stuff.split("\n")):
            result.append(
                RaidPlayerAttack(
                    1,
                    str(row["ID"]),
                    str(row["Name"]),
                    int(row["Attacks"]),
                    int(row["Damage"]),
                )
            )
        await self.raid_stat_service.save_raid_player_attacks(result)

    @commands.command(name="upload_stats")
    async def upload_stats(self, ctx, *, stats):
        result = []
        for row in DictReader(stats.split("\n")):
            result.append(
                RaidPlayerStat(
                    1,
                    str(row["ID"]),
                    int(row["Raid total card level"]),
                    int(row["Raid player level"]),
                )
            )
        await self.raid_stat_service.save_raid_player_stats(result)


def setup(bot):
    context: Context = bot.context

    efficiency_module = context.get_module(MODULE_NAME)
    bot.add_cog(efficiency_module)
