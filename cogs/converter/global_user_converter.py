from discord.ext.commands import IDConverter, BadArgument
import discord
import re


class GlobalUserConverter(IDConverter):
    async def convert(self, ctx, argument):
        state = ctx._state
        match = self._get_id_match(argument) or re.match(r"<@!?([0-9]+)>$", argument)

        if match is not None:
            user_id = int(match.group(1))
            result = ctx.bot.get_user(user_id)
            # if user does not exist in global cache, try fetching from discord api
            if result is None:
                try:
                    result = await ctx.bot.fetch_user(user_id)
                except (discord.NotFound, discord.HTTPException):
                    result = None
        else:
            arg = argument
            # check for discriminator if it exists
            if len(arg) > 5 and arg[-5] == "#":
                discrim = arg[-4:]
                name = arg[:-5]
                predicate = lambda u: u.name == name and u.discriminator == discrim
                result = discord.utils.find(predicate, state._users.values())
                if result is not None:
                    return result

            predicate = lambda u: u.name == arg
            result = discord.utils.find(predicate, state._users.values())

        if result is None:
            raise BadArgument('User "{}" not found'.format(argument))
        return result
