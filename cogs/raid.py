from discord.ext import tasks
from discord.ext import commands
from discord.utils import get
from datetime import timedelta
from itertools import zip_longest
from .utils.converters import Queue
import typing
import asyncio
import arrow
import discord

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

TIMER_TEXT = "Raid {} **{:02}**h **{:02}**m **{:02}**s."
QUEUE_CONFIG_KEY = "raid:{}:queue:{}"
RAID_CONFIG_KEY = "raid:{}"
QUEUE_KEY = "raid:{}:queue:{}:q"

QUEUE_CURRENT_USERS = "current_users"
QUEUE_SIZE = "size"
QUEUE_NAME = "name"
QUEUE_ACTIVE = "active"
QUEUE_PROGRESS = "in_progress"

QUEUE_CONFIG_KEYS = [QUEUE_NAME, QUEUE_SIZE]

RAID_ANNOUNCEMENTCHANNEL = "channel"
RAID_SPAWN = "spawn"
RAID_RESET = "reset"
RAID_COUNTDOWNMESSAGE = "countdown_message"

ALIAS_SKIP = ["skip"]
ALIAS_SHOW = ["show"]
ALIAS_CLEAR = ["clear"]


def get_hms(delta: timedelta):
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 60 * 60)
    minutes, seconds = divmod(remainder, 60)
    return hours, minutes, seconds


class RaidModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.raid_timer.start()

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
        # print("starting timer handler")
        # print("current guild {}, now: {}".format(guild, now))
        """
            TODO
                update raid timer message
                handle raid queue
                handle on demand queues
        """
        current_raid_config = await self.get_raid_configuration(guild.id)
        if not current_raid_config:
            raise asyncio.CancelledError

        announcement_channel = guild.get_channel(
            int(current_raid_config.get(RAID_ANNOUNCEMENTCHANNEL, 0))
        )
        spawn = current_raid_config.get(RAID_SPAWN, None)
        reset = int(current_raid_config.get(RAID_RESET, 0))
        messageid = current_raid_config.get(RAID_COUNTDOWNMESSAGE, None)

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
                await self.bot.db.hset(
                    f"raid:{guild.id}", "countdown_message", countdown_message.id
                )

        if countdown_message is None and spawn:
            print("creating countdown message")
            countdown_message = await announcement_channel.send("Respawning timer ...")
            await self.bot.db.hset(
                f"raid:{guild.id}", "countdown_message", countdown_message.id
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
                is_default_queue_active = await self.bot.db.hget(
                     f"raid:{guild.id}:queue:default", "active"
                )
                if not is_default_queue_active:
                    await self.bot.db.hset(f"raid:{guild.id}:queue:default", "active", 1)
                await self.bot.db.hset(RAID_CONFIG_KEY.format(guild.id), RAID_RESET, reset + 1)

            await countdown_message.edit(
                content=TIMER_TEXT.format(text, hms[0], hms[1], hms[2])
            )

    async def handle_queues_for_guild(self, guild):
        queues = await self.bot.db.lrange(f"raid:{guild.id}:queues")
        await asyncio.gather(
            *(self.handle_queue(guild, queue) for queue in queues),
            return_exceptions=True,
        )

    async def handle_queue(self, guild, queue):
        # await self.bot.db.hgetall(f"raid:{guild.id}:{queue}")
        queue_config = await self.get_raid_queue_configuration(guild.id, queue)
        current_users = queue_config.get(QUEUE_CURRENT_USERS, "").split()
        queue_size = int(queue_config.get(QUEUE_SIZE, 0))
        queue_in_progress = int(queue_config.get(QUEUE_PROGRESS, 0))

        is_active = queue_config.get(QUEUE_ACTIVE, 0)
        if not is_active:
            return

        queued_users = await self.get_raid_queued_user(guild.id, queue)

        raid_config = await self.get_raid_configuration(guild.id)
        print(raid_config)
        
        announcement_channel = guild.get_channel(
            int(raid_config.get(RAID_ANNOUNCEMENTCHANNEL, 0))
        )
        
        if announcement_channel is None:
            print("Announcement channel is none")
            return;

        if not queue_in_progress:
            await announcement_channel.send(f"Queue 'name' started, should ping here")
            await self.bot.db.hset(QUEUE_CONFIG_KEY.format(guild.id, queue), QUEUE_PROGRESS, 1)

        if queue_size == 0:
            print("queue size == 0; returning")
            # what to do here ? 
            # just leave it for now
            # set depl to 1
            # set active to 0

            await self.bot.db.hdel(QUEUE_CONFIG_KEY.format(guild.id, queue), QUEUE_PROGRESS)
            await self.bot.db.hdel(QUEUE_CONFIG_KEY.format(guild.id, queue), QUEUE_ACTIVE)
            await announcement_channel.send("Queue is over")

            return

        if current_users:
            # users are currently attacking
            print("Users are currently attacking")
            return

        if not queued_users and not current_users:
            # Queue is over
            await self.bot.db.hdel(QUEUE_CONFIG_KEY.format(guild.id, queue), QUEUE_PROGRESS)
            await self.bot.db.hdel(QUEUE_CONFIG_KEY.format(guild.id, queue), QUEUE_ACTIVE)
            await announcement_channel.send("Queue is over")
            print("Queue is over")

        if queued_users:
            next_users = queued_users[0:queue_size]
            queued_members = [guild.get_member(int(memberid)) for memberid in next_users]
            print(next_users)
            print(queued_members)
            i = 0
            while i < len(next_users):
                await self.remove_user_from_queue(guild.id, queue, next_users[i])
                i += 1
                
            await self.bot.db.hset(
                f"raid:{guild.id}:queue:{queue}",
                QUEUE_CURRENT_USERS,
                " ".join([str(m.id) for m in queued_members]),
            )

            print("sending announcement")

            await announcement_channel.send(
                "It's {}'s turn to attack the raid!".format(
                    ", ".join([f"{m.mention}" for m in queued_members])
                )
            )

    @commands.group(name="raid", aliases=["r"])
    async def raid(self, ctx):
        pass

    @raid_timer.before_loop
    async def wait_for_bot(self):
        print("waiting for the bot to be ready")
        await self.bot.wait_until_ready()

    async def create_on_demand_queue(self, ctx):
        pass

    @raid.command(name="setup", description="initial raid config setup")
    async def raid_initial_setup(self, ctx):
        # raid:{guildid}
        # input = get(ctx.guild.channels, id=612922052571168779)
        # print(chan)
        chan = await commands.TextChannelConverter().convert(ctx, "612922052571168779")
        chanid = chan.id

        # TODO ensure unique entries in q list only, or use set?
        await self.bot.db.delete(f"raid:{ctx.guild.id}:queues")

        # raid.{guildid}:channel = chanid

        channsaveres = await self.bot.db.hset(f"raid:{ctx.guild.id}", "channel", chanid)

        await self.bot.db.rpush(f"raid:{ctx.guild.id}:queues", "default")
        default_queue_key = f"raid:{ctx.guild.id}:queue:default"
        await self.bot.db.hset(default_queue_key, QUEUE_NAME, "Reset Queue")
        await self.bot.db.hset(default_queue_key, QUEUE_SIZE, 1)

        # channel = ctx.guild.get_channel(chanid)
        # await channel.send("Hello from raid setup")
        await ctx.send(f"raid setup done :) {channsaveres}")

    # TODO requires check if any raid is active / params for when the raid starts
    @raid.command(name="in")
    async def raid_in(self, ctx):
        now = arrow.utcnow()
        time = now.shift(seconds=30)
        print(time)

        await self.bot.db.hdel(f"raid:{ctx.guild.id}", RAID_SPAWN)
        await self.bot.db.hdel(f"raid:{ctx.guild.id}", RAID_COUNTDOWNMESSAGE)
        await self.bot.db.hdel(RAID_CONFIG_KEY.format(ctx.guild.id), RAID_RESET)

        spawnres = await self.bot.db.hset(
            f"raid:{ctx.guild.id}", "spawn", time.timestamp
        )
        await ctx.send(f"set raid timer response: {spawnres}")

    @raid.group(name="queue")
    async def raid_queue(self, ctx, *args):
        queue = "default"
        arg = None

        if len(args) > 2:
            raise commands.BadArgument("To many arguments")

        if len(args) == 1:
            if args[0] in ALIAS_CLEAR + ALIAS_SHOW + ALIAS_SKIP:
                arg = args[0]
            else:
                queue = args[0]
        elif len(args) == 2:
            queue, arg = args[0], args[1]

        await self.check_if_queue_exists_or_break(ctx.guild.id, queue)

        if not arg is None:
            if arg in ALIAS_SHOW:
                await self.raid_queue_show(ctx, queue)
            elif arg in ALIAS_CLEAR:
                await self.raid_queue_clear(ctx, queue)
            elif arg in ALIAS_SKIP:
                await self.raid_queue_skip(ctx, queue)
            return

        # queueconfig = await self.get_raid_queue_configuration(ctx.guild.id, queue)
        # queued_users = await self.get_raid_queued_user(ctx.guild.id, queue)

        queueconfig, queued_users = await asyncio.gather(
            self.get_raid_queue_configuration(ctx.guild.id, queue),
            self.get_raid_queued_user(ctx.guild.id, queue),
            return_exceptions=True
        )

        current_users = queueconfig.get(QUEUE_CURRENT_USERS, "").split()

        if str(ctx.author.id) in queued_users:
            await ctx.send(f"Sorry **{ctx.author.name}**, you are already **#{queued_users.index(str(ctx.author.id))}** in the queue")
        elif str(ctx.author.id) in current_users:
            await ctx.send(f"**{ctx.author.name}**, you are currently attacking, use **{ctx.prefix}raid done** to finish your turn")
        else:
            res = await self.add_user_to_queue(ctx.guild.id, queue, ctx.author.id)
            queued_users.append(ctx.author.id)
            if res:
                await ctx.send(f":white_check_mark: Ok **{ctx.author.name}**, i've added you to the queue")
            else:
                ctx.send(f"Sorry **{ctx.author.name}**... Something went wrong. Please try to queue up again")

    async def raid_queue_show(self, ctx, queue):
        # queued_users = await self.get_raid_queued_user(ctx.guild.id, queue)
        # queueconfig = await self.get_raid_queue_configuration(ctx.guild.id, queue)

        queued_users, queueconfig = await asyncio.gather(
            self.get_raid_queued_user(ctx.guild.id, queue),
            self.get_raid_queue_configuration(ctx.guild.id, queue),
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
            
        if result:
            await ctx.send(
                "**Queue** for **{}**:\n```css\n{}```\nUse **{}tt unqueue** to cancel.".format(
                    "TODO dummy", result and "\n".join(result) or " ", ctx.prefix
                )
            )
        else:
            await ctx.send(f"Queue **{queue}** is currently empty")
    
    async def raid_queue_clear(self, ctx, queue):
        await asyncio.gather(
            self.bot.db.delete(QUEUE_KEY.format(ctx.guild.id, queue)),
            self.bot.db.hdel(QUEUE_CONFIG_KEY.format(ctx.guild.id, queue), QUEUE_CURRENT_USERS)
        )
        await ctx.send(f":white_check_mark: Queue **{queue}** has been cleared!")

    async def raid_queue_skip(self, ctx, queue):
        await self.bot.db.hdel(QUEUE_CONFIG_KEY.format(ctx.guild.id, queue), QUEUE_CURRENT_USERS)
        await ctx.send(f":white_check_mark: **{queue}**: Current attackers cleared")

    @raid.command(name="unqueue")
    async def raid_unqueue(self, ctx, queue: typing.Optional[str] = "default"):
        queues = await self.get_all_raid_queues(ctx.guild.id)
        if queue not in queues:
            await ctx.send("Queue not found")

        queueconfig = await self.get_raid_queue_configuration(ctx.guild.id, queue)
        queued_users = await self.get_raid_queued_user(ctx.guild.id, queue)
        current_users = queueconfig.get(QUEUE_CURRENT_USERS, "").split()

        if str(ctx.author.id) in current_users:
            await ctx.send("Its currently your turn. Use raid queue done")
            return
        
        if not str(ctx.author.id) in queued_users:
            await ctx.send("You are currently not queued")
            return
        
        await self.remove_user_from_queue(ctx.guild.id, queue, ctx.author.id)
        await ctx.send("Ok, i removed you from queue")

    @raid.command(name="done")
    async def raid_done(self, ctx, queue: typing.Optional[str] = "default"):
        queue_config = await self.get_raid_queue_configuration(ctx.guild.id, queue)
        queued_users = await self.get_raid_queued_user(ctx.guild.id, queue)

        current_users = queue_config.get(QUEUE_CURRENT_USERS, "").split()

        if not str(ctx.author.id) in current_users:
            if not str(ctx.author.id) in queued_users:
                await ctx.send("It's not your turn & you're not queued.")
                return
            else:
                await ctx.send(f"Not your go. Do **{ctx.prefix}tt uq** instead.")
                return
        else:
            current_users = " ".join(current_users)
            current_users = current_users.replace(str(ctx.author.id), "")
            await self.bot.db.hset(QUEUE_CONFIG_KEY.format(ctx.guild.id, queue), QUEUE_CURRENT_USERS,current_users.strip())
            await ctx.send(f"**{ctx.author}** has finished their turn.")
            return

    @commands.group(name="raidconfig", invoke_without_command=True)
    async def raidconfig(self, ctx):
        await ctx.send("Raidconfig list")

    @raidconfig.command(name="edit")
    async def raidconfig_edit(self, ctx):
        await ctx.send("Raidconfig edit")

    @commands.group(name="queueconfig", invoke_without_command=True)
    async def queueconfig(self, ctx):
        await ctx.send("Queueconfig list")


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
    async def queueconfig_show(self, ctx, queue: typing.Union[Queue] = None):
        if queue:
            queues = [queue]
        else:
            queues = await self.get_all_raid_queues(ctx.guild.id)
        
        queue_configurations = await asyncio.gather(
            *(self.get_raid_queue_configuration(ctx.guild.id, q) for q in queues),
            return_exceptions=True
        )


        tmp = []
        for i, queue_configuration in enumerate(queue_configurations):
            tmp.append(f"Config values for queue **{queues[i]}** ({queue_configuration.get(QUEUE_NAME)}):")
            for config_key in QUEUE_CONFIG_KEYS:
                config_value = queue_configuration.get(config_key, None)
                tmp.append(f"{config_key}: {config_value}")
            
            tmp.append("")

        await ctx.send("**Queue configuration:**\n\n{}".format('\n'.join(tmp)))

    @queueconfig.command(name="set")
    async def queueconfig_set(self, ctx, queue: typing.Optional[Queue], config_key: typing.Union[QueueConfigKey], value):
        if not queue:
            queue = "default"
        await ctx.send(f"{queue}, {config_key}, {value}")

        if config_key in [QUEUE_SIZE]:
            try:
                int(value)
            except ValueError:
                raise commands.BadArgument(f"Cannot set **{config_key}** to **{value}**. Integer required")

        await self.bot.db.hset(QUEUE_CONFIG_KEY.format(ctx.guild.id, queue), config_key, value)
        await ctx.send(f":white_check_mark: Successfully set **{config_key}** to **{value}** for queue **{queue}**")


    async def get_all_raid_queues(self, guild_id):
        return await self.bot.db.lrange(f"raid:{guild_id}:queues")
        
    async def get_raid_queue_configuration(self, guild_id, queue_name):
        return await self.bot.db.hgetall(f"raid:{guild_id}:queue:{queue_name}")

    async def get_raid_queued_user(self, guild_id, queue_name):
        return await self.bot.db.lrange(f"raid:{guild_id}:queue:{queue_name}:q")

    async def add_user_to_queue(self, guild_id, queue_name, user_id):
        # return await self.bot.db.lrem(f"raid:{guild_id}:queue:{queue_name}:q", user_id)
        return await self.bot.db.rpush(f"raid:{guild_id}:queue:{queue_name}:q", user_id)

    async def remove_user_from_queue(self, guild_id, queue_name, user_id):
        return await self.bot.db.lrem(f"raid:{guild_id}:queue:{queue_name}:q", user_id)

    async def get_raid_configuration(self, guild_id):
        return await self.bot.db.hgetall(f"raid:{guild_id}")

    async def check_if_queue_exists_or_break(self, guild_id, queue):
        queues = await self.get_all_raid_queues(guild_id)
        if not queue in queues:
            raise commands.BadArgument(f"Queue **{queue}** does not exist. Available queues: {', '.join(queues)}")


def setup(bot):
    bot.add_cog(RaidModule(bot))
