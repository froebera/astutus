import asyncio
from discord.ext import commands
from csv import DictReader
from ..context import Context, Module
from notbot.services import get_raid_stat_service
from typing import List
from notbot.models import RaidPlayerAttack
import notbot.cogs.util.formatter as formatter
from logging import getLogger
from .checks import has_raid_management_permissions

MODULE_NAME = "stats_module"

logger = getLogger(__name__)


class RaidStatsModule(commands.Cog, Module):
    def __init__(self, context: Context):
        self.bot = context.get_bot()
        self.raid_stat_service = get_raid_stat_service(context)

    def get_name(self):
        return MODULE_NAME

    @commands.group(name="stats", invoke_without_command=True)
    async def stats(self, ctx):
        pass

    @stats.group(name="raid", invoke_without_command=True)
    async def stats_raid(self, ctx):
        pass

    @stats_raid.command(name="upload")
    @commands.check(has_raid_management_permissions)
    async def stats_raid_upload(self, ctx, raid_id: int, *, raid_data):
        has_permission_and_exists, attacks_exist = await asyncio.gather(
            self.raid_stat_service.has_raid_permission_and_raid_exists(
                ctx.guild.id, raid_id
            ),
            self.raid_stat_service.check_if_attacks_exist(ctx.guild.id, raid_id),
        )

        logger.debug("stats_raid_upload: Uploading raid data for raid_id %s", raid_id)
        logger.debug(
            "stats_raid_upload: Has permission and raid exists: %s, Stats already uploaded for this raid: %s",
            has_permission_and_exists,
            attacks_exist,
        )

        if not has_permission_and_exists:
            raise commands.BadArgument("Raid does not exist for your guild")

        if attacks_exist:
            raise commands.BadArgument(
                "Attacks have already been uploaded for this raid. Delete them if you want to reupload"
            )

        raid_attacks: List[RaidPlayerAttack] = []
        for row in DictReader(raid_data.split("\n")):
            rpa = RaidPlayerAttack(
                raid_id, row["ID"], row["Name"], int(row["Attacks"]), int(row["Damage"])
            )
            raid_attacks.append(rpa)

        await self.raid_stat_service.save_raid_player_attacks(raid_attacks)
        await ctx.send(formatter.success_message("Saved raid conclusion"))

    # @commands.Cog.listener()
    # async def on_message(self, message):
    #     print("New message")
    #     print(message.channel)

    # @stats.group(name="player", invoke_without_command=True)
    # async def stats_player(self, ctx):
    #     pass

    # @stats_player.command(name="upload")
    # async def stats_player_upload(self, ctx, completion_date: str, *, player_stats):
    #     pass

    # @stats.command(name="upload")

    @stats.command(name="list")
    async def stats_list(self, ctx):
        """
        Lists last couple raids ( 10 )
        Lists uncompleted raids ( raid stats uploaded yet, up to 10 )
        """

        uncompleted_raids, completed_raids = await self.raid_stat_service.get_raid_list(
            ctx.guild.id
        )

        msg = "\n\n".join(
            [
                "{}\n{}".format(
                    "**{}**\n(Raid ID, started_at, cleared_at)".format(raid_list[0]),
                    "\n".join(
                        [
                            "**{}**, {}, {}".format(
                                r.id,
                                r.started_at.format("YYYY-MM-DD HH:mm:ss")
                                if r.started_at
                                else "-",
                                r.cleared_at.format("YYYY-MM-DD HH:mm:ss")
                                if r.cleared_at
                                else "-",
                            )
                            for r in raid_list[1]
                        ]
                    ),
                )
                for idx, raid_list in enumerate(
                    [
                        ("Uncompleted raids", uncompleted_raids),
                        ("Completed raids", completed_raids),
                    ]
                )
            ]
        )

        await ctx.send(msg)


def setup(bot):
    context: Context = bot.context

    stats_module = context.get_module(MODULE_NAME)
    bot.add_cog(stats_module)

