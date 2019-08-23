from .redis_connection import get_redis_connection
from discord.ext import commands
from .config_keys import RAID_CONFIG_KEY, RAID_MANAGEMENT_ROLES, RAID_TIMER_ROLES


def raidconfig_exists():
    async def predicate(ctx):
        res = await get_redis_connection().exists(RAID_CONFIG_KEY.format(ctx.guild.id))
        if not res:
            raise commands.BadArgument(
                f"No raid configuration found. Use **{ctx.prefix}raid setup** to get started"
            )

        return res

    return commands.check(predicate)


def has_raid_management_permissions():
    async def predicate(ctx):
        raid_management_roles = await get_redis_connection().hget(
            RAID_CONFIG_KEY.format(ctx.guild.id), RAID_MANAGEMENT_ROLES
        )

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

    return commands.check(predicate)


def has_raid_timer_permissions():
    async def predicate(ctx):
        raid_configuration = await get_redis_connection().hgetall(
            RAID_CONFIG_KEY.format(ctx.guild.id)
        )

        raid_management_roles = raid_configuration.get(RAID_MANAGEMENT_ROLES, "")
        raid_timer_roles = raid_configuration.get(RAID_TIMER_ROLES, "")

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

    return commands.check(predicate)


def is_mod():
    async def predicate(ctx: commands.Context):
        return await check_guild_permissions(ctx, {"ban_members": True})

    return commands.check(predicate)


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
