import os
import sys
import configparser
import logging.config

# import yaml
import json
import discord
from discord.ext import commands
from context.context import Context
from db import RedisConnection, RaidDao, QueueDao, PostgresConnection


def apply_overwrite(node, key, value):
    if isinstance(value, dict):
        for item in value:
            apply_overwrite(node[key], item, value[item])
    else:
        node[key] = value


def setup_logging():
    log_config_path = "logging-default.json"
    log_config_overwrite_path = "logging.json"
    c = None
    if os.path.exists(log_config_path):
        with open(log_config_path, "rt") as f:
            c = json.load(f)

    if os.path.exists(log_config_overwrite_path):
        with open(log_config_overwrite_path, "rt") as f:
            if not c:
                c = json.load(f)
            else:
                overwrite_values = json.load(f)
                for overwrite_key, value in overwrite_values.items():
                    apply_overwrite(c, overwrite_key, value)

    if c:
        logging.config.dictConfig(c)
    else:
        logging.basicConfig(level="INFO")


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
            fetch_offline_members=True,
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


print(__name__)

setup_logging()

cfg = get_config("config.ini")

context = Context(
    {
        "redis_connection": RedisConnection(cfg["REDIS"]),
        "postgres_connection": PostgresConnection(cfg["POSTGRESQL"]),
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


bot.run()
