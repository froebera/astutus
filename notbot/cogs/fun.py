from notbot.context import Context, Module
from discord.ext import commands
from typing import Set
from logging import getLogger
from random import random

MODULE_NAME = "fun_module"
logger = getLogger(__name__)


class FunModule(commands.Cog, Module):
    def __init__(self, context: Context):
        self.bot = context.get_bot()
        self.mayhem_channels: Set[int] = set()

    def get_name(self):
        return MODULE_NAME

    @commands.command(name="mayhem")
    async def mayhem(self, ctx):
        channel_id = ctx.channel.id
        mayhem_activated = channel_id in self.mayhem_channels

        if not mayhem_activated:
            try:
                await ctx.message.delete()
            except:
                await ctx.send("I cannot do that here :(")
                return

            logger.info(
                "%s started the mayhem mode in channel %s",
                ctx.author,
                f"{ctx.channel} - {ctx.channel.id}",
            )
            self.mayhem_channels.add(ctx.channel.id)
            await ctx.send(
                f"**{ctx.author.nick if ctx.author.nick else ctx.author.name}** started the mayhem mode. Lets get this party started!!"
            )
        else:
            self.mayhem_channels.discard(channel_id)
            await ctx.send("How boring of you ...")

    @commands.Cog.listener()
    async def on_message(self, message):
        if not hasattr(message, "guild"):
            return
        # why is this check required ? There should be a global check for bots
        if message.author.bot:
            return
        channel_id = message.channel.id
        if channel_id in self.mayhem_channels:
            ctx = await self.bot.get_context(message)
            if ctx.command:
                # ignore if command gets called
                return

            channel = ctx.channel
            transformed_message = self.transform_message(message.content)
            logger.info(
                "Mayhem mode active: Transformed '%s' to '%s' from %s in channel %s",
                message.content,
                transformed_message,
                message.author,
                f"{message.channel} - {message.channel.id}",
            )
            await message.delete()
            await channel.send(
                content=f"**{ctx.author.nick if ctx.author.nick else ctx.author.name}**: {transformed_message} <:spongebob_mock:639394358990209034>"
            )

    def transform_message(self, message: str) -> str:
        msgbuff = ""
        uppercount = 0
        lowercount = 0
        for c in message:
            if c.isalpha():
                if uppercount == 2:
                    uppercount = 0
                    upper = False
                    lowercount += 1
                elif lowercount == 2:
                    lowercount = 0
                    upper = True
                    uppercount += 1
                else:
                    upper = random() > 0.5
                    uppercount = uppercount + 1 if upper else 0
                    lowercount = lowercount + 1 if not upper else 0

                msgbuff += c.upper() if upper else c.lower()
            else:
                msgbuff += c

        return msgbuff


def setup(bot):
    context: Context = bot.context

    fun_module = context.get_module(MODULE_NAME)
    bot.add_cog(fun_module)
