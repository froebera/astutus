from typing import Union, Optional
import logging
from discord.ext import commands
from ..services import (
    get_efficiency_service,
    get_raid_stat_service,
    EFFICIENCY_CONFIG_KEYS,
)
from .util import (
    num_to_hum,
    EFFICIENCY_CARD_PERC,
    EFFICIENCY_REDUCTION1,
    EFFICIENCY_REDUCTION2,
    EFFICIENCY_LETHAL_BONUS,
)

from csv import DictReader
from ..models import RaidPlayerAttack, RaidPlayerStat
from .checks import has_raid_management_permissions

logger = logging.getLogger(__name__)

from ..context import Context, Module

MODULE_NAME = "efficiency_module"


class EfficiencyConfigKey(commands.Converter):
    async def convert(self, ctx, argument):
        if argument in EFFICIENCY_CONFIG_KEYS:
            return argument

        raise commands.BadArgument(
            f"Config key must be one of {', '.join(EFFICIENCY_CONFIG_KEYS)} "
        )


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

    @commands.command(
        name="efficiency",
        brief="Calculates your efficiency ( including lethal bonus if supplied )",
        description="Calculates your efficiency ( including lethal bonus if supplied )",
    )
    async def calculate_efficiency(
        self,
        ctx,
        player_raid_level: int,
        total_card_levels: int,
        average_damage: int,
        rounds: Optional[int] = 0,
    ):
        efficiency = self.efficiency_service.calculate_efficiency_with_lethal_bonus(
            player_raid_level, total_card_levels, average_damage, rounds * 4, rounds * 4
        )

        await ctx.send(
            "Efficiency for PRL **{}**, TCL **{}** and an average damage of **{}** {}: **{}%**".format(
                player_raid_level,
                total_card_levels,
                average_damage,
                "(including lethal bonus for {} rounds / {} attacks)".format(
                    rounds, rounds * 4
                )
                if rounds > 0
                else "",
                round(efficiency * 100, 2),
            )
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

    # @commands.command(name="upload_test")
    # async def upload_test(self, ctx, *, stuff):
    #     result = []
    #     for row in DictReader(stuff.split("\n")):
    #         result.append(
    #             RaidPlayerAttack(
    #                 1,
    #                 str(row["ID"]),
    #                 str(row["Name"]),
    #                 int(row["Attacks"]),
    #                 int(row["Damage"]),
    #             )
    #         )
    #     await self.raid_stat_service.save_raid_player_attacks(result)

    # @commands.command(name="upload_stats")
    # async def upload_stats(self, ctx, *, stats):
    #     result = []
    #     for row in DictReader(stats.split("\n")):
    #         result.append(
    #             RaidPlayerStat(
    #                 1,
    #                 str(row["ID"]),
    #                 int(row["Raid total card level"]),
    #                 int(row["Raid player level"]),
    #             )
    #         )
    #     await self.raid_stat_service.save_raid_player_stats(result)

    @commands.group(name="efficiencyconfig")
    @commands.check(has_raid_management_permissions)
    async def efficiency_config(self, ctx):
        pass

    @efficiency_config.command(name="show")
    @commands.check(has_raid_management_permissions)
    async def efficiency_config_show(self, ctx):
        efficiency_config = self.efficiency_service.get_efficiency_config()

        tmp = []
        for key, value in efficiency_config.items():
            tmp.append(f"**{key}**: {value}")

        await ctx.send("**Efficiency configuration**:\n\n{}".format("\n".join(tmp)))

    @efficiency_config.command(name="set")
    @commands.check(has_raid_management_permissions)
    async def efficiency_config_set(
        self, ctx, config_key: Union[EfficiencyConfigKey], value
    ):
        if config_key in [
            EFFICIENCY_CARD_PERC,
            EFFICIENCY_REDUCTION1,
            EFFICIENCY_REDUCTION2,
            EFFICIENCY_LETHAL_BONUS,
        ]:
            converted_value = float(value)
        else:
            converted_value = int(value)

        await self.efficiency_service.set_efficiency_config_value(
            config_key, converted_value
        )
        await ctx.send(
            f":white_check_mark: Successfully set **{config_key}** to {converted_value}"
        )


def setup(bot):
    context: Context = bot.context

    efficiency_module = context.get_module(MODULE_NAME)
    bot.add_cog(efficiency_module)
