from discord.ext import tasks
from discord.ext import commands
from typing import Optional


class TestModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(description="test", brief="just a brief description")
    async def test(self, ctx, *message: Optional[str]):
        if message:
            await ctx.send(" ".join(message))
        else:
            await ctx.send("Hello")


def setup(bot):
    bot.add_cog(TestModule(bot))
