from discord.ext import commands
from db import get_queue_dao


class Queue(commands.Converter):
    async def convert(self, ctx, argument):
        queue_dao = get_queue_dao(ctx.bot.context)
        queues = await queue_dao.get_all_queues(ctx.guild.id)

        if not argument in queues:
            raise commands.BadArgument(
                f"Queue **{argument}** does not exist. Available queues: {', '.join(queues)}"
            )

        return argument
