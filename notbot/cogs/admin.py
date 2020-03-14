from discord.ext import tasks
from discord.ext import commands
import importlib
import os
import glob
import logging

from notbot.db import get_redis_connection, RedisConnection, Redis

from ..context import Context, Module

logger = logging.getLogger(__name__)

MODULE_NAME = "admin_module"


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


class AdminModule(commands.Cog, Module):
    def __init__(self, context: Context):
        self.bot = context.get_bot()
        self.redis_connection_module = get_redis_connection(context)
        self.redis_connection: Redis = None

    def start(self):
        self.redis_connection = self.redis_connection_module.get_connection()

    def get_name(self):
        return MODULE_NAME

    @commands.is_owner()
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

    @commands.is_owner()
    @admin.command(name="rc")
    async def admin_create_role(self, ctx):
        author = ctx.message.author
        await ctx.guild.create_role(author.server, name="role name")


def setup(bot):
    context: Context = bot.context

    admin_module = context.get_module(MODULE_NAME)
    bot.add_cog(admin_module)
