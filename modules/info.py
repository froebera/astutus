import aiohttp
from discord.ext import commands as cmd
from discord.utils import get
import psutil
import arrow
import discord
from .utils.converters import MemberID
from .utils.etc import download_image
from .utils.discord_search import choose_item
import humanfriendly
import mimetypes
import re

EMOJI = re.compile(r"^<a?:\w+:\d+>$")


class InfoModule(cmd.Cog):
    """Find information on the bot, users, and other things, like if the bot has a custom prefix set."""

    def __init__(self, bot: cmd.Bot):
        self.bot = bot
        self.process = psutil.Process()

    async def get_or_upload_avatar(self, ctx, user):
        if user is None:
            user = ctx.author.id
        user = await self.bot.fetch_user(user)
        cached = await self.bot.db.hget("avatar_cache", user.id)
        if not cached or cached is None:
            url = user.avatar_url_as(static_format="png", size=1024)
            urls = str(url).split("/")[-1].split("?")[0]
            ctype, _ = mimetypes.guess_type(urls)
            ext = ctype.split("/")[-1]
            i = await self.bot.cdn.upload_file("u", user.id, url, ext, ctype)
            await self.bot.db.hset("avatar_cache", user.id, i)
            cached = i
        return cached, user

    async def get_or_upload_guildicon(self, guild):
        cached = await self.bot.db.hget("guild_cache", guild.id)
        if not cached or cached is None:
            url = guild.icon_url_as(static_format="png", size=1024)
            urls = str(url).split("/")[-1].split("?")[0]
            ctype, _ = mimetypes.guess_type(urls)
            ext = ctype.split("/")[-1]
            i = await self.bot.cdn.upload_file("g", guild.id, url, ext, ctype)
            await self.bot.db.hset("guild_cache", guild.id, i)
            cached = i
        print(cached)
        return cached

    @cmd.command(name="emoji", aliases=["e"])
    async def emoji(self, ctx, emoji):
        if not EMOJI.match(emoji):
            raise cmd.BadArgument("Invalid emoji!")
        split = emoji.replace(">", "").replace("<", "").split(":")
        animate, name, id = split
        url = f"https://cdn.discordapp.com/emojis/{id}"
        cached = await self.bot.db.hget("emoji_cache", f"{name}_{id}")
        if not cached or cached is None:
            mimetype = "image/gif" if animate else "image/png"
            ext = "gif" if animate else "png"
            url = f"{url}.{ext}"
            async with aiohttp.ClientSession() as cs:
                async with cs.get(url) as r:
                    i = await self.bot.cdn.upload_file("e", id, r, ext, mimetype)
            cached = i
            await self.bot.db.hset("emoji_cache", f"{name}_{id}", i)

        embed = await self.bot.embed()
        embed.title = f"{name} emoji"
        embed.set_image(url=cached)
        embed.image.width = 384
        embed.image.height = 384
        edict = embed.to_dict()
        del edict["timestamp"]
        embed = discord.Embed().from_dict(edict)
        await ctx.send(embed=embed)

    @cmd.command(name="guildicon", aliases=["servericon", "icon"])
    @cmd.cooldown(1, 30, cmd.BucketType.user)
    async def guildicon(self, ctx):
        cached = await self.get_or_upload_guildicon(ctx.guild)
        async with ctx.typing():
            embed = discord.Embed(title=f"**{ctx.guild}** icon")
            embed.set_image(url=cached)
            await ctx.send(embed=embed)

    @cmd.command()
    @cmd.cooldown(1, 30, cmd.BucketType.user)
    async def avatar(self, ctx, *user):
        if user:
            user = await choose_item(ctx, "member", ctx.guild, " ".join(user).lower())
        else:
            user = ctx.author
        cached, user = await self.get_or_upload_avatar(ctx, user.id)
        async with ctx.typing():
            embed = discord.Embed(title=f"**{user}**'s avatar")
            embed.set_image(url=cached)
            await ctx.send(embed=embed)

    @cmd.command()
    async def prefix(self, ctx):
        "Show's the bot's current prefix for this guild."
        cstm = await self.bot.db.hget(f"{ctx.guild.id}:set", "pfx")
        if not cstm or cstm is None:
            cstm = ""
        await ctx.send(
            "You can summon me with: **{}**{}".format(
                self.bot.config["DEFAULT"]["prefix"], cstm and f" or **{cstm}**" or ""
            )
        )

    @cmd.command(name="support")
    async def support(self, ctx):
        embed = await self.bot.embed()
        guild = self.bot.get_guild(440785686438871040)
        cached = await self.get_or_upload_guildicon(guild)
        embed.set_thumbnail(url=cached)
        embed.title = f"{ctx.guild.me} Support Server"
        embed.description = (
            "[Click here to go to the support server](https://discord.gg/WvcryZW)"
        )
        embed.color = 0x473080
        await ctx.send(embed=embed)

    @cmd.command(name="patreon", aliases=["donate", "fund", "gofundme"])
    async def patreon(self, ctx):
        embed = await self.bot.embed()
        # guild = self.bot.get_guild(440785686438871040)
        cached, _ = await self.get_or_upload_avatar(ctx, 216303189073461248)
        embed.set_thumbnail(url=cached)
        embed.title = f"{ctx.guild.me} Patreon"
        embed.description = (
            "[Click here to support the bot!](https://patreon.com/lxmcneill)"
        )
        embed.color = 0xF86754
        await ctx.send(embed=embed)

    @cmd.command(name="rolecount")
    async def rolecount(self, ctx, *role_search):
        if role_search:
            role_search = await choose_item(
                ctx, "role", ctx.guild, " ".join(role_search).lower()
            )
        else:
            raise cmd.BadArgument(
                "No role given! Use **{}roles** to see existing roles.".format(
                    ctx.prefix
                )
            )
        member_count = len(role_search.members)
        plural = "s" if member_count != 1 else ""
        await ctx.send(
            "**{}** member{} {} the role @**{}**!".format(
                member_count, plural, "has" if not plural else "have", role_search
            )
        )
        return role_search

    @cmd.command(name="rolelist")
    async def rolelist(self, ctx, *role_search):
        if role_search:
            role_search = await choose_item(
                ctx, "role", ctx.guild, " ".join(role_search).lower()
            )
        else:
            raise cmd.BadArgument(
                "No role given! Use **{}roles** to see existing roles.".format(
                    ctx.prefix
                )
            )
        embed = await self.bot.embed()
        members = role_search.members[0:100]
        # if len(role_search.members) > 100:
        show = len(role_search.members) == len(members)
        show = "Displaying" if show else f"{len(members)} of {len(role_search.members)}"
        embed.title = f"{show} members with {role_search} role"
        embed.color = role_search.color
        embed.description = ", ".join([m.mention for m in members])
        await ctx.send(embed=embed)

    @cmd.group(name="info", invoke_without_command=True, aliases=["i"])
    async def info(self, ctx):
        return

    @info.command(name="role", aliases=["roles"])
    async def roles(self, ctx, *role_search):
        embed = await self.bot.embed()
        if not role_search:
            roles = ", ".join([r.mention for r in ctx.guild.roles])
            embed.description = roles
            await ctx.send(embed=embed)
            return
        if role_search:
            role_search = " ".join(role_search).lower()
            role_search = await choose_item(ctx, "role", ctx.guild, role_search)
        else:
            raise cmd.BadArgument(
                "No role given! Use **{}roles** to see existing roles.".format(
                    ctx.prefix
                )
            )
        embed.color = role_search.color
        embed.description = f"Information about {role_search.mention} role"
        embed.add_field(name="ID", value=role_search.id)

        days = (ctx.message.created_at - role_search.created_at).days
        plural = "s" if days != 1 else ""
        embed.add_field(name="Created", value=f"**{days}** day{plural} ago")
        embed.add_field(name="Integration", value=role_search.managed)
        embed.add_field(name="Displayed Separately", value=role_search.hoist)
        embed.add_field(name="Pingable", value=role_search.mentionable)
        embed.add_field(
            name="Position", value=ctx.guild.roles[::-1].index(role_search) + 1
        )
        count = len(role_search.members)
        online = len(
            [m for m in role_search.members if m.status != discord.Status.offline]
        )
        embed.add_field(name="Members", value=f"{online} / {count} online")
        await ctx.send(embed=embed)

    @info.command(name="user", aliases=["member"])
    @cmd.guild_only()
    async def info_user(self, ctx, *user):
        if user:
            user = await choose_item(ctx, "member", ctx.guild, " ".join(user).lower())
        else:
            user = ctx.author
        cached, user = await self.get_or_upload_avatar(ctx, user.id)
        member = ctx.guild.get_member(user.id)
        embed = None
        title = f"Information about {user}"
        embed = await self.bot.embed()
        embed.title = title
        if member is not None:
            embed.description = f"Member of {ctx.guild}"
            embed.color = member.color
        else:
            embed.description = f"Not a member of {ctx.guild}"
        embed.add_field(name="User ID", value=user.id)
        created = (ctx.message.created_at - user.created_at).days
        plural = "s" if created != 1 else ""
        embed.add_field(name="Born", value=f"**{created}** day{plural} ago")
        if member is not None:

            joined = (ctx.message.created_at - member.joined_at).days
            plural = "s" if joined != 1 else ""
            embed.add_field(name="Joined", value=f"**{joined}** day{plural} ago")

            roles = [x.mention for x in member.roles if x.name != "@everyone"]
            plural = "s" if len(roles) != 1 else ""
            embed.add_field(
                name=f"Role{plural}",
                value=", ".join(roles) if roles else "None.",
                inline=False,
            )
            warnings = await self.bot.db.zscore(f"{ctx.guild.id}:wrncnt", user.id)
            if warnings is not None:
                warnings = int(warnings)
                if warnings:
                    embed.add_field(name=f"Warnings", value=warnings)
        else:
            embed.description = "Not a member of the server."
        embed.set_thumbnail(url=cached)
        await ctx.send(embed=embed)

    @info.command(name="bot")
    @cmd.guild_only()
    async def info_bot(self, ctx: cmd.Context):
        "Get information about the bot!"
        emoji = self.bot.get_cog("TapTitansModule").emoji("elixum")
        embed = await self.bot.embed()
        embed.title = f"{emoji} {self.bot.user}"
        embed.description = "Please insert coin to continue."
        embed.color = 0x473080
        # )
        embed.set_thumbnail(url=emoji.url)
        embed.add_field(
            name="Author",
            value=str(self.bot.get_user(305879281580638228)),
            inline=False,
        )
        embed.add_field(
            name="Memory",
            value=humanfriendly.format_size(self.process.memory_full_info().uss),
        )
        embed.add_field(
            name="CPU",
            value="{:.2f}%".format(self.process.cpu_percent() / psutil.cpu_count()),
        )
        total_members = sum(1 for _ in self.bot.get_all_members())
        total_online = len(
            {
                m.id
                for m in self.bot.get_all_members()
                if m.status is not discord.Status.offline
            }
        )
        total_unique = len(self.bot.users)
        embed.add_field(name="Guilds", value=len(self.bot.guilds))
        prem = await self.bot.db.hgetall("premium")
        embed.add_field(name="Premium Servers", value=len(prem))
        text_channels = []
        voice_channels = []
        for guild in self.bot.guilds:
            voice_channels.extend(guild.voice_channels)
            text_channels.extend(guild.text_channels)

        text = len(text_channels)
        voice = len(voice_channels)
        embed.add_field(
            name="Channels",
            value=f"{text + voice:,} total - {text:,} text - {voice:,} voice",
        )
        embed.add_field(
            name="Members",
            value=f"{total_members} total - {total_unique} unique - {total_online} online",
            inline=False,
        )
        await ctx.send(embed=embed)

    @info.command(name="db")
    @cmd.guild_only()
    async def info_db(self, ctx: cmd.Context):
        embed = discord.Embed()
        size = await self.bot.db.size()
        embed.add_field(name="Keys", value=size)
        # await ctx.send(f"Current database size: **{size}**")
        memory = (await self.bot.db.info()).splitlines()
        memory = next((m for m in memory if m.startswith("used_memory_human:")), None)
        if memory:
            _, result = memory.split(":")
            embed.add_field(name="Size", value=result)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(InfoModule(bot))
