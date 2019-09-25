from notbot.context import Context, Module
from notbot.db import get_redis_connection
from notbot.cogs.util import (
    CMD_RESTRICTIONS_CHANNEL,
    CMD_RESTRICTIONS_ROLE,
    CMD_RESTRICTIONS_USER,
)
from .redis import Redis

MODULE_NAME = "command_restriction_dao"


class CommandRestrictionDao(Module):
    def __init__(self, context: Context):
        self.redis_connection_module = get_redis_connection(context)
        self.connection: Redis = None

    def start(self):
        self.connection = self.redis_connection_module.get_connection()

    def get_name(self):
        return MODULE_NAME

    async def add_user_restriction(self, guild_id, command_name, user_id):
        await self.connection.sadd(
            CMD_RESTRICTIONS_USER.format(guild_id, command_name), user_id
        )

    async def add_channel_restriction(self, guild_id, command_name, channel_id):
        await self.connection.sadd(
            CMD_RESTRICTIONS_CHANNEL.format(guild_id, command_name), channel_id
        )

    async def add_role_restriction(self, guild_id, command_name, role_id):
        await self.connection.sadd(
            CMD_RESTRICTIONS_ROLE.format(guild_id, command_name), role_id
        )

    async def remove_user_restriction(self, guild_id, command_name, user_id):
        await self.connection.srem(
            CMD_RESTRICTIONS_USER.format(guild_id, command_name), user_id
        )

    async def remove_channel_restriction(self, guild_id, command_name, channel_id):
        await self.connection.srem(
            CMD_RESTRICTIONS_CHANNEL.format(guild_id, command_name), channel_id
        )

    async def remove_role_restriction(self, guild_id, command_name, role_id):
        await self.connection.srem(
            CMD_RESTRICTIONS_ROLE.format(guild_id, command_name), role_id
        )

    async def get_user_restrictions(self, guild_id, command_name):
        return await self.connection.smembers(
            CMD_RESTRICTIONS_USER.format(guild_id, command_name)
        )

    async def get_channel_restrictions(self, guild_id, command_name):
        return await self.connection.smembers(
            CMD_RESTRICTIONS_CHANNEL.format(guild_id, command_name)
        )

    async def get_role_restrictions(self, guild_id, command_name):
        return await self.connection.smembers(
            CMD_RESTRICTIONS_ROLE.format(guild_id, command_name)
        )

    async def clear_user_restrictions(self, guild_id, command_name):
        await self.connection.delete(
            CMD_RESTRICTIONS_USER.format(guild_id, command_name)
        )

    async def clear_channel_restrictions(self, guild_id, command_name):
        await self.connection.delete(
            CMD_RESTRICTIONS_CHANNEL.format(guild_id, command_name)
        )

    async def clear_role_restrictions(self, guild_id, command_name):
        await self.connection.delete(
            CMD_RESTRICTIONS_ROLE.format(guild_id, command_name)
        )


def get_command_restriction_dao(context: Context) -> CommandRestrictionDao:
    return context.get_or_register_module(
        MODULE_NAME, lambda: CommandRestrictionDao(context)
    )

