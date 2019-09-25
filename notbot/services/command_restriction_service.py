import asyncio
from notbot.context import Context, Module
from notbot.db import get_command_restriction_dao

MODULE_NAME = "command_restriction_service"


class CommandRestrictionService(Module):
    def __init__(self, context: Context):
        self.command_restriction_dao = get_command_restriction_dao(context)

    def get_name(self):
        return MODULE_NAME

    async def add_user_restriction(self, guild_id, command_name, user_id):
        await self.command_restriction_dao.add_user_restriction(
            guild_id, command_name, user_id
        )

    async def add_channel_restriction(self, guild_id, command_name, channel_id):
        await self.command_restriction_dao.add_channel_restriction(
            guild_id, command_name, channel_id
        )

    async def add_role_restriction(self, guild_id, command_name, role_id):
        await self.command_restriction_dao.add_role_restriction(
            guild_id, command_name, role_id
        )

    async def remove_user_restriction(self, guild_id, command_name, user_id):
        await self.command_restriction_dao.remove_user_restriction(
            guild_id, command_name, user_id
        )

    async def remove_channel_restriction(self, guild_id, command_name, channel_id):
        await self.command_restriction_dao.remove_channel_restriction(
            guild_id, command_name, channel_id
        )

    async def remove_role_restriction(self, guild_id, command_name, role_id):
        await self.command_restriction_dao.remove_role_restriction(
            guild_id, command_name, role_id
        )

    async def get_user_restrictions(self, guild_id, command_name):
        return await self.command_restriction_dao.get_user_restrictions(
            guild_id, command_name
        )

    async def get_channel_restrictions(self, guild_id, command_name):
        return await self.command_restriction_dao.get_channel_restrictions(
            guild_id, command_name
        )

    async def get_role_restrictions(self, guild_id, command_name):
        return await self.command_restriction_dao.get_role_restrictions(
            guild_id, command_name
        )

    async def clear_user_restrictions(self, guild_id, command_name):
        await self.command_restriction_dao.clear_user_restrictions(
            guild_id, command_name
        )

    async def clear_channel_restrictions(self, guild_id, command_name):
        await self.command_restriction_dao.clear_channel_restrictions(
            guild_id, command_name
        )

    async def clear_role_restrictions(self, guild_id, command_name):
        await self.command_restriction_dao.clear_role_restrictions(
            guild_id, command_name
        )

    async def get_all_restrictions(self, guild_id, command_name):
        user_restrictions, channel_restrictions, role_restrictions = await asyncio.gather(
            self.get_user_restrictions(guild_id, command_name),
            self.get_channel_restrictions(guild_id, command_name),
            self.get_role_restrictions(guild_id, command_name),
            return_exceptions=True,
        )

        return user_restrictions, channel_restrictions, role_restrictions

    async def clear_restrictions(self, guild_id, command_name):
        await asyncio.gather(
            self.clear_user_restrictions(guild_id, command_name),
            self.clear_channel_restrictions(guild_id, command_name),
            self.clear_role_restrictions(guild_id, command_name),
            return_exceptions=True,
        )


def get_command_restriction_service(context: Context) -> CommandRestrictionService:
    return context.get_or_register_module(
        MODULE_NAME, lambda: CommandRestrictionService(context)
    )

