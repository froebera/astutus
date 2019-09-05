from discord.ext import commands as cmd
from .utils import checks, chat_formatting
import time

# import psutil
import arrow
import discord
import importlib
import os
import json
import glob
from urllib.parse import quote_plus
import aiohttp

# from utils import chat_formatting

class CogNotFoundError(Exception):
    pass


class CogLoadError(Exception):
    pass


class NoSetupError(CogLoadError):
    pass


class CogUnloadError(Exception):
    pass


class OwnerUnloadWithoutReloadError(CogUnloadError):
    pass


class UtilityModule(cmd.Cog):
    def __init__(self, bot: cmd.Bot):
        self.bot = bot

    @cmd.command()
    async def ping(self, ctx):
        msg = "It's just a song about ping pong ..."
        before = time.monotonic()
        ping_message = await ctx.send(msg)
        after = time.monotonic()
        ping = (after - before) * 1000
        try:
            await ping_message.edit(content=f"{msg} **({ping:.0f} ms)**")
        except:
            await ctx.send(f"**{ping:.0f} ms**")

    @cmd.command()
    async def invite(self, ctx, kind: str = "admin"):
        if kind.lower() not in "admin.normal":
            await ctx.send("Choose between **admin**/**normal** for bot invite links.")
            return
        await ctx.send(f"{kind.title()} link: <{getattr(self.bot, f'link_{kind}')}>")

    @cmd.command(aliases=["dictionary", "d"])
    async def define(self, ctx, word: str):
        if not word:
            return

    @cmd.command(aliases=["ud"])
    @cmd.guild_only()
    async def urban(self, ctx, *, search_terms: str):
        """Search Urban Dictionary"""

        def encode(s):
            return quote_plus(s, encoding="utf-8", errors="replace")

        search_terms = search_terms.split(" ")
        try:
            if len(search_terms) > 1:
                pos = int(search_terms[-1]) - 1
                search_terms = search_terms[:-1]
            else:
                pos = 0
            if pos not in range(0, 11):
                pos = 0
        except ValueError:
            pos = 0

        search_terms = "+".join([encode(s) for s in search_terms])
        url = "http://api.urbandictionary.com/v0/define?term=" + search_terms
        try:
            async with aiohttp.ClientSession() as cs:
                async with cs.get(url) as r:
                    result = await r.json()
            if result["list"]:

                embed = await self.bot.embed()
                embed.timestamp = arrow.get(result["list"][pos]["written_on"]).datetime
                embed.colour = 0x134FE6
                embed.title = (
                    "**"
                    + result["list"][pos]["word"]
                    + "** by "
                    + result["list"][pos]["author"]
                )
                embed.description = result["list"][pos]["definition"]
                embed.add_field(
                    name="Examples", value=result["list"][pos]["example"], inline=False
                )
                embed.add_field(
                    name="Upvotes",
                    value=f":arrow_up: {result['list'][pos]['thumbs_up']}",
                )
                embed.add_field(
                    name="Downvotes",
                    value=f":arrow_down: {result['list'][pos]['thumbs_down']}",
                )
                embed.add_field(
                    name="Definitions",
                    value=f"{pos+1} of {len(result['list'])}",
                    inline=False,
                )
                embed.add_field(
                    name="Link",
                    value="[{}]({})".format(
                        result["list"][pos]["word"], result["list"][pos]["permalink"]
                    ),
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("Your search terms gave no results.")
        except IndexError:
            await ctx.send("There is no definition #{}".format(pos + 1))

    @cmd.command(hidden=True)
    @checks.is_bot_owner()
    async def shutdown(self, ctx, when: str = None):
        await self.bot.logout()

    @cmd.command(hidden=True)
    @checks.is_bot_owner()
    async def redisclear(self, ctx, key):
        result = await self.bot.db.delete(key.format(ctx))
        await ctx.send(str(result))

    @cmd.command(hidden=True)
    @checks.is_bot_owner()
    async def importblames(self, ctx):
        with open("blames.json", "r") as fh:
            data = json.loads(fh.read())
        for user, val in data.items():
            await self.bot.db.zadd("blames", user, val)
        await ctx.send("Success!")

    @cmd.command(hidden=True)
    @checks.is_bot_owner()
    async def migratechannels(self, ctx):

        for guild in self.bot.guilds:
            starboard = await self.bot.db.hget(f"{guild.id}:set", "starboard")
            if starboard not in ("0", None):
                await self.bot.db.hset(
                    f"{guild.id}:set", "channelstarboard", int(starboard)
                )
            greetc = await self.bot.db.hget(f"{guild.id}:set", "grtc")
            if greetc not in ("0", None):
                await self.bot.db.hset(f"{guild.id}:set", "channelgreet", int(greetc))
            dptc = await self.bot.db.hget(f"{guild.id}:set", "dptc")
            if dptc not in ("0", None):
                await self.bot.db.hset(f"{guild.id}:set", "channelgoodbye", int(dptc))
        worldchats = await self.bot.db.hgetall("worldchat")
        await ctx.send("Migrating world chats...")
        for guild, worldchat in worldchats.items():
            if worldchat not in ("0", None):
                await self.bot.db.hset(
                    f"{guild}:set", "channelworldchat", int(worldchat)
                )

        await ctx.send("Success!")

    @cmd.command(name="source", aliases=["sourcecode", "github", "git"])
    async def source(self, ctx):
        await ctx.send(
            "How nice that you want to contribute! <https://github.com/froebera/notbot>"
        )

    @cmd.command(hidden=True)
    @checks.is_bot_owner()
    async def load(self, ctx: cmd.Context, *, module: str):
        if "astutus.modules" not in module:
            module = f"modules.{module}"
        try:
            self._load_cog(module)
        except CogNotFoundError:
            await ctx.send("That cog could not be found.")
        except CogLoadError:
            await ctx.send("There was an error loading the cog. Check your logs.")
        else:
            await ctx.send("loaded the cog")

    @cmd.command(hidden=True)
    @checks.is_bot_owner()
    async def reload(self, ctx: cmd.Context, *, module: str):
        if "modules" not in module:
            module = f"modules.{module}"
        try:
            self._unload_cog(module, reloading=True)
        except:
            pass

        try:
            self._load_cog(module)
        except CogNotFoundError:
            await ctx.send("That cog cannot be found.")
        except NoSetupError:
            await ctx.send("That cog does not have a setup function.")
        except CogLoadError:
            await ctx.send("There was an error reloading the cog. Check your logs.")
        else:
            await ctx.send("The cog has been reloaded.")

    def _load_cog(self, cogname):
        if not self._does_cogfile_exist(cogname):
            raise CogNotFoundError(cogname)
        try:
            mod_obj = importlib.import_module(cogname)
            importlib.reload(mod_obj)
            self.bot.load_extension(mod_obj.__name__)
        except SyntaxError as e:
            raise CogLoadError(*e.args)
        except:
            raise

    def _unload_cog(self, cogname, reloading=False):
        if not reloading and cogname == "modules.utility":
            raise OwnerUnloadWithoutReloadError(
                "Can't permanently unload the utils plugin :P"
            )
        try:
            self.bot.unload_extension(cogname)
        except:
            raise CogUnloadError

    def _list_cogs(self):
        cogs = [os.path.basename(f) for f in glob.glob("modules/*.py")]
        return ["modules." + os.path.splitext(f)[0] for f in cogs]

    def _does_cogfile_exist(self, module):
        if "modules." not in module:
            module = "modules." + module
        if module not in self._list_cogs():
            return False
        return True


def setup(bot):
    bot.add_cog(UtilityModule(bot))
