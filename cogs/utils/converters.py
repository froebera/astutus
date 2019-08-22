import modules.utils.redis_connection as redis_conn
from discord.ext import commands


class Queue(commands.Converter):
    async def convert(self, ctx, argument):
        print(f"converter {argument}")
        queues = await redis_conn.get_redis_connection().lrange(
            f"raid:{ctx.guild.id}:queues"
        )
        if not argument in queues:
            print("raising exception")
            raise commands.BadArgument(
                f"Queue **{argument}** does not exist. Available queues: {', '.join(queues)}"
            )

        return argument
