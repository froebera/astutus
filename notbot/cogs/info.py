from typing import Union
from discord.ext import commands
from discord import Role, Emoji, Embed, User
from .util import create_embed
from .converter import GlobalUserConverter


class InfoModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    @commands.command
    async def info(self, ctx):
        pass


def setup(bot):
    bot.add_cog(InfoModule(bot))
