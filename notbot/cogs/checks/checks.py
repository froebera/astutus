from discord.ext import commands
from notbot.db import RaidDao, get_raid_dao
import asyncio


async def raidconfig_exists(ctx):
    raid_dao = get_raid_dao(ctx.bot.context)
    res = await raid_dao.raid_config_exists(ctx.guild.id)

    if not res:
        raise commands.BadArgument(
            f"No raid configuration found. Use **{ctx.prefix}raid setup** to get started"
        )

    return res


async def has_raid_management_permissions(ctx):
    raid_dao = get_raid_dao(ctx.bot.context)

    is_owner = await ctx.bot.is_owner(ctx.author)
    if is_owner:
        return True

    raid_management_roles = await raid_dao.get_raid_management_roles(ctx.guild.id)

    if not raid_management_roles:
        return True

    # roles = raid_management_roles.split()
    roles = [int(role) for role in raid_management_roles.split()]
    user_roles = [r.id for r in ctx.author.roles]
    res = bool(next((role for role in roles if role in user_roles), None))

    if res:
        return True

    # return bool(next((role for role in roles if role in ctx.author.roles), None))

    raise commands.BadArgument("You dont have the permission to manage raids")


async def has_raid_timer_permissions(ctx):
    raid_dao = get_raid_dao(ctx.bot.context)
    is_owner = await ctx.bot.is_owner(ctx.author)
    if is_owner:
        return True

    # raid_configuration = await get_redis_connection().hgetall(
    #     RAID_CONFIG_KEY.format(ctx.guild.id)
    # )

    raid_management_roles, raid_timer_roles = await asyncio.gather(
        raid_dao.get_raid_management_roles(ctx.guild.id),
        raid_dao.get_raid_timer_roles(ctx.guild.id),
        return_exceptions=True,
    )

    if not raid_management_roles and not raid_timer_roles:
        return True

    management_roles = [int(role) for role in raid_management_roles.split()]
    timer_roles = [int(role) for role in raid_management_roles.split()]

    roles = list(set(management_roles + timer_roles))

    # roles = raid_management_roles.split()
    roles = [int(role) for role in raid_management_roles.split()]
    user_roles = [r.id for r in ctx.author.roles]
    res = bool(next((role for role in roles if role in user_roles), None))

    if res:
        return True

    # return bool(next((role for role in roles if role in ctx.author.roles), None))

    raise commands.BadArgument("You dont have the permission to manage timers")


async def is_mod(ctx: commands.Context):
    return await check_guild_permissions(ctx, {"ban_members": True})


async def check_guild_permissions(
    ctx: commands.Context, permissions: dict, *, check=all
):
    is_owner = await ctx.bot.is_owner(ctx.author)
    if is_owner:
        return True
    if ctx.guild is None:
        return False
    resolved = ctx.author.guild_permissions
    result = check(
        getattr(resolved, name, None) == value for name, value in permissions.items()
    )
    if result:
        return result
    else:
        await ctx.send(
            f"Sorry **{ctx.author}**, you do not have sufficient permissions to use this command."
        )
