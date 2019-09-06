from discord.ext import commands
from csv import DictReader
from ..context import Context, Module

MODULE_NAME = "stats_module"


class RaidStatsModule(commands.Cog, Module):
    def __init__(self, context: Context):
        self.bot = context.get_bot()

    @commands.group(name="stats", invoke_without_command=True)
    async def stats(self, ctx):
        pass

    @stats.group(name="raid", invoke_without_command=True)
    async def stats_raid(self, ctx):
        pass

    @stats_raid.command(name="upload")
    async def stats_raid_upload(self, ctx, completion_date: str, *, raid_data):
        raid_data_raw = []
        for row in DictReader(raid_data.split("\n")):
            raid_data_raw.append(row)

        print(raid_data_raw)

    @stats.group(name="player", invoke_without_command=True)
    async def stats_player(self, ctx):
        pass

    @stats_player.command(name="upload")
    async def stats_player_upload(self, ctx, completion_date: str, *, player_stats):
        pass


def setup(bot):
    context: Context = bot.context

    stats_module = context.get_module(MODULE_NAME)
    bot.add_cog(stats_module)

