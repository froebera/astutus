#TODO:
#use converter for queue/unqueue
#group some coroutines
#errorhandling in timer loop
#remove verbose printlns
#reorganize command groups

#TODO CHECK IF QUEUE STILL WORKS

from discord.ext import tasks
from discord.ext import commands
from discord.utils import get
from datetime import timedelta
from itertools import zip_longest
import typing
import asyncio
import arrow
import discord

from .converter.queue import Queue
from .util import Duration, get_hms
from .checks import raidconfig_exists, has_raid_management_permissions, has_raid_timer_permissions, is_mod
from .util.config_keys import *
from db import get_queue_dao, get_raid_dao

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

RAID_CONFIG_KEYS = [RAID_ANNOUNCEMENTCHANNEL, RAID_MANAGEMENT_ROLES, RAID_TIMER_ROLES]
QUEUE_CONFIG_KEYS = [QUEUE_NAME, QUEUE_SIZE, QUEUE_PING_AFTER]

class RaidModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.raid_timer.start()
        self.queue_dao = get_queue_dao(self.bot.context)
        self.raid_dao = get_raid_dao(self.bot.context)

    def cog_unload(self):
        self.raid_timer.cancel()

    @tasks.loop(seconds=3)
    async def raid_timer(self):
        now = arrow.utcnow()
        await asyncio.gather(
            *(self.handle_timer_for_guild(guild, now) for guild in self.bot.guilds),
            return_exceptions=True,
        )

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
        permitted_roles = current_raid_config.get(RAID_MANAGEMENT_ROLES, None)

        if announcement_channel is None:
            raise asyncio.CancelledError

        countdown_message = None

        if messageid is not None:
            try:
                countdown_message = await announcement_channel.fetch_message(
                    int(messageid)
                )
            except discord.NotFound as error:
                print("Couldnt find message")
                print(error)
                countdown_message = await announcement_channel.send(
                    "Error while fetching timer message. Respawning timer..."
                )
                await self.raid_dao.set_countdown_message(guild.id, countdown_message.id)


        if countdown_message is None and spawn:
            print("creating countdown message")
            countdown_message = await announcement_channel.send("Respawning timer ...")
            await self.raid_dao.set_countdown_message(guild.id, countdown_message.id)

        if cooldown is not None:
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

                    await self.raid_dao.set_cooldown_reminded(guild.id)
                    await announcement_channel.send("Set the raid timer!\n{}".format(', '.join(to_ping)))
                    await self.clear_current_raid(guild.id)

            else:
                arr = cdn - now
                hms = get_hms(arr)
                await countdown_message.edit(
                    content=TIMER_TEXT.format("cooldown ends in", hms[0], hms[1], hms[2])
                )

        if spawn is not None:
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
                await self.raid_dao.set_raid_reset(guild.id, reset + 1)

            await countdown_message.edit(
                content=TIMER_TEXT.format(text, hms[0], hms[1], hms[2])
            )

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

        is_active = queue_config.get(QUEUE_ACTIVE, 0)
        if not is_active:
            return

        queued_users = await self.queue_dao.get_queued_users(guild.id, queue)

        raid_config = await self.raid_dao.get_raid_configuration(guild.id)
        print(raid_config)
        
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

    @raid_timer.before_loop
    async def wait_for_bot(self):
        print("waiting for the bot to be ready")
        await self.bot.wait_until_ready()

    @commands.group(name="raid", aliases=["r"], invoke_without_command=True)
    async def raid(self, ctx):
        pass

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
        raid_config = await self.raid_dao.get_raid_configuration(ctx.guild.id)
        now = arrow.utcnow()

        cooldown = raid_config.get(RAID_COOLDOWN, None)
        spawn = raid_config.get(RAID_SPAWN, None)
        announcement_channel_id = int(raid_config.get(RAID_ANNOUNCEMENTCHANNEL, 0))

        announcement_channel = ctx.guild.get_channel(announcement_channel_id)

        if not time:
            time = now.shift(hours=24)

        if not announcement_channel:
            raise commands.BadArgument("No announcementchannel configured")

        if cooldown:
            cdn = arrow.get(cooldown)
            if cdn > now:
                raise commands.BadArgument(f"Raid is currently on cooldown. Wait or use **{ctx.prefix}raid cancel** first")

        if spawn:
            raise commands.BadArgument(f"Raid is currently active. Use **{ctx.prefix}raid clear** or **{ctx.prefix}raid cancel** first")

        #TODO clear current raid in dao
        await self.clear_current_raid(ctx.guild.id)

        await self.raid_dao.set_raid_spawn(ctx.guild.id, time.timestamp)
        await ctx.send(f":white_check_mark: Set raid timer")

    @commands.check(raidconfig_exists)
    @raid.command(name="when")
    async def raid_when(self, ctx):
        raid_config = await self.raid_dao.get_raid_configuration(ctx.guild.id)
        channel_id = raid_config.get(RAID_ANNOUNCEMENTCHANNEL, 0)
        channel = ctx.guild.get_channel(int(channel_id))
        if not channel:
             raise commands.BadArgument("Could not find announcement channel. :<")

        await ctx.send(f"Check {channel.mention}, you lazy fuck!")

    @commands.check(raidconfig_exists)
    @commands.check(has_raid_timer_permissions)
    @raid.command(name="clear")
    async def raid_clear(self, ctx, duration: typing.Union[Duration] = None):
        raid_config = await self.raid_dao.get_raid_configuration(ctx.guild.id)
        spawn = raid_config.get(RAID_SPAWN, 0)
        cd = raid_config.get(RAID_COOLDOWN, 0)

        if not spawn and not cd:
            raise commands.BadArgument("No raid to clear")

        if cd:
            raise commands.BadArgument("Raid has been cleared already")

        now = arrow.utcnow()
        spwn_arrow = arrow.get(spawn)
        if now < spwn_arrow:
            raise commands.BadArgument(
                f"Can't clear unspawned raid. Use **{ctx.prefix}raid cancel** to cancel it."
            )

        if duration is None:
            duration = now.shift(minutes=59, seconds=59)

        delta_cd = duration - now
        _h, _m, _s = get_hms(delta_cd)
        shifter = {}
        if _m not in [0, 59]:
            shifter["minutes"] = 60 - _m
        if _s not in [0, 59]:
            shifter["seconds"] = 60 - _s
        if duration < spwn_arrow.shift(minutes=59, seconds=58):
            raise commands.BadArgument("Cooldown end must be 60m after raid.")

        total_time = now.shift(**shifter) - spwn_arrow
        _h2, _m2, _s2 = get_hms(total_time)
        cleared = f"**{_h2}**h **{_m2}**m **{_s2}**s"
        await ctx.send(
            "Raid **cleared** in {}.".format(cleared)
        )

        #TODO clear current raid in dao
        await self.clear_current_raid(ctx.guild.id)

        shft_arrow = now.shift(minutes=_m > 0 and _m or 0, seconds=_s > 0 and _s or 0)
        await self.raid_dao.set_raid_cooldown(ctx.guild.id, shft_arrow.timestamp)

        cleared = f"**{_h}**h **{_m}**m **{_s}**s"
        announcement_channel = int(raid_config.get(RAID_ANNOUNCEMENTCHANNEL, 0))
        announce = ctx.guild.get_channel(announcement_channel)
        if announce is None:
            raise commands.BadArgument("Could not find announce channel. :<")
        msg = await announce.send(f"Raid cooldown ends in {cleared}.")
        await self.raid_dao.set_countdown_message(ctx.guild.id, msg.id)

    @commands.check(raidconfig_exists)
    @raid.command(name="cancel")
    @commands.check(has_raid_timer_permissions)
    async def raid_cancel(self, ctx):
        raid_config = await self.raid_dao.get_raid_configuration(ctx.guild.id)
        spawn = raid_config.get(RAID_SPAWN, None)
        cd = raid_config.get(RAID_COOLDOWN, None)
        if not any([spawn, cd]):
            raise commands.BadArgument("No raid to cancel")
        
        #TODO clear current raid in dao
        await self.clear_current_raid(ctx.guild.id)
        await ctx.send("Cancelled the current raid.")

    @raid.group(name="queue", aliases=["q"], invoke_without_command=True)
    @commands.check(raidconfig_exists)
    async def raid_queue(self, ctx, queue: typing.Union[Queue] = "default"):
        queueconfig, queued_users = await asyncio.gather(
            self.queue_dao.get_queue_configuration(ctx.guild.id, queue),
            self.queue_dao.get_queued_users(ctx.guild.id, queue),
            return_exceptions=True
        )

        current_users = queueconfig.get(QUEUE_CURRENT_USERS, "").split()

        if str(ctx.author.id) in queued_users:
            await ctx.send(f"Sorry **{ctx.author.name}**, you are already **#{queued_users.index(str(ctx.author.id))}** in the queue")
        elif str(ctx.author.id) in current_users:
            await ctx.send(f"**{ctx.author.name}**, you are currently attacking, use **{ctx.prefix}raid done {queue}** to finish your turn")
        else:
            res = await self.queue_dao.add_user_to_queued_users(ctx.guild.id, queue, ctx.author.id)
            queued_users.append(ctx.author.id)
            if res:
                await ctx.send(f":white_check_mark: Ok **{ctx.author.name}**, i've added you to the queue")
            else:
                ctx.send(f"Sorry **{ctx.author.name}**... Something went wrong. Please try to queue up again")

    @raid_queue.command(name="show")
    @commands.check(raidconfig_exists)
    async def raid_queue_show(self, ctx, queue: typing.Union[Queue] = "default"):
        queued_users, queueconfig = await asyncio.gather(
            self.queue_dao.get_queued_users(ctx.guild.id, queue),
            self.queue_dao.get_queue_configuration(ctx.guild.id, queue),
            return_exceptions=True
        )

        queue_size = int(queueconfig.get(QUEUE_SIZE, 1))
        clusters = zip_longest(*[iter(queued_users)] * queue_size, fillvalue=None)

        result = []
        for c in clusters:
            temp = str(len(result) + 1)
            r = []
            for u in c:
                if u is not None:
                    ux = await self.bot.fetch_user(int(u))
                    r.append(f"{ux}")
            result.append(temp + ". " + ", ".join(r))
            
        queue_name = queueconfig.get(QUEUE_NAME, None)
        
        if result:
            await ctx.send(
                "**Queue** for **{}**:\n```css\n{}```\nUse **{}raid unqueue** to cancel.".format(
                   queue_name if queue_name else queue, result and "\n".join(result) or " ", ctx.prefix
                )
            )
        else:
            await ctx.send(f"Queue **{queue_name if queue_name else queue}** is currently empty")

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
    @commands.check(raidconfig_exists)
    async def raid_unqueue(self, ctx, queue: typing.Union[Queue] = "default"):
        queueconfig = await self.queue_dao.get_queue_configuration(ctx.guild.id, queue)
        queued_users = await self.queue_dao.get_queued_users(ctx.guild.id, queue)
        current_users = queueconfig.get(QUEUE_CURRENT_USERS, "").split()

        if str(ctx.author.id) in current_users:
            await ctx.send("Its currently your turn. Use raid queue done")
            return
        
        if not str(ctx.author.id) in queued_users:
            await ctx.send("You are currently not queued")
            return
        
        await self.queue_dao.remove_user_from_queued_users(ctx.guild.id, queue, ctx.author.id)
        await ctx.send("Ok, i removed you from queue")

    @raid.command(name="done", aliases=["d"])
    @commands.check(raidconfig_exists)
    async def raid_done(self, ctx, queue: typing.Union[Queue] = "default"):
        queue_config = await self.queue_dao.get_queue_configuration(ctx.guild.id, queue)
        queued_users = await self.queue_dao.get_queued_users(ctx.guild.id, queue)

        current_users = queue_config.get(QUEUE_CURRENT_USERS, "").split()

        if not str(ctx.author.id) in current_users:
            if not str(ctx.author.id) in queued_users:
                await ctx.send("It's not your turn & you're not queued.")
                return
            else:
                await ctx.send(f"Not your go. Do **{ctx.prefix}raid unqueue {queue}** instead.")
                return
        else:
            current_users = " ".join(current_users)
            current_users = current_users.replace(str(ctx.author.id), "")
            await self.queue_dao.set_current_users(ctx.guild.id, queue, current_users.strip())
            await ctx.send(f"**{ctx.author}** has finished their turn.")
            return

    @commands.group(name="raidconfig", invoke_without_command=True)
    async def raidconfig(self, ctx):
        pass

    @raidconfig.command(name="show")
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
        
        elif config_key in [RAID_MANAGEMENT_ROLES, RAID_TIMER_ROLES]:
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
            print(val)

        await self.raid_dao.set_key(ctx.guild.id, config_key, val)
        await ctx.send(f":white_check_mark: Successfully set **{config_key}** to {formatted_value if formatted_value else val}")
        
    @commands.group(name="queueconfig", invoke_without_command=True)
    async def queueconfig(self, ctx):
        pass

# raidconfig:
#     raidconfig show
#         prints all configurable raid config keys + values

#     raidconfig set <key> <value>

#     queueconfig show <queue?>
#         if not queue
#             prints all queues + configurable queue config keys + values
#         if queue
#             prints all configurable queue config keys + values for the given queue

#     queueconfig set <queue?> <key> <value>
#         if not queue
#             queue = "default"

#         sets the new value for the given key for the supplied queue
    @queueconfig.command(name="show")
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

        if config_key in [QUEUE_SIZE]:
            try:
                value = int(config_value)
                formatted_value = f"**{value}**"
            except ValueError:
                raise commands.BadArgument(f"Cannot set **{config_key}** to **{value}**. Integer required")
        elif config_key in [QUEUE_PING_AFTER]:
            role = await commands.RoleConverter().convert(ctx, config_value)
            value = role.id
            formatted_value = f"@**{role.name}**"
        else:
            value = config_value
            formatted_value = f"**{value}**"

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
        await ctx.send(f"Started queue {queue_name}") 

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
    bot.add_cog(RaidModule(bot))
