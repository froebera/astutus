from discord.ext import commands
from typing import Union
import arrow
import discord


class InfoModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="rolecount",
        brief="Displays how many members have the given role",
        description="Displays how many members have the given role",
    )
    async def rolecount(self, ctx, role: Union[discord.Role]):
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
    async def rolelist(self, ctx, role: Union[discord.Role]):
        embed = discord.Embed(timestamp=arrow.utcnow().datetime)
        embed.set_footer(text=str(self.bot.user), icon_url=self.bot.user.avatar_url)
        members = role.members[0:100]
        all_members = len(role.members) == len(members)
        title = (
            "Displaying" if all_members else f"{len(members)} of {len(role.members)}"
        )
        embed.title = f"{title} members with {role} role"
        embed.colour = role.color
        embed.description = ", ".join([m.mention for m in members])
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(InfoModule(bot))
