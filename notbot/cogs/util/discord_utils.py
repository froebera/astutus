import discord
import arrow


def create_embed(bot):
    embeded = discord.Embed(timestamp=arrow.utcnow().datetime)
    embeded.set_footer(text=str(bot.user), icon_url=bot.user.avatar_url)

    return embeded
