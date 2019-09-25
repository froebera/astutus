from typing import Union
import logging

from discord.ext import commands
from discord import TextChannel, Member, Role
from discord.utils import get

from notbot.context import Module, Context
from notbot.services import get_command_restriction_service
from .util import create_embed

MODULE_NAME = "restriction_module"

logger = logging.getLogger(__name__)


class RestrictionModule(commands.Cog, Module):
    def __init__(self, context: Context):
        self.command_restriction_service = get_command_restriction_service(context)

    def get_name(self):
        return MODULE_NAME

    @commands.group(name="restrictions", invoke_without_command=True)
    async def restrictions(self, ctx, command):
        cmd = ctx.bot.get_command(command)
        if not cmd:
            raise commands.BadArgument(f"Could not find command {command}")

        logger.debug("Listing restrictions for command '%s'", cmd)

        user_res, channel_res, role_res = await self.command_restriction_service.get_all_restrictions(
            ctx.guild.id, cmd
        )

        if not user_res and not channel_res and not role_res:
            raise commands.BadArgument(f"Command **{cmd}** is not restricted")

        channel_restrictions = [get(ctx.guild.channels, id=int(c)) for c in channel_res]
        role_restrictions = [get(ctx.guild.roles, id=int(c)) for c in role_res]
        user_restrictions = [get(ctx.guild.members, id=int(c)) for c in user_res]

        logger.debug("user restrictions: %s", user_restrictions)
        logger.debug("channel restrictions: %s", channel_restrictions)
        logger.debug("role restrictions: %s", role_restrictions)

        embed = create_embed(ctx.bot)
        embed.title = f"Restrictions for command **{cmd}**"

        if user_restrictions:
            embed.add_field(
                name="Permitted Users",
                value=", ".join([user.mention for user in user_restrictions]),
            )
        if channel_restrictions:
            embed.add_field(
                name="Allowed Channels",
                value=", ".join([channel.mention for channel in channel_restrictions]),
            )
        if role_restrictions:
            embed.add_field(
                name="Permitted Roles",
                value=", ".join([role.mention for role in role_restrictions]),
            )

        embed.colour = 0xED133F

        await ctx.send(embed=embed)

    @restrictions.command(name="add")
    async def restrictions_add(
        self,
        ctx,
        command,
        *objects: Union[
            commands.TextChannelConverter,
            commands.RoleConverter,
            commands.MemberConverter,
        ],
    ):
        cmd = ctx.bot.get_command(command)
        logger.debug("Adding restrictions for command %s", cmd)

        if not cmd:
            raise commands.BadArgument(f"Could not find command {command}")

        for o in objects:
            if isinstance(o, TextChannel):
                await self.command_restriction_service.add_channel_restriction(
                    ctx.guild.id, cmd, o.id
                )
            elif isinstance(o, Member):
                await self.command_restriction_service.add_user_restriction(
                    ctx.guild.id, cmd, o.id
                )
            elif isinstance(o, Role):
                await self.command_restriction_service.add_role_restriction(
                    ctx.guild.id, cmd, o.id
                )

        await ctx.send(
            ":white_check_mark: Added **{}** restriction{} to {}".format(
                len(objects), "s" if len(objects) > 1 else "", cmd
            )
        )

    @restrictions.command(name="remove")
    async def restrictions_remove(
        self,
        ctx,
        command,
        *objects: Union[
            commands.TextChannelConverter,
            commands.RoleConverter,
            commands.MemberConverter,
        ],
    ):
        cmd = ctx.bot.get_command(command)
        logger.debug("Removing restrictions for command %s", cmd)

        for o in objects:
            if isinstance(o, TextChannel):
                await self.command_restriction_service.remove_channel_restriction(
                    ctx.guild.id, cmd, o.id
                )
            elif isinstance(o, Member):
                await self.command_restriction_service.remove_user_restriction(
                    ctx.guild.id, cmd, o.id
                )
            elif isinstance(o, Role):
                await self.command_restriction_service.remove_role_restriction(
                    ctx.guild.id, cmd, o.id
                )

        await ctx.send(
            ":white_check_mark: Removed **{}** restriction{} from {}".format(
                len(objects), "s" if len(objects) > 1 else "", cmd
            )
        )

    @restrictions.command(name="clear")
    async def restrictions_clear(self, ctx, command):
        cmd = ctx.bot.get_command(command)
        logger.debug("Clearing restrictions for command %s", cmd)

        await self.command_restriction_service.clear_restrictions(ctx.guild.id, cmd)

        await ctx.send(f":white_check_mark: Cleared all restrictions for command {cmd}")


def setup(bot):
    context: Context = bot.context

    module = context.get_module(MODULE_NAME)
    bot.add_cog(module)
