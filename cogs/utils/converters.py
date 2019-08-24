from .redis_connection import get_redis_connection
from discord.ext import commands


class Queue(commands.Converter):
    async def convert(self, ctx, argument):
        queues = await get_redis_connection().lrange(f"raid:{ctx.guild.id}:queues")
        if not argument in queues:
            raise commands.BadArgument(
                f"Queue **{argument}** does not exist. Available queues: {', '.join(queues)}"
            )

        return argument
