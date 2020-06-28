#TODO:
#use converter for queue/unqueue
#group some coroutines
#errorhandling in timer loop
#remove verbose printlns
#reorganize command groups

from discord.ext import tasks
from discord.ext import commands
from discord.utils import get
from datetime import timedelta
from itertools import zip_longest
import typing
import asyncio
import arrow
import discord
import logging

from notbot.services import RaidService, get_raid_service, get_queue_service, get_raid_info_service
from .converter.queue import Queue
from .util import Duration, get_hms, create_embed, num_to_hum
from .checks import raidconfig_exists, has_raid_management_permissions, has_raid_timer_permissions, is_mod, has_clan_role
from .util.config_keys import *
from .util.formatter import format_user_name
from notbot.db import get_queue_dao, get_raid_dao
from notbot.context import Context, Module

from ..exceptions import RaidActive, RaidOnCooldown, NoRaidActive, RaidAlreadyCleared, RaidUnspawned, UserAlreadyQueued, UserAttacking, RaidInfoNotFound, InvalidTitanCount, InvalidTitansForRaid, QueueNotOpen

logger = logging.getLogger(__name__)

"""
    raid configuration:
        queues
        channel
        spawn
        reset
        cooldown
        mentions

    queue configuration:
        name?
        delay
        size
        current
        queued_users
        active
"""

class QueueConfigKey(commands.Converter):
    async def convert(self, ctx, argument):
        if argument in QUEUE_CONFIG_KEYS:
            return argument
        
        raise commands.BadArgument(f"Config key must be one of {', '.join(QUEUE_CONFIG_KEYS)} ")

class RaidConfigKey(commands.Converter):
    async def convert(self, ctx, argument):
        if argument in RAID_CONFIG_KEYS:
            return argument

        raise commands.BadArgument(f"Config key must be one of {', '.join(RAID_CONFIG_KEYS)} ")

TIMER_TEXT = "Raid {} **{:02}**h **{:02}**m **{:02}**s."

RAID_CONFIG_KEYS = [RAID_ANNOUNCEMENTCHANNEL, RAID_MANAGEMENT_ROLES, RAID_TIMER_ROLES, RAID_CLAN_ROLES]
QUEUE_CONFIG_KEYS = [QUEUE_NAME, QUEUE_SIZE, QUEUE_PING_AFTER, QUEUE_AUTO_CLOSE]

MODULE_NAME = "raid_cog"

class RaidModule(commands.Cog, Module):
    def __init__(self, context: Context):
        self.bot = context.get_bot()
        self.queue_dao = get_queue_dao(context)
        self.raid_dao = get_raid_dao(context)
        self.raid_service = get_raid_service(context)
        self.queue_service = get_queue_service(context)
        self.raid_info_service = get_raid_info_service(context)

    def start(self):
        self.raid_timer.start()

    def get_name(self):
        return MODULE_NAME

    def cog_unload(self):
        self.raid_timer.cancel()

    @tasks.loop(seconds=3)
    async def raid_timer(self):
        now = arrow.utcnow()
        await asyncio.gather(
            *(self.handle_timer_for_guild(guild, now) for guild in self.bot.guilds),
            return_exceptions=True,
        )

    @raid_timer.before_loop
    async def wait_for_bot(self):
        logger.debug("waiting for the bot to be ready")
        await self.bot.wait_until_ready()

    async def handle_timer_for_guild(self, guild, now):
        await asyncio.gather(
            self.handle_raid_timer_for_guild(guild, now),
            self.handle_queues_for_guild(guild),
            return_exceptions=True,
        )

    async def handle_raid_timer_for_guild(self, guild, now):
        """
            TODO
                update raid timer message
                handle raid queue
                handle on demand queues
        """
        current_raid_config = await self.raid_dao.get_raid_configuration(guild.id)
        if not current_raid_config:
            raise asyncio.CancelledError

        announcement_channel = guild.get_channel(
            int(current_raid_config.get(RAID_ANNOUNCEMENTCHANNEL, 0))
        )

        spawn = current_raid_config.get(RAID_SPAWN, None)
        cooldown = current_raid_config.get(RAID_COOLDOWN, None)
        reset = int(current_raid_config.get(RAID_RESET, 0))
        messageid = current_raid_config.get(RAID_COUNTDOWNMESSAGE, None)
        reminded = int(current_raid_config.get(RAID_REMINDED, 0))
        permitted_roles = current_raid_config.get(RAID_MANAGEMENT_ROLES, "")
        unset_reminder = current_raid_config.get(RAID_UNSET_REMINDER, None)

        logger.debug("handle raid timer, guild: %s, spawn: %s, cd: %s, unset_reminder: %s", guild ,spawn, cooldown, unset_reminder)

        if announcement_channel is None:
            raise asyncio.CancelledError

        countdown_message = None
        
        if messageid is not None:
            try:
                countdown_message = await announcement_channel.fetch_message(
                    int(messageid)
                )
            except discord.NotFound:
                logger.exception("Could not find countdown message")
                countdown_message = await announcement_channel.send(
                    "Error while fetching timer message. Respawning timer..."
                )
                await self.raid_dao.set_countdown_message(guild.id, countdown_message.id)


        if countdown_message is None and (spawn or cooldown):
            countdown_message = await announcement_channel.send("Respawning timer ...")
            await self.raid_dao.set_countdown_message(guild.id, countdown_message.id)


        if cooldown is not None:
            logger.debug("%s - Updating remainding cooldown", guild)
            cdn = arrow.get(cooldown)
            if now > cdn:
                arr = now - cdn
                hms = get_hms(arr)
                await countdown_message.edit(
                    content=TIMER_TEXT.format("cooldown ends in", hms[0], hms[1], hms[2])
                )
                if not reminded:
                    roles = (guild.get_role(int(roleid)) for roleid in permitted_roles.split())

                    to_ping = []
                    for role in roles:
                        for member in role.members:
                            if member.mention not in to_ping:
                                to_ping.append(member.mention)

                    unset_reminder = now.shift(hours=3)
                    await self.raid_dao.set_unset_reminder(guild.id, unset_reminder.timestamp)

                    await self.raid_dao.set_cooldown_reminded(guild.id)
                    await announcement_channel.send("Set the raid timer!\n{}".format(', '.join(to_ping)))
                    await self.clear_current_raid(guild.id)

            else:
                arr = cdn - now
                hms = get_hms(arr)
                await countdown_message.edit(
                    content=TIMER_TEXT.format("cooldown ends in", hms[0], hms[1], hms[2])
                )

        elif spawn is not None:
            logger.debug("%s - Updating timer", guild)
            next_spawn = arrow.get(spawn).shift(hours=12 * reset)
            hms = get_hms(next_spawn - now)
            text = "raid_content"
            if not reset and next_spawn >= now:
                text = "starts in"
            elif now > next_spawn:
                text = f"reset #{reset} ends in"
                if reset > 0:
                    hms = get_hms(next_spawn.shift(hours=12 * reset) - now)
                else:
                    hms = get_hms(next_spawn.shift(hours=12) - now)
            else:
                text = f"reset #{reset} starts in"

            if now > next_spawn:
                print("activating default queue")
                is_default_queue_active = await self.queue_dao.get_queue_active(guild.id, "default")
                if not is_default_queue_active:
                    await self.queue_dao.set_queue_active(guild.id, "default")

                await asyncio.gather(
                    countdown_message.edit(
                        content="Raid {}".format("started" if not reset else f"reset #{reset} started")
                    ),
                    self.raid_dao.set_raid_reset(guild.id, reset + 1),
                    return_exceptions=True
                )
                
                countdown_message = await announcement_channel.send("Respawning timer ...")
                await self.raid_dao.set_countdown_message(guild.id, countdown_message.id)
            else:
                await countdown_message.edit(
                    content=TIMER_TEXT.format(text, hms[0], hms[1], hms[2])
                )
        elif unset_reminder is not None:
            logger.debug("%s - Handling unset reminder", guild)
            _unset_reminder = arrow.get(unset_reminder)
            if now > _unset_reminder:
                logger.debug("Reminding to set the raid timer")
                roles = (guild.get_role(int(roleid)) for roleid in permitted_roles.split())

                to_ping = []
                for role in roles:
                    for member in role.members:
                        if member.mention not in to_ping:
                            to_ping.append(member.mention)

                await self.raid_dao.del_key(guild.id, RAID_UNSET_REMINDER)
                await announcement_channel.send("Start raiding lazy folks.\nOr did you forget to set the timer again? :rolling_eyes:\n{}".format(', '.join(to_ping)))

    async def handle_queues_for_guild(self, guild):
        queues = await self.queue_dao.get_all_queues(guild.id)
        await asyncio.gather(
            *(self.handle_queue(guild, queue) for queue in queues),
            return_exceptions=True,
        )

    async def handle_queue(self, guild, queue):
        queue_config = await self.queue_dao.get_queue_configuration(guild.id, queue)
        current_users = queue_config.get(QUEUE_CURRENT_USERS, "").split()
        queue_size = int(queue_config.get(QUEUE_SIZE, 0))
        queue_in_progress = int(queue_config.get(QUEUE_PROGRESS, 0))
        queue_name = queue_config.get(QUEUE_NAME, None)
        queue_ping_after = int(queue_config.get(QUEUE_PING_AFTER, 0))
        queue_auto_close = int(queue_config.get(QUEUE_AUTO_CLOSE, 0))

        queue_paused = int(queue_config.get(QUEUE_PAUSED, 0))

        is_active = queue_config.get(QUEUE_ACTIVE, 0)
        if not is_active:
            return

        if queue_paused:
            logger.debug("Queue %s is paused", queue_name if queue_name else queue)
            return

        queued_users = await self.queue_dao.get_queued_users(guild.id, queue)

        raid_config = await self.raid_dao.get_raid_configuration(guild.id)
        
        announcement_channel = guild.get_channel(
            int(raid_config.get(RAID_ANNOUNCEMENTCHANNEL, 0))
        )
        
        if announcement_channel is None:
            print("Announcement channel is none")
            return;

        if not queue_in_progress:
            await announcement_channel.send(f"Queue **{queue_name if queue_name else queue}** started")
            await self.queue_dao.set_queue_progress(guild.id, queue)

        if queue_size == 0:
            await self.queue_dao.reset_queue(guild.id, queue)
            await announcement_channel.send("Queue is over")
            return

        if current_users:
            # users are currently attacking
            # print("Users are currently attacking")
            return

        if not queued_users and not current_users:
            # Queue is over
            await self.queue_dao.reset_queue(guild.id, queue)

            if queue_auto_close:
                await self.queue_service.close_queue(guild.id, queue)

            ping = ""
            if queue_ping_after:
                role = guild.get_role(queue_ping_after)
                ping = role.mention

            await announcement_channel.send(f"Queue **{queue_name if queue_name else queue}** is over {ping}")

        if queued_users:
            next_users = queued_users[0:queue_size]
            queued_members = [guild.get_member(int(memberid)) for memberid in next_users]

            await asyncio.gather(
                *(self.queue_dao.remove_user_from_queued_users(
                    guild.id, queue, next_user) for next_user in next_users
                ),
                self.queue_dao.set_current_users(
                    guild.id, queue, " ".join([str(m.id) for m in queued_members])
                ),
                return_exceptions=True
            )

            await announcement_channel.send(
                "It's {}'s turn to attack the raid!".format(
                    ", ".join([f"{m.mention}" for m in queued_members])
                )
            )

    @commands.group(name="raid", aliases=["r"], invoke_without_command=True)
    async def raid(self, ctx):
        pass

    @raid.command(
        name="damageneeded",
        description="""
        Calculates the total damage ( Body + Armor ) needed to clear the given raid.
        If supplied, also calculates based on the member the least needed average per member to clear the raid( for cycles 1-6 )

        Example usage: 
            raid damageneeded 3 3 Sterl,Terro,Lojak,Lojak
            raid damageneeded 3 3 Sterl,Terro,Lojak,Lojak 50
        """,
        aliases=["dmg"]
    )
    async def raid_damageneeded(
        self,
        ctx,
        raid_tier: int,
        raid_level: int,
        titans: str,
        members: int = 0
    ):
        damage_needed = 0

        try:
            damage_needed = self.raid_info_service.get_damage_needed_to_clear(raid_tier, raid_level, titans.split(","))
        except (RaidInfoNotFound, InvalidTitanCount, InvalidTitansForRaid) as err:
            raise commands.BadArgument(str(err))

        res = []
        res.append(f"Total damage needed to clear {raid_tier}-{raid_level} ({', '.join(titans.split(','))}): **{num_to_hum(damage_needed)}**")

        if members:
            raid_info = self.raid_info_service.get_raid_info(raid_tier, raid_level)
            if raid_info:
                res.append(f"Required average damage with **{members}** members to clear it in")
                for cycle in range(1, 7):
                    total_attacks = members * cycle * raid_info.attacks_per_reset
                    avg_needed = damage_needed / total_attacks
                    res.append(f"  - {cycle} {'cycles' if cycle > 1 else 'cycle'}: **{num_to_hum(avg_needed)}**")

        await ctx.send("\n".join(res))

    @commands.check(is_mod)
    @raid.command(name="setup", description="initial raid config setup")
    async def raid_initial_setup(self, ctx):
        rconfig_exists = await self.raid_dao.raid_config_exists(ctx.guild.id)
        if rconfig_exists:
            raise commands.BadArgument("Raids have been setup already")

        
        await self.raid_dao.add_queue(ctx.guild.id, "default")
        
        await self.queue_dao.set_queue_name(ctx.guild.id, "default", "Reset Queue")
        await self.queue_dao.set_queue_size(ctx.guild.id, "default", 1)

        await self.raid_dao.set_raid_init(ctx.guild.id)

        await ctx.send(f"raid setup done :)")

    @commands.check(raidconfig_exists)
    @commands.check(has_raid_timer_permissions)
    @raid.command(name="in")
    async def raid_in(self, ctx, time: typing.Union[Duration] = None):
        now = arrow.utcnow()
        if not time:
            time = now.shift(hours=24)

        announcement_channel_id = int(await self.raid_service.get_announcement_channel_id(ctx.guild.id))
        announcement_channel = ctx.guild.get_channel(announcement_channel_id)

        if not announcement_channel:
            raise commands.BadArgument("No announcement channel configured")

        try:
            await self.raid_service.start_raid(ctx.guild.id, time)
        except RaidActive:
            raise commands.BadArgument(f"Raid is currently active. Use **{ctx.prefix}raid clear** or **{ctx.prefix}raid cancel** first")
        except RaidOnCooldown:
            raise commands.BadArgument(f"Raid is currently on cooldown. Wait or use **{ctx.prefix}raid cancel** first")

        await ctx.send(f":white_check_mark: Set raid timer")

    @commands.check(raidconfig_exists)
    @commands.check(has_clan_role)
    @raid.command(name="when")
    async def raid_when(self, ctx):
        now = arrow.utcnow()
        raid_config = await self.raid_service.get_raid_configuration(ctx.guild.id)
        spawn = raid_config.get(RAID_SPAWN, None)
        reset = int(raid_config.get(RAID_RESET, 0))
        cooldown = raid_config.get(RAID_COOLDOWN, None)

        timer = None
        embed_text = ""
        hms = None

        if cooldown:
            cdn = arrow.get(cooldown)
            if cdn > now:
                timer = cdn
                embed_text = "cooldown ends in"
                hms = get_hms(cdn - now)

        elif spawn:
            spwn = arrow.get(spawn).shift(hours=12 * reset)
            hms = get_hms(spwn - now)
            timer = spwn
            if reset:
                embed_text = f"reset #{reset} starts in"
            else:
                embed_text = "starts in"
        else:
            raise commands.BadArgument("Theres no raid currently active")

        embed = create_embed(self.bot)

        if timer is not None:
            embed.timestamp = timer.datetime

        embed.description = TIMER_TEXT.format(embed_text, hms[0], hms[1], hms[2])
        embed.set_footer(text=f"{embed_text[:-3]}", icon_url=ctx.guild.me.avatar_url)
        await ctx.send(embed=embed)

    @commands.check(raidconfig_exists)
    @commands.check(has_raid_timer_permissions)
    @raid.command(name="clear")
    async def raid_clear(self, ctx, duration: typing.Union[Duration] = None):
        now = arrow.utcnow()
        logger.debug("raid_clear now: %s", now)
        logger.debug("raid_clear + 59 59 %s", now.shift(minutes=59, seconds=59))
        if duration is None:
            duration = now.shift(minutes=59, seconds=59)
        
        try:
            time_needed_to_clear = await self.raid_service.clear_raid(ctx.guild.id, duration)
        except ValueError:
            raise commands.BadArgument("Cooldown end must be 60m after raid.")
        except NoRaidActive:
            raise commands.BadArgument("No raid to clear")
        except RaidAlreadyCleared:
            raise commands.BadArgument("Raid has been cleared already")
        except RaidUnspawned:
            raise commands.BadArgument(
                f"Can't clear unspawned raid. Use **{ctx.prefix}raid cancel** to cancel it."
            )
        
        h, m, s = get_hms(time_needed_to_clear)
        cleared = f"**{h}**h **{m}**m **{s}**s"

        await ctx.send(
            "Raid **cleared** in {}.".format(cleared)
        )

        await self.raid_dao.del_key(ctx.guild.id, RAID_COUNTDOWNMESSAGE)


    @commands.check(raidconfig_exists)
    @raid.command(name="cancel")
    @commands.check(has_raid_timer_permissions)
    async def raid_cancel(self, ctx):
        try:
            await self.raid_service.cancel_raid(ctx.guild.id)
        except NoRaidActive:
            raise commands.BadArgument("No raid to cancel")

        await ctx.send("Cancelled the current raid.")

    @raid.group(name="queue", aliases=["q"], invoke_without_command=True)
    @commands.check(has_clan_role)
    @commands.check(raidconfig_exists)
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def raid_queue(self, ctx, queue: typing.Union[Queue] = "default"):
        try:
            await self.queue_service.queue_up(ctx.author.id, ctx.guild.id, queue)
            await ctx.send(f":white_check_mark: Ok **{format_user_name(ctx.author)}**, i've added you to the queue")
        except UserAlreadyQueued as err:
            raise commands.BadArgument(f"Sorry **{format_user_name(ctx.author)}**, you are already **#{err.queued_index + 1}** in the queue")
        except UserAttacking:
            raise commands.BadArgument(f"**{format_user_name(ctx.author)}**, you are currently attacking, use **{ctx.prefix}raid done {queue}** to finish your ")
        except QueueNotOpen:
            raise commands.BadArgument(f"Queue **{queue}** is currently closed")

    @raid_queue.command(name="show")
    @commands.check(raidconfig_exists)
    @commands.check(has_clan_role)
    async def raid_queue_show(self, ctx, queue: typing.Union[Queue] = "default"):
        queued_users, queueconfig = await asyncio.gather(
            self.queue_dao.get_queued_users(ctx.guild.id, queue),
            self.queue_dao.get_queue_configuration(ctx.guild.id, queue),
            return_exceptions=True
        )

        queue_paused = int(queueconfig.get(QUEUE_PAUSED, 0))
        queue_size = int(queueconfig.get(QUEUE_SIZE, 1))
        current_attacker_ids = queueconfig.get(QUEUE_CURRENT_USERS, "").split()
        clusters = zip_longest(*[iter(queued_users)] * queue_size, fillvalue=None)
        queue_open = int(queueconfig.get(QUEUE_OPEN, 0))

        result = []
        for c in clusters:
            temp = str(len(result) + 1)
            r = []
            for u in c:
                if u is not None:
                    ux = self.bot.get_user(int(u))
                    r.append(f"{ux.mention}")
            result.append(temp + ". " + ", ".join(r))
            
        queue_name = queueconfig.get(QUEUE_NAME, None)

        current_attackers = []
        for current_attacker_id in current_attacker_ids:
            user = self.bot.get_user(int(current_attacker_id))
            current_attackers.append(f"{user.mention}")

        current_attackers_formatted = ", ".join(current_attackers)
        
        if result or current_attackers_formatted:
            embed = create_embed(ctx.bot)
            embed.title = "**Queue** for **{}**{}:".format(
                queue_name if queue_name else queue,
                "" if not queue_paused else " ( paused )"
            )

            if current_attackers_formatted:
                embed.add_field(name="Current attackers", value=current_attackers_formatted, inline=False)
                pass
            if result:
                embed.add_field(name="Queued members", value="\n".join(result), inline=False)
                pass

            embed.set_footer(
                text="Use {}raid unqueue {} to unqueue".format(ctx.prefix, queue_name), icon_url=self.bot.user.avatar_url
            )

            embed.colour = 0x9e5db7

            await ctx.send(embed=embed)
        else:
            await ctx.send(f"Queue **{queue_name if queue_name else queue}** is currently empty{' and **closed**' if not queue_open else ''}", )

    @raid_queue.command(name="skip")
    @commands.check(raidconfig_exists)
    @commands.check(has_raid_timer_permissions)
    async def raid_queue_skip(self, ctx, queue: typing.Union[Queue] = "default"):
        await self.queue_dao.delete_current_users(ctx.guild.id, queue)
        await ctx.send(f":white_check_mark: **{queue}**: Current attackers cleared")

    @raid_queue.command(name="clear")
    @commands.check(raidconfig_exists)
    @commands.check(has_raid_timer_permissions)
    async def raid_queue_clear(self, ctx, queue: typing.Union[Queue] = "default"):
        await self.queue_dao.remove_current_and_queued_users_from_queue(ctx.guild.id, queue)
        await ctx.send(f":white_check_mark: Queue **{queue}** has been cleared!")

    @raid.command(name="unqueue", aliases=["uq"])
    @commands.check(has_clan_role)
    @commands.check(raidconfig_exists)
    async def raid_unqueue(self, ctx, queue: typing.Union[Queue] = "default"):
        queueconfig = await self.queue_dao.get_queue_configuration(ctx.guild.id, queue)
        queued_users = await self.queue_dao.get_queued_users(ctx.guild.id, queue)
        current_users = queueconfig.get(QUEUE_CURRENT_USERS, "").split()

        if str(ctx.author.id) in current_users:
            raise commands.BadArgument(f"**{format_user_name(ctx.author)}**, its currently your turn. Use **{ctx.prefix}raid done {queue}**")
        
        if not str(ctx.author.id) in queued_users:
            raise commands.BadArgument(f"**{format_user_name(ctx.author)}**, you are currently not queued")
        
        await self.queue_dao.remove_user_from_queued_users(ctx.guild.id, queue, ctx.author.id)
        await ctx.send(f":white_check_mark: Ok **{format_user_name(ctx.author)}**, i removed you from queue")

    @raid.command(name="done", aliases=["d"])
    @commands.check(has_clan_role)
    @commands.check(raidconfig_exists)
    async def raid_done(self, ctx, queue: typing.Union[Queue] = "default"):
        queue_config = await self.queue_dao.get_queue_configuration(ctx.guild.id, queue)
        queued_users = await self.queue_dao.get_queued_users(ctx.guild.id, queue)

        current_users = queue_config.get(QUEUE_CURRENT_USERS, "").split()

        if not str(ctx.author.id) in current_users:
            if not str(ctx.author.id) in queued_users:
                raise commands.BadArgument(f"**{format_user_name(ctx.author)}**, it's not your turn and you're not queued.")
            else:
                raise commands.BadArgument(f"**{format_user_name(ctx.author)}**, not your go. Do **{ctx.prefix}raid unqueue {queue}** instead.")
        else:
            current_users = " ".join(current_users)
            current_users = current_users.replace(str(ctx.author.id), "")
            await self.queue_dao.set_current_users(ctx.guild.id, queue, current_users.strip())
            await ctx.send(f"**{format_user_name(ctx.author)}** has finished their turn.")
            return

    @commands.group(name="raidconfig", invoke_without_command=True)
    async def raidconfig(self, ctx):
        pass

    @raidconfig.command(name="show")
    @commands.check(has_clan_role)
    @commands.check(raidconfig_exists)
    async def raidconfig_show(self, ctx):
        raid_configuration = await self.raid_dao.get_raid_configuration(ctx.guild.id)
        tmp = []
        for config_key in RAID_CONFIG_KEYS:
            config_value = raid_configuration.get(config_key, None)
            tmp.append(f"{config_key}: {self.format_config_value(ctx, config_key, config_value)}")
            
        await ctx.send("**Raid configuration:**\n\n{}".format('\n'.join(tmp)))

    @raidconfig.command(name="set")
    @commands.check(raidconfig_exists)
    @commands.check(has_raid_management_permissions)
    async def raidconfig_set(self, ctx, config_key: typing.Union[RaidConfigKey], *value):
        if not value:
            raise commands.BadArgument("value is a required argument that is missing")

        val = None
        formatted_value = None

        if config_key in [RAID_ANNOUNCEMENTCHANNEL]:
            if config_key == RAID_ANNOUNCEMENTCHANNEL:
                channel = await commands.TextChannelConverter().convert(ctx, value[0])
                val = channel.id
                formatted_value = f"**{channel.mention}**"
        
        elif config_key in [RAID_MANAGEMENT_ROLES, RAID_TIMER_ROLES, RAID_CLAN_ROLES]:
            roles = []
            for v in value:
                role = await commands.RoleConverter().convert(ctx, v)
                roles.append(role)
            val = " ".join([
                "{}".format(role.id)
                for role in roles
            ])
            formatted_value = " ".join([
                "@**{}**".format(role) for role in roles
            ])

        await self.raid_dao.set_key(ctx.guild.id, config_key, val)
        await ctx.send(f":white_check_mark: Successfully set **{config_key}** to {formatted_value if formatted_value else val}")
        
    @commands.group(name="queueconfig", invoke_without_command=True)
    async def queueconfig(self, ctx):
        pass

#         sets the new value for the given key for the supplied queue
    @queueconfig.command(name="show")
    @commands.check(has_clan_role)
    @commands.check(raidconfig_exists)
    async def queueconfig_show(self, ctx, queue: typing.Union[Queue] = None):
        if queue:
            queues = [queue]
        else:
            queues = await self.queue_dao.get_all_queues(ctx.guild.id)
        
        queue_configurations = await asyncio.gather(
            *(self.queue_dao.get_queue_configuration(ctx.guild.id, q) for q in queues),
            return_exceptions=True
        )

        tmp = []
        for i, queue_configuration in enumerate(queue_configurations):
            tmp.append(f"Config values for queue **{queues[i]}** ({queue_configuration.get(QUEUE_NAME)}):")
            for config_key in QUEUE_CONFIG_KEYS:
                config_value = queue_configuration.get(config_key, None)
                tmp.append(f"{config_key}: {self.format_config_value(ctx, config_key, config_value)}")
            
            tmp.append("")

        await ctx.send("**Queue configuration:**\n\n{}".format('\n'.join(tmp)))

    @queueconfig.command(name="set")
    @commands.check(raidconfig_exists)
    @commands.check(has_raid_management_permissions)
    async def queueconfig_set(self, ctx, queue: typing.Optional[Queue], config_key: typing.Union[QueueConfigKey], config_value):
        formatted_value = None
        if not queue:
            queue = "default"

        if config_key in [QUEUE_SIZE, QUEUE_AUTO_CLOSE]:
            try:
                value = int(config_value)
                formatted_value = f"**{value}**"
            except ValueError:
                raise commands.BadArgument(f"Cannot set **{config_key}** to **{config_value}**. Integer required")
        elif config_key in [QUEUE_PING_AFTER]:
            role = await commands.RoleConverter().convert(ctx, config_value)
            value = role.id
            formatted_value = f"@**{role.name}**"
        else:
            value = config_value
            formatted_value = f"**{value}**"

        if config_key in [QUEUE_AUTO_CLOSE]:
            if value < 0 or value > 1:
                raise commands.BadArgument(f"**{config_key}** has to be 0 or 1")
        
        if config_key in [QUEUE_SIZE]:
            if not value > 0:
                raise commands.BadArgument(f"**{config_key}** has to be greater than 0")

        await self.queue_dao.set_key(ctx.guild.id, queue, config_key, value)
        await ctx.send(f":white_check_mark: Successfully set **{config_key}** to {formatted_value if formatted_value else value} for queue **{queue}**")  

    @queueconfig.command(name="create")
    @commands.check(raidconfig_exists)
    @commands.check(has_raid_management_permissions)
    async def queueconfig_create(self, ctx, queue_name, queue_size: int):
        queues = await self.queue_dao.get_all_queues(ctx.guild.id)

        if queue_name in queues:
            raise commands.BadArgument(f"**{queue_name}** already exits!")

        await self.raid_dao.add_queue(ctx.guild.id, queue_name)
        await self.queue_dao.set_queue_size(ctx.guild.id, queue_name, queue_size)

        await ctx.send(f":white_check_mark: Queue **{queue_name}** has been created!")

    @queueconfig.command(name="delete")
    @commands.check(raidconfig_exists)
    @commands.check(has_raid_management_permissions)
    async def queueconfig_delete(self, ctx, queue_name: typing.Union[Queue]):
        if queue_name == "default":
            raise commands.BadArgument("Cannot delete default queue")

        await self.queue_dao.delete_queue_configuration(ctx.guild.id, queue_name)
        await self.raid_dao.remove_queue(ctx.guild.id, queue_name)

        await ctx.send(f":white_check_mark: Queue **{queue_name}** has been deleted!")

    @queueconfig.command(name="start")
    @commands.check(has_raid_timer_permissions)
    async def queueconfig_start(self, ctx, queue_name: typing.Union[Queue]):
        if queue_name == "default":
            raise commands.BadArgument("Cannot manually start the default queue")

        await self.queue_dao.set_queue_active(ctx.guild.id, queue_name)
        await ctx.send(f":white_check_mark: Started queue {queue_name}") 

    @queueconfig.command(name="pause")
    @commands.check(has_raid_timer_permissions)
    async def queueconfig_pause(self, ctx, queue_name: typing.Optional[Queue] = "default"):
        await self.queue_service.pause_queue(ctx.guild.id, queue_name)
        await ctx.send(f":white_check_mark: Paused queue {queue_name}")

    @queueconfig.command(name="resume")
    @commands.check(has_raid_timer_permissions)
    async def queueconfig_resume(self, ctx, queue_name: typing.Union[Queue] = "default"):
        await self.queue_service.resume_queue(ctx.guild.id, queue_name)
        await ctx.send(f":white_check_mark: Resumed queue {queue_name}")

    @queueconfig.command(name="close")
    @commands.check(has_raid_timer_permissions)
    async def queueconfig_close(self, ctx, queue_name: typing.Union[Queue] = "default"):
        await self.queue_service.close_queue(ctx.guild.id, queue_name)
        await self.queue_service.clear_queued_users(ctx.guild.id, queue_name)
        await ctx.send(f":white_check_mark: Closed queue {queue_name}")

    @queueconfig.command(name="open")
    @commands.check(has_raid_timer_permissions)
    async def queueconfig_open(self, ctx, queue_name: typing.Union[Queue] = "default"):
        await self.queue_service.open_queue(ctx.guild.id, queue_name)
        await ctx.send(f":white_check_mark: Opened queue {queue_name}") 

    async def check_if_queue_exists_or_break(self, guild_id, queue):
        queues = await self.queue_dao.get_all_queues(guild_id)
        if not queue in queues:
            raise commands.BadArgument(f"Queue **{queue}** does not exist. Available queues: {', '.join(queues)}")

    async def clear_current_raid(self, guild_id):
        for k in [RAID_COUNTDOWNMESSAGE, RAID_SPAWN, RAID_RESET, RAID_REMINDED, RAID_COOLDOWN]:
            await self.raid_dao.del_key(guild_id, k)
        
        await self.queue_dao.delete_queued_users(guild_id, "default")

        for k in [QUEUE_ACTIVE, QUEUE_PROGRESS, QUEUE_CURRENT_USERS]:
            await self.queue_dao.del_key(guild_id, "default", k)

    def format_config_value(self, ctx, key, value):
        if not value:
            return value

        if "role" in key:
            role_ids = value.split()
            
            formatted_value = "{}".format(
                ", ".join(
                    f"@**{ctx.guild.get_role(int(role))}**" for role in role_ids
                )
            )
            # role = ctx.guild.get_role(int(value))
            # formatted_value = f"@**{role}**"
            return formatted_value
        elif "channel" in key:
            channel = ctx.guild.get_channel(int(value))
            formatted_value = channel.mention
            return formatted_value
        else:
            return value

def setup(bot):
    context: Context = bot.context

    raid_module = context.get_module(MODULE_NAME)
    bot.add_cog(raid_module)
