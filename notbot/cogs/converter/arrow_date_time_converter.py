import arrow
from discord.ext.commands import BadArgument, Converter

from notbot.cogs.util import DATETIME_FORMAT


class ArrowDateTimeConverter(Converter):
    async def convert(self, ctx, arg):
        datetime = None
        try:
            datetime = arrow.get(arg, DATETIME_FORMAT)
        except arrow.parser.ParserError:
            raise BadArgument(
                f"Invalid datetime format. Valid format: {DATETIME_FORMAT}"
            )

        return datetime

