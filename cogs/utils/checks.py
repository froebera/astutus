import modules.utils.redis_connection as redis_conn
from discord.ext import commands
from .config_keys import RAID_CONFIG_KEY


def raidconfig_exists():
    async def predicate(ctx):
        res = await redis_conn.get_redis_connection().exists(
            RAID_CONFIG_KEY.format(ctx.guild.id)
        )
        if not res:
            raise commands.BadArgument(
                f"No raid configuration found. Use **{ctx.prefix}raid setup** to get started"
            )

        return res

    return commands.check(predicate)
