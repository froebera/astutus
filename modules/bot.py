"""Discord AstutusBot."""
import datetime
import sys
import asyncio
import os
from os import listdir
from os.path import isfile, join
from itertools import chain
import arrow
import discord
from discord.ext import commands as cmds
from discord.utils import get
from modules.utils.checks import user_has_role
# from modules.webserver.app import app

extensions = [
    "autorole",
    "censor",
    "channels",
    "curation",
    "disable",
    "fun",
    "greet",
    "help",
    "info",
    "logging",
    "math",
    "moderation",
    # "music",
    # "patrons",
    "postgre",
    # "premium",
    "restrictions",
    "sar",
    "settings",
    "setup",
    "starboard",
    "timers",
    "todo",
    "tracking",
    "tt",
    "utility",
    "worldchat",
    "xp"
]

async def prefix_callable(bot, message) -> list:
    """Setup the bot prefix function."""
    user_id = bot.user.id
    prefix_base = [f"<@!{user_id}> ", f"<@{user_id}> "]
    if message.guild is not None:
        prefix_base.append(bot.config["DEFAULT"]["prefix"])
        custom = await bot.db.hget(f"{message.guild.id}:set", "pfx")
        if custom or custom is not None:
            prefix_base.append(custom)
        pprefix_enabled = await bot.db.hget(f"{message.guild.id}:toggle", "pprefix")
        if pprefix_enabled is not None and pprefix_enabled != "0":
            pprefix = await bot.db.hget("pprefix", message.author.id)
            if pprefix is not None:
                prefix_base.append(pprefix)
    return prefix_base


class AstutusBot(cmds.AutoShardedBot):
    """Defines the bot class."""

    def __init__(self, config):
        super().__init__(
            command_prefix=prefix_callable,
            description="",
            pm_help=None,
            help_attrs={"hidden": True},
            fetch_offline_members=False,
        )
        self.config = config
        self.exit_code = None
        self.prefixes = {}
        self.booted_at = None
        self.link_admin = None
        self.link_normal = None
        self.db = None
        self.cdn = None
        self.blacklists = dict(users=[], channels=[], servers=[])
        self.remove_command("help")
        self.load_extensions()

    def load_extensions(self):
        """Load the bot's extension modules."""
        # extensions = [
        #     f.replace(".py", "")
        #     for f in listdir(self.config["DEFAULT"]["cogs"])
        #     if isfile(join(self.config["DEFAULT"]["cogs"], f))
        # ]
        for extension in extensions:
            print(extension)
            try:
                self.load_extension(
                    "{}.{}".format(self.config["DEFAULT"]["cogs"], extension)
                )
            except (discord.ClientException, ModuleNotFoundError):
                print(f"Failed to load extension {extension}.", file=sys.stderr)

    async def embed(self):
        embed = discord.Embed(timestamp=arrow.utcnow().datetime)
        embed.set_footer(text=str(self.user), icon_url=self.user.avatar_url)
        return embed

    async def on_ready(self):
        """Do these things when the bot is connected to discord's api."""
        if not hasattr(self, "booted_at"):
            self.booted_at = datetime.datetime.utcnow()
        oauth = "https://discordapp.com/api/oauth2/authorize?client_id={}&permissions={{}}&scope=bot".format(
            self.user.id
        )
        setattr(self, "link_admin", oauth.format("8"))
        setattr(self, "link_normal", oauth.format("2146954487"))
        print(f"Ready: {self.user} (ID: {self.user.id})")
        print(f"Invite link: {self.link_admin}")
        # webserver = app.create_server(
        #     host="0.0.0.0", port=80, return_asyncio_server=True
        # )
        loop = self.loop
        # asyncio.ensure_future(webserver)

    async def on_command_error(self, ctx, error):
        """Hooks for discord.py command errors."""
        if isinstance(error, cmds.CommandOnCooldown):
            cooldown = round(error.retry_after)
            await ctx.send(
                "Woah **{}**, please cool down. Try **{}{}** again in **{}**s.".format(
                    ctx.author, ctx.prefix, ctx.invoked_with, cooldown
                )
            )
        elif isinstance(error, cmds.BadArgument):
            await ctx.send(f":negative_squared_cross_mark: {error}")

        elif isinstance(error, cmds.BadUnionArgument):
            await ctx.send(
                f":negative_squred_cross_mark: You didn't supply any valid items! {ctx.prefix}help {ctx.command.qualified_name}"
            )
        elif isinstance(error, cmds.MissingPermissions):
            perms = ", ".join(error.missing_perms)
            await ctx.send(f":no_entry: {perms}.")

        elif isinstance(error, cmds.BotMissingPermissions):
            perms = ", ".join([f"**{perm}**" for perm in error.missing_perms])
            await ctx.send(f":warning: I need permission to {perms} for this to work.")
        
        elif isinstance(error, cmds.MissingRequiredArgument):
            # TODO Find usage for cmd ?
            await ctx.send(f":negative_squared_cross_mark: {error}")

        else:
            print(error)
            await ctx.send(f":warning: Something went wrong... Please contact the Bot author. {str(error)}")
            raise error

    async def process_commands(self, message: discord.Message):
        ctx = await self.get_context(message)
        if ctx.command is None or ctx.author.bot or not getattr(ctx, "guild"):
            return

        disabled = await ctx.bot.db.lrange(f"{ctx.guild.id}:disable")
        if ctx.command.cog_name.replace("Module", "").lower() in disabled:
            return

        restrictions = await ctx.bot.db.hget(f"{ctx.guild.id}:toggle", "restrictions")
        if restrictions == "1":
            mode = await ctx.bot.db.hget(f"{ctx.guild.id}:set", "rmode")
            cog = ctx.bot.get_cog("RestrictionsModule")
            _, chan, role, mem = await cog.get_restrictions(
                ctx.guild, ctx.command.qualified_name
            )
            chans = [get(ctx.guild.channels, id=int(c)) for c in chan]
            roles = [get(ctx.guild.roles, id=int(c)) for c in role]
            membs = [get(ctx.guild.members, id=int(c)) for c in mem]
            if not any([chans, roles, membs]):
                await self.invoke(ctx)
                return
            chan_perm = ctx.channel in chans or False
            role_perm = (
                await user_has_role(
                    [r.id for r in ctx.author.roles], *[r.id for r in roles]
                )
                or False
            )
            memb_perm = ctx.author in membs or False
            if mode == "and":
                if all([chan_perm, role_perm, memb_perm]):
                    await self.invoke(ctx)
                    return
                # else:
                rolmem = list(chain.from_iterable((roles, membs)))
                text = "**{}** can only be used".format(ctx.command.qualified_name)
                if chans:
                    text = text + " in " + ", ".join([f"**#{x}**" for x in chans])
                if rolmem:
                    text = text + " by " + ", ".join([f"**@{x}**" for x in rolmem])
                await ctx.send(text)
                return
            if not any([chan_perm, role_perm, memb_perm]):
                text = "**{}** can be used if:\n".format(ctx.command.qualified_name)
                res = []
                if chans:
                    res.append("are in " + ", ".join([f"**#{x}**" for x in chans]))
                if roles:
                    res.append(
                        "have the role " + ", ".join([f"**@{x}**" for x in roles])
                    )
                if membs:
                    res.append("are " + ", ".join([f"**@{x}**" for x in membs]))
                res = [f"- you {r}" for r in res]
                await ctx.send(
                    ":negative_squared_cross_mark: {}{}".format(
                        text, "; or\n".join(res)
                    )
                )
                return
        log_commands = await ctx.bot.db.hget(f"{ctx.guild.id}:set", "logcommands") or 0
        log_cmd = ctx.guild.get_channel(int(log_commands))
        if log_cmd is not None:
            embed = await ctx.bot.embed()
            embed.description = f"{ctx.author.mention} used command **{ctx.command.qualified_name}** in {ctx.channel.mention}"
            embed.color = ctx.author.color
            await log_cmd.send(embed=embed)
        await self.invoke(ctx)

    async def on_message(self, message: discord.Message):
        await self.process_commands(message)

    async def stop(self, exit_code: int = 0, force: bool = False):
        """Attempt to forcefully stop the bot."""
        if force:
            sys.exit(exit_code)
        await self.db.disconnect()
        await self.loop.stop()
        self.exit_code = exit_code

    def run(self):
        token = self.config["DEFAULT"].get("token", os.environ.get("DISCORD_TOKEN", ""))
        super().run(token, reconnect=True)
