import logging
from typing import Union
import psutil
import humanfriendly
import aiohttp
from discord.ext import commands
from discord import Role, Emoji, User, Status
from .util import create_embed
from .converter import GlobalUserConverter


logger = logging.getLogger(__name__)


class InfoModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.process = psutil.Process()

    @commands.command(
        name="rolecount",
        brief="Displays how many members have the given role",
        description="Displays how many members have the given role",
    )
    async def rolecount(self, ctx, role: Union[Role]):
        member_count = len(role.members)
        await ctx.send(
            "**{}** {} the role @**{}**".format(
                member_count, "members have" if member_count > 1 else "member has", role
            )
        )

    @commands.command(
        name="rolelist",
        brief="Displays up to 100 members of the given role",
        description="Displays up to 100 members of the given role",
    )
    async def rolelist(self, ctx, role: Union[Role]):
        embed = create_embed(ctx.bot)
        members = role.members[0:100]
        all_members = len(role.members) == len(members)
        title = (
            "Displaying" if all_members else f"{len(members)} of {len(role.members)}"
        )
        embed.title = f"{title} members with {role} role"
        embed.colour = role.color
        embed.description = ", ".join([m.mention for m in members])
        await ctx.send(embed=embed)

    @commands.command(
        name="emoji",
        aliases=["e"],
        brief="Displays a bigger version of the given emoji",
        description="Displays a bigger version of the given emoji. Does not work with Discords default emojis",
    )
    async def emoji(self, ctx, emoji: Union[Emoji]):
        e: Emoji = emoji

        id = e.id
        name = e.name
        url = f"https://cdn.discordapp.com/emojis/{id}"

        embed = create_embed(ctx.bot)
        embed.title = f"{name} emoji"
        embed.set_image(url=url)
        embed.image.width = 384
        embed.image.height = 384
        await ctx.send(embed=embed)

    @commands.command(
        name="avatar",
        aliases=["a"],
        brief="Displays a larger version of the avatar of the given user",
        description="Displays a larger version of the avatar of the given user.",
        help="""Users can be searched by ID, mention, discriminator and name
        612910410974101505
        @NOTBOT
        User#0001
        User

        NOTE: Searching a user by discriminator only works if the bot shares a guild with them
        """,
    )
    async def avatar(self, ctx, user: Union[GlobalUserConverter]):
        u: User = user

        name = u.name
        image_url = u.avatar_url_as(static_format="png", size=1024)

        embed = create_embed(ctx.bot)
        embed.title = f"**{name}**'s avatar"
        embed.set_image(url=image_url)
        await ctx.send(embed=embed)

    @commands.command(name="info")
    async def info(self, ctx: commands.Context):
        # emoji = self.bot.get_cog("TapTitansModule").emoji("elixum")
        # notbot_emoji = self.bot.emojis
        # e: Emoji = ""
        # e.name
        notbot_emoji = list(
            filter(
                lambda e: e.name == "notbot" and e.guild_id == 612910979189047325,
                self.bot.emojis,
            )
        )[0]

        embed = create_embed(self.bot)
        if notbot_emoji:
            embed.title = f"{notbot_emoji} {self.bot.user}"
            embed.set_thumbnail(url=notbot_emoji.url)

        embed.description = "Please insert coin to continue."
        embed.color = 0x473080

        embed.add_field(
            name="Author",
            value=str(self.bot.get_user(275522204559605770)),
            inline=False,
        )

        try:
            embed.add_field(
                name="Memory",
                value=humanfriendly.format_size(self.process.memory_full_info().uss),
            )
        except psutil.AccessDenied:
            logger.exception("Could not get full memory info")

        embed.add_field(
            name="CPU",
            value="{:.2f}%".format(self.process.cpu_percent() / psutil.cpu_count()),
        )

        total_members = sum(1 for _ in self.bot.get_all_members())
        total_online = len(
            {m.id for m in self.bot.get_all_members() if m.status is not Status.offline}
        )
        total_unique = len(self.bot.users)
        embed.add_field(name="Guilds", value=len(self.bot.guilds))
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

    @commands.command(
        name="issues",
        aliases=["todos"],
        brief="Displays a list of all open github issues",
        description="Displays a list of all open github issues",
    )
    async def issues(self, ctx):
        embed = create_embed(self.bot)
        embed.title = "Currently open issues:"
        embed.colour = 0xFF0000
        async with aiohttp.ClientSession() as client:
            async with client.get(
                "https://api.github.com/repos/froebera/notbot/issues"
            ) as resp:
                res = await resp.json()
                for issue in res:
                    issue_title = issue["title"]
                    issue_body = issue.get("body", "<>")
                    if not issue_body:
                        issue_body = "<>"
                    embed.add_field(name=issue_title, value=issue_body, inline=False)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(InfoModule(bot))
