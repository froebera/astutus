from datetime import timedelta
from discord.ext import commands as cmd
import re
import arrow


# COMPILED = re.compile(
#     r"(?:(?P<years>[0-9])(?:years?|y))?"
#     r"(?:(?P<months>[0-9])(?:months?|mo))?"
#     r"(?:(?P<weeks>[0-9])(?:weeks?|w))?"
#     r"(?:(?P<days>[0-9])(?:days?|d))?"
#     r"(?:(?P<hours>[0-9])(?:hours?|h))?"
#     r"(?:(?P<minutes>[0-9])(?:minutes?|m))?"
#     r"(?:(?P<seconds>[0-9])(?:seconds?|s))?",
#     re.VERBOSE,
# )

COMPILED = re.compile(
    r"(?:(?P<years>\d{1,2}){0,1}(?=[y: ]{0,2})(?<=\d)[y ]+)?"
    r"(?:(?P<weeks>\d{1,2}){0,1}(?=[w: ]{0,2})(?<=\d)[w ]+)?"
    r"(?:(?P<days>\d{1,2}){0,1}(?=[d: ]{0,2})(?<=\d)[d ]+)?"
    r"(?:(?P<hours>\d{1,2}){0,1}(?=[h: ]{0,2})(?<=\d)[h :]+)?"
    r"(?:(?P<minutes>\d{1,2}){0,1}(?=[m: ]{0,2})(?<=\d)[m :]+)?"
    r"(?:(?P<seconds>\d{1,2}){0,1}(?=[s: ]{0,2})(?<=\d)[s :]{0,2})?",
    re.VERBOSE,
)


async def convert(argument):
    match = COMPILED.match(argument.strip())
    data = {key: value and int(value) or 0 for key, value in match.groupdict().items()}
    now = arrow.utcnow()
    res = now.shift(**data)
    return res


class Duration(cmd.Converter):
    async def convert(self, ctx: cmd.Context, argument):
        if not COMPILED.match(argument.strip()).group(0):
            raise cmd.BadArgument("bad time")
        res = await convert(argument)
        return res


def get_hms(delta: timedelta):
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 60 * 60)
    minutes, seconds = divmod(remainder, 60)
    return hours, minutes, seconds


def get_dhms(delta: timedelta):
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return days, hours, minutes, seconds

