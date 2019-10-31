from discord.ext import commands
from notbot.context import Context, Module
from typing import Optional
from notbot.cogs.util.formatter import success_message, format_user_name

from notbot.services import get_settings_service

MODULE_NAME = "settings_module"


class SettingsModule(commands.Cog, Module):
    def __init__(self, context: Context):
        self.bot = context.get_bot()
        self.settings_service = get_settings_service(context)

    def get_name(self):
        return MODULE_NAME

    @commands.command(
        name="pprefix",
        description="""
    Sets or removes the personal prefix to interact with the bot.
    If the command is called without arguments, it will display your current personal prefix instead.
    """,
        usage="[personal_prefix|unset]",
    )
    async def pprefix(self, ctx, pprefix: Optional[str] = None):
        if pprefix == "unset":
            await self.settings_service.del_pprefix(ctx.author.id)
            await ctx.send(success_message("PPrefix removed"))
            return

        pprfx = await self.settings_service.get_pprefix(ctx.author.id)
        if pprefix is None and pprfx is None:
            raise commands.BadArgument("You do not have a personal prefix.")
        if pprefix is None and pprfx is not None:
            await ctx.send(
                f":information_source: Your personal prefix is **{'nothing' if pprfx == '' else pprfx}**"
            )
            return
        if pprefix is None:
            raise commands.BadArgument("You should specify a prefix.")
        if len(pprefix) > 5:
            raise commands.BadArgument("Personal prefix must be **1-5** characters.")
        await self.settings_service.set_pprefix(ctx.author.id, pprefix)
        if pprefix == "":
            pprefix = "nothing"
        await ctx.send(
            f"Set **{format_user_name(ctx.author)}**'s personal prefix to **{pprefix}**"
        )


def setup(bot):
    context: Context = bot.context

    module = context.get_module(MODULE_NAME)
    bot.add_cog(module)
