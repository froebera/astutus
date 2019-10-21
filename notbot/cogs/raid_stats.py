import asyncio
import math
from typing import List
from csv import DictReader
from logging import getLogger
from discord.ext import commands

from notbot.context import Context, Module
from notbot.services import get_raid_stat_service
from notbot.models import RaidPlayerAttack, RaidAttacks
import notbot.cogs.util.formatter as formatter
from .checks import has_raid_management_permissions
from .util import create_embed, num_to_hum, DATETIME_FORMAT, get_hms
from .converter import ArrowDateTimeConverter

MODULE_NAME = "stats_module"

logger = getLogger(__name__)


class RaidStatsModule(commands.Cog, Module):
    def __init__(self, context: Context):
        self.bot = context.get_bot()
        self.raid_stat_service = get_raid_stat_service(context)

    def get_name(self):
        return MODULE_NAME

    @commands.group(name="raidstats", aliases=["rs"], invoke_without_command=True)
    async def stats(self, ctx, raid_id: int):
        # TODO: check if raid is complete
        has_permission_and_exists, attacks_exist = await asyncio.gather(
            self.raid_stat_service.has_raid_permission_and_raid_exists(
                ctx.guild.id, raid_id
            ),
            self.raid_stat_service.check_if_attacks_exist(ctx.guild.id, raid_id),
        )

        if not has_permission_and_exists:
            raise commands.BadArgument("Raid does not exist for your guild")

        if not attacks_exist:
            raise commands.BadArgument("Please upload player attacks")

        awaitables = []  # list to collect all messages
        raid_stats = await self.raid_stat_service.calculate_raid_stats(raid_id)
        raid_data = await self.raid_stat_service.load_raid_data_for_stats(
            ctx.guild.id, raid_id
        )

        duration_hms = get_hms(raid_stats.cleared_at - raid_stats.started_at)
        d_h, d_m, d_s = duration_hms[0], duration_hms[1], duration_hms[2]

        embed = create_embed(self.bot)

        embed.add_field(
            name="**Average Player Damage**",
            value="\n".join(
                self._create_min_max_avg_texts(
                    raid_stats.min_avg, raid_stats.max_avg, raid_stats.total_avg
                )
            ),
        )

        embed.add_field(
            name="**Player Damage**",
            value="\n".join(
                self._create_min_max_avg_texts(
                    raid_stats.min_dmg, raid_stats.max_dmg, raid_stats.avg_dmg
                )
            ),
        )

        embed.add_field(
            name="**Attacks**",
            value="\n".join(
                self._create_min_max_avg_texts(raid_stats.min_hits, raid_stats.max_hits)
            ),
        )

        embed.add_field(
            name="**Total Damage Dealt**",
            value="{}".format(num_to_hum(raid_stats.total_dmg)),
        )

        embed.add_field(
            name="**Cycles**", value="{}".format(math.ceil(raid_stats.max_hits / 4))
        )

        embed.add_field(name="**Attackers**", value="{}".format(raid_stats.attackers))

        embed.add_field(
            name="**Started**", value=raid_stats.started_at.format(DATETIME_FORMAT)
        )

        embed.add_field(
            name="**Cleared**", value=raid_stats.cleared_at.format(DATETIME_FORMAT)
        )

        embed.add_field(name="**Duration**", value=f"**{d_h}**h **{d_m}**m **{d_s}**s")

        awaitables.append(ctx.send(embed=embed))

        raid_player_hits = []
        string_length = 0
        DISCORD_MAX_CONTENT_LENGHT = 2000 - 50  # some buffer

        latest_raid_data = raid_data[0]
        if len(raid_data) == 1:
            reference_raid_data = raid_data[1]
        else:
            reference_raid_data = None

        for idx, player_attack in enumerate(latest_raid_data.raid_player_attacks):
            if reference_raid_data:
                reference_player_attack = next(
                    (
                        raid_player_attack
                        for raid_player_attack in reference_raid_data.raid_player_attacks
                        if raid_player_attack.player_id == player_attack.player_id
                    ),
                    None,
                )
            else:
                reference_player_attack = None

            stat_string = "{:2}. {:<20}: {:<7}, {:2}, {:<6} ({})".format(
                idx + 1,
                player_attack.player_name,
                num_to_hum(player_attack.total_dmg),
                player_attack.total_hits,
                num_to_hum(player_attack.total_dmg / player_attack.total_hits),
                num_to_hum((player_attack.total_dmg / player_attack.total_hits) - (reference_player_attack.total_dmg / reference_player_attack.total_hits))
                if reference_player_attack
                else "",
            )
          
            if string_length + len(stat_string) >= DISCORD_MAX_CONTENT_LENGHT:
                awaitables.append(
                    ctx.send("```{}```".format("\n".join(raid_player_hits)))
                )
                string_length = 0
                raid_player_hits.clear()

            string_length += len(stat_string)
            raid_player_hits.append(stat_string)

        awaitables.append(ctx.send("```{}```".format("\n".join(raid_player_hits))))
        await asyncio.gather(*(awaitables))

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

    @stats_raid.command(name="create")
    @commands.check(has_raid_management_permissions)
    async def stats_raid_create(
        self,
        ctx,
        started_at: ArrowDateTimeConverter,
        cleared_at: ArrowDateTimeConverter,
    ):
        raid_id = await self.raid_stat_service.create_raid_stat_entry(
            ctx.guild.id, started_at, cleared_at
        )

        await ctx.send(
            formatter.success_message(f"Created new raid entry with id {raid_id}")
        )

    @stats_raid.command(name="delete")
    @commands.check(has_raid_management_permissions)
    async def stats_raid_delete(self, ctx, raid_id: int):
        has_permissions_and_exists = await self.raid_stat_service.has_raid_permission_and_raid_exists(
            ctx.guild.id, raid_id
        )

        if not has_permissions_and_exists:
            raise commands.BadArgument("Raid does not exist for your guild")

        await self.raid_stat_service.delete_raid_entry(raid_id)

        await ctx.send(
            formatter.success_message(f"Deleted raid entry with id {raid_id}")
        )

    @stats_raid.command(name="delete_attacks")
    @commands.check(has_raid_management_permissions)
    async def stats_raid_delete_attacks(self, ctx, raid_id: int):
        has_permissions_and_exists = await self.raid_stat_service.has_raid_permission_and_raid_exists(
            ctx.guild.id, raid_id
        )

        if not has_permissions_and_exists:
            raise commands.BadArgument("Raid does not exist for your guild")

        await self.raid_stat_service.delete_attacks_for_raid(raid_id)

        await ctx.send(
            formatter.success_message(f"Deleted raid attacks for raid {raid_id}")
        )

    @stats.command(name="list")
    async def stats_list(self, ctx):
        """
        Lists last couple raids ( 10 )
        Lists uncompleted raids ( raid stats uploaded yet, up to 10 )
        """

        uncompleted_raids, completed_raids = await self.raid_stat_service.get_raid_list(
            ctx.guild.id
        )

        uncompleted_raids_with_attack_check = []
        completed_raids_with_attack_check = []

        aw_attacks_exist_uncompleted = asyncio.gather(
            *(
                self.raid_stat_service.check_if_attacks_exist(ctx.guild.id, raid.id)
                for raid in uncompleted_raids
            )
        )

        aw_attacks_exist_completed = asyncio.gather(
            *(
                self.raid_stat_service.check_if_attacks_exist(ctx.guild.id, raid.id)
                for raid in completed_raids
            )
        )

        attacks_exist_uncompleted = await aw_attacks_exist_uncompleted
        for idx, raid in enumerate(uncompleted_raids):
            attack_exists = attacks_exist_uncompleted[idx]
            uncompleted_raids_with_attack_check.append((attack_exists, raid))

        attacks_exist_completed = await aw_attacks_exist_completed
        for idx, raid in enumerate(completed_raids):
            attack_exists = attacks_exist_completed[idx]
            completed_raids_with_attack_check.append((attack_exists, raid))

        msg = "\n\n".join(
            [
                "{}\n{}".format(
                    "**{}**\n(Raid ID, started_at, cleared_at, attacks uploaded)".format(
                        raid_list[0]
                    ),
                    "\n".join(
                        [
                            "**{}**, {}, {}, {}".format(
                                r[1].id,
                                r[1].started_at.format(DATETIME_FORMAT)
                                if r[1].started_at
                                else "-",
                                r[1].cleared_at.format(DATETIME_FORMAT)
                                if r[1].cleared_at
                                else "-",
                                "Y" if r[0] else "N",
                            )
                            # r = tuple from int ( attacks uploaded ) and the raid model
                            for r in raid_list[1]
                        ]
                    ),
                )
                for idx, raid_list in enumerate(
                    [
                        ("Uncompleted raids", uncompleted_raids_with_attack_check),
                        ("Completed raids", completed_raids_with_attack_check),
                    ]
                )
            ]
        )

        await ctx.send(msg)

    def _create_min_max_avg_texts(self, min_val, max_val, avg_val=None):
        res = [
            ":arrow_double_up:: {}".format(num_to_hum(max_val)),
            ":arrow_double_down:: {}".format(num_to_hum(min_val)),
        ]

        if avg_val:
            res.append(":heavy_minus_sign:: {}".format(num_to_hum(avg_val)))
        return res


def setup(bot):
    context: Context = bot.context

    stats_module = context.get_module(MODULE_NAME)
    bot.add_cog(stats_module)

