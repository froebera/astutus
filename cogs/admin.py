from discord.ext import tasks
from discord.ext import commands

from db import get_redis_connection

class AdminModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.redis_connection = get_redis_connection(self.bot.context).get_connection()

    @commands.group(name="admin")
    async def admin(self, ctx):
        pass

    @admin.group(name="redis")
    async def redis(self, ctx):
        pass
    
    @commands.is_owner()
    @redis.command(name="lrem")
    async def redis_lrem(self, ctx, redis_key, value):
        key_exists = await self.redis_connection.exists(redis_key)
        if not key_exists:
            await ctx.send("Key does not exist")
            return
        return await self.redis_connection.lrem(redis_key, value)

def setup(bot):
    bot.add_cog(AdminModule(bot))