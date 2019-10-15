from notbot.context import Context, Module
from discord.ext import commands
from typing import Union
from discord import Member
from .util import create_embed

MODULE_NAME = "personal_commands_module"


class PersonalCommandsModule(commands.Cog, Module):
    def __init__(self, context: Context):
        self.bot = context.get_bot()
        self.kira = 441525718065872906

    def get_name(self):
        return MODULE_NAME

    @commands.command(name="judgement", aliases=["judge"])
    async def _judge(self, ctx, user: Union[Member]):
        if not ctx.author.id == self.kira:
            raise commands.BadArgument(
                "You do not have the power to write the death note."
            )
        if not user:
            raise commands.BadArgument("You must write a name in the death note.")
        embed = create_embed(self.bot)
        embed.description = (
            f"I am the god of the new world! {user} is now written in the death note."
        )
        embed.set_image(
            url="https://cdn.discordapp.com/attachments/478869899499012096/596230452071890964/writesinnote.gif"
        )
        await ctx.send(embed=embed)


def setup(bot):
    context: Context = bot.context

    info_module = context.get_module(MODULE_NAME)
    bot.add_cog(info_module)
