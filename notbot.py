from discord.ext import commands
from context.context import Context
from db import RedisConnection, RaidDao, QueueDao
import asyncio
import configparser
import discord
import sys

extensions = [
    "cogs.raid",
    "cogs.admin",
    "cogs.info",
    # "cogs.stats",
    # "cogs.test",
    # "cogs.help"
]


async def prefix_callable(b, message) -> list:
    user_id = bot.user.id
    prefix_base = [f"<@!{user_id}> ", f"<@{user_id}> "]
    if message.guild is not None:
        prefix_base.append(bot.config["DEFAULT"]["prefix"])
    #     custom = await bot.db.hget(f"{message.guild.id}:set", "pfx")
    #     if custom or custom is not None:
    #         prefix_base.append(custom)
    #     pprefix_enabled = await bot.db.hget(f"{message.guild.id}:toggle", "pprefix")
    #     if pprefix_enabled is not None and pprefix_enabled != "0":
    #         pprefix = await bot.db.hget("pprefix", message.author.id)
    #         if pprefix is not None:
    #             prefix_base.append(pprefix)
    return prefix_base
    # return "?"


class NOTBOT(commands.AutoShardedBot):
    def __init__(self, config, ctx):
        super().__init__(
            command_prefix=prefix_callable,
            description="",
            pm_help=None,
            fetch_offline_members=False,
        )
        self.config = config
        self.db = None
        self.context = ctx

        # self.remove_command("help")
        for extension in extensions:
            try:
                print(f"Loading cog {extension}")
                self.load_extension(extension)
            except (discord.ClientException, ModuleNotFoundError):
                print(f"Failed to load extension {extension}.", file=sys.stderr)

    async def on_ready(self):
        print(f"Ready: {self.user} (ID: {self.user.id})")

    def run(self):
        token = self.config["DEFAULT"]["token"]
        super().run(token, reconnect=True)

    async def on_command_error(self, ctx, error):
        """Hooks for discord.py command errors."""
        if isinstance(error, commands.CommandOnCooldown):
            cooldown = round(error.retry_after)
            await ctx.send(
                "Woah **{}**, please cool down. Try **{}{}** again in **{}**s.".format(
                    ctx.author, ctx.prefix, ctx.invoked_with, cooldown
                )
            )
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f":negative_squared_cross_mark: {error}")

        elif isinstance(error, commands.BadUnionArgument):
            await ctx.send(
                f":negative_squred_cross_mark: You didn't supply any valid items! {ctx.prefix}help {ctx.command.qualified_name}"
            )
        elif isinstance(error, commands.MissingPermissions):
            perms = ", ".join(error.missing_perms)
            await ctx.send(f":no_entry: {perms}.")

        elif isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join([f"**{perm}**" for perm in error.missing_perms])
            await ctx.send(f":warning: I need permission to {perms} for this to work.")

        elif isinstance(error, commands.MissingRequiredArgument):
            # TODO Find usage for cmd ?
            await ctx.send(f":negative_squared_cross_mark: {error}")

        else:
            print(error)
            await ctx.send(
                f":warning: Something went wrong... Please contact the Bot author. {str(error)}"
            )
            raise error

    # @commands.check
    # async def globally_block_bots(ctx):
    #     return not ctx.author.bot


def get_config(configuration_file: str = "default_config.ini"):
    config = configparser.ConfigParser()
    config.read("default_config.ini")
    if configuration_file != "default_config.ini":
        config.read(configuration_file)
    return config


cfg = get_config("config.ini")

context = Context(
    {
        "redis_connection": RedisConnection(cfg["REDIS"]),
        "raid_dao": RaidDao(),
        "queue_dao": QueueDao()
        #
    }
)

context.start()

bot = NOTBOT(config=cfg, ctx=context)


@bot.check
async def globally_block_bots(ctx):
    return not ctx.author.bot


# pool = redis_conn.con.get_or_create_redis_connection(bot.config["REDIS"])
# bot.db = pool


bot.run()
