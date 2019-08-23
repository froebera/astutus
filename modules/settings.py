import discord
import arrow
from typing import List, Optional
from discord.ext import commands as cmd
from discord.ext import tasks as tsk
from .utils import checks
from .utils.converters import Truthy
from .utils.discord_search import choose_item
from string import ascii_letters, digits

AVAILABLE_SETTINGS = [
    "censor",
    "logging",
    "modlog",
    "automod",
    "autorole",
    "greet",
    "goodbye",
    "restrictions",
    "pprefix",
    "starboard",
    "worldchat",
    "xpbroadcast",
]


class SettingsKey(cmd.Converter):
    async def convert(self, ctx: cmd.Context, arg):
        if arg.lower() not in AVAILABLE_SETTINGS:
            raise cmd.BadArgument(f"**{arg}** is not a valid server setting.")
        if arg == "censor" and not checks.is_mod():
            raise cmd.BadArgument
        return arg.lower()


class SettingsModule(cmd.Cog):
    """Set all the things that you need to set with this module. This includes toggling functions on and off, as well as setting a custom bot prefix."""

    def __init__(self, bot: cmd.Bot):
        self.bot = bot

    @cmd.group(name="settings", aliases=["set", "setting"], invoke_without_command=True)
    async def settings(self, ctx):
        toggles = await self.bot.db.hgetall(f"{ctx.guild.id}:toggle")
        _settings = await self.bot.db.hgetall(f"{ctx.guild.id}:set")
        embed = await self.bot.embed()
        embed.title = f"Settings for {ctx.guild}"

        embed.add_field(
            name=f"Settings toggles",
            value="\n".join(
                [
                    f"{'🔲' if toggles.get(k, None) not in (None, '0') else '⬛'} - {k}"
                    for k in AVAILABLE_SETTINGS
                ]
            ),
        )

        for kind in "role log channel".split():
            _list = [s for s in _settings if s.startswith(kind)]
            if kind == "log":
                _ids = {s: ctx.guild.get_channel(int(_settings[s] or 0)) for s in _list}
            elif kind == "role":
                _ids = {s: ctx.guild.get_role(int(_settings[s] or 0)) for s in _list}
            elif kind == "channel":
                _ids = {s: ctx.guild.get_channel(int(_settings[s] or 0)) for s in _list}

            if _ids:
                embed.add_field(
                    name=f"{kind.title()} settings",
                    value="\n".join(
                        [
                            f"{k.replace(kind, '')} - {v.mention}"
                            for k, v in _ids.items()
                            if v is not None
                        ]
                    ),
                )

        await ctx.send(embed=embed)

    @settings.command(name="prefix")
    @checks.is_mod()
    async def prefix(self, ctx, *, prefix=None):
        pfx_set = await self.bot.db.hget(f"{ctx.guild.id}:set", "pfx")
        if not prefix or prefix is None:
            await ctx.send("Current server prefix: **{}**".format(pfx_set or ";"))
            return
        if len(prefix) > 2:
            raise cmd.BadArgument(
                "Custom prefix must be **1** to **2** characters in length."
            )
        if any([p for p in prefix if p in ascii_letters + digits]):
            raise cmd.BadArgument(
                "Custom prefix must be a non-letter, non-number character."
            )
        await self.bot.db.hset(f"{ctx.guild.id}:set", "pfx", prefix)
        await ctx.send(f"Set the custom server prefix to **{prefix}**")

    @settings.command(name="wccensor", aliases=["worldchatcensor"])
    @checks.is_mod()
    async def worldchatc(self, ctx, enabled: Optional[bool] = False):
        await self.bot.db.hset("worldchatc", ctx.guild.id, int(not enabled))
        await ctx.send(f"Set the world-chat censor to **{enabled}**!")

    @settings.command(name="role")
    @checks.is_mod()
    @checks.bot_has_perms(manage_roles=True)
    async def role(self, ctx, roletype="", *role):
        roletypes = "auto muted jailed curator".split()
        if roletype.lower() not in roletypes:
            raise cmd.BadArgument(
                "**Role type** must be one of: {}".format(
                    ", ".join([f"**{l}**" for l in roletypes])
                )
            )
        if role:
            role = await choose_item(ctx, "role", ctx.guild, " ".join(role).lower())
        if role is None or not role:
            raise cmd.BadArgument(f"Could not find a role with that name.")
        await self.bot.db.hset(f"{ctx.guild.id}:set", f"role{roletype}", role.id)
        await ctx.send(f":white_check_mark: Set **{roletype} role** to @**{role}**")

    @settings.command(name="channel")
    @checks.is_mod()
    @checks.bot_has_perms(manage_channels=True)
    async def channel(self, ctx, channeltype="", *channel):
        channeltypes = "poll staff music worldchat starboard greet goodbye".split()
        if channeltype.lower() not in channeltypes:
            raise cmd.BadArgument(
                "**Channel type** must be one of: {}".format(
                    ", ".join([f"**{l}**" for l in channeltypes])
                )
            )
        if channel:
            channel = await choose_item(
                ctx, "text_channel", ctx.guild, " ".join(channel).lower()
            )
        if channel is None or not channel:
            raise cmd.BadArgument("Could not find a channel with that name.")
        await self.bot.db.hset(
            f"{ctx.guild.id}:set", f"channel{channeltype}", channel.id
        )
        await ctx.send(f"✅ Set **{channeltype} channel** to #**{channel}**")

    @settings.command(name="automod")
    @checks.is_mod()
    @checks.bot_has_perms(manage_roles=True)
    async def automod(self, ctx, modtype="", *count: int):
        modtypes = "mute kick ban".split()
        if modtype.lower() not in modtypes:
            raise cmd.BadArgument(
                "**Action type** must be one of: {}".format(
                    ", ".join([f"**{l}**" for l in modtypes])
                )
            )
        if count is None or not count:
            raise cmd.BadArgument("Offense count must be greater than 0.")
        if count > 30:
            raise cmd.BadArgument("Offense count must be less than or equal to 30.")
        await self.bot.db.hset(f"{ctx.guild.id}:set", f"automod{modtype}", count)
        await ctx.send(f"✅ Set automod **{modtype}** to **{count}** offenses.")

    @settings.command(name="logging", aliases=["log"])
    @checks.is_mod()
    async def logging(self, ctx, logtype="", *channel):
        logtypes = "mod joins leaves edits deletes avatars channels roles pins commands".split()
        if logtype.lower() not in logtypes:
            raise cmd.BadArgument(
                "**Log type** must be one of: {}".format(
                    ", ".join([f"**{l}**" for l in logtypes])
                )
            )
        if channel:
            channel = await choose_item(
                ctx, "text_channel", ctx.guild, " ".join(channel).lower()
            )
        if channel is None or not channel:
            raise cmd.BadArgument("Could not find a channel with that name.")
        await self.bot.db.hset(f"{ctx.guild.id}:set", f"log{logtype}", channel.id)
        await ctx.send(f"✅ Set **log{logtype}** channel to #**{channel}**!")

    @settings.command(name="greet", aliases=["welcome"])
    @checks.is_mod()
    async def greet(self, ctx, *, message):
        if len(message) > 140:
            raise cmd.BadArgument("Greets are limited to 140 characters.")
        await self.bot.db.hset(f"{ctx.guild.id}:set", "grt", message)
        await ctx.send(
            message.format(
                user=str(ctx.author), server=str(ctx.guild), mention=ctx.author.mention
            )
        )

    @settings.command(name="goodbye", aliases=["depart", "fairwell"])
    @checks.is_mod()
    async def goodbye(self, ctx, *, message):
        if len(message) > 140:
            raise cmd.BadArgument(
                "Goodbyes are limited to 140 characters. Please choose a smaller message."
            )
        await self.bot.db.hset(f"{ctx.guild.id}:set", "dpt", message)
        await ctx.send(
            message.format(
                user=str(ctx.author), server=str(ctx.guild), mention=ctx.author.mention
            )
        )

    @cmd.command(name="toggle")
    @checks.is_mod()
    async def toggle(self, ctx, setting: SettingsKey, value: Optional[Truthy]):
        "Toggle a function of the bot on or off. Everything defaults to off."
        if value is None:
            value = await self.bot.db.hget(f"{ctx.guild.id}:toggle", setting)
            value = value is None and "off" or value == "0" and "off" or "on"
            await ctx.send("**{}** is currently **{}**.".format(setting, value))
            return
        await self.bot.db.hset(f"{ctx.guild.id}:toggle", setting, value)
        await ctx.send(
            "**{}** is now **{}**".format(setting, int(value) and "on" or "off")
        )

    @cmd.command(name="pprefix")
    async def pprefix(self, ctx, pprefix: Optional[str] = None):
        ppfx = await self.bot.db.hget("pprefix", ctx.author.id)
        if pprefix is None and ppfx is None:
            raise cmd.BadArgument("You do not have a personal prefix.")
        if pprefix is None and ppfx is not None:
            await ctx.send(f":information_source: Your personal prefix is **{ppfx}**")
            return
        if pprefix is None:
            raise cmd.BadArgument("You should specify a prefix.")
        if len(pprefix) > 5:
            raise cmd.BadArgument("Personal prefix must be **1-5** characters.")
        await self.bot.db.hset("pprefix", ctx.author.id, pprefix)
        if pprefix == "":
            pprefix = "nothing"
        await ctx.send(f"Set **{ctx.author}**'s personal prefix to **{pprefix}**")


def setup(bot):
    cog = SettingsModule(bot)
    bot.add_cog(cog)
