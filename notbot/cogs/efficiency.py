from discord.ext import commands
from ..services import get_efficiency_service
from .util import num_to_hum


class EfficiencyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.efficiency_service = get_efficiency_service(bot.context)

    @commands.command(
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
            f"The estimated damage for raid level **{player_raid_level}** and total card levels **{total_card_levels}** is **{estimated_damage_hum}**"
        )


def setup(bot):
    bot.add_cog(EfficiencyCog(bot))
