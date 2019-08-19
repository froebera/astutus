import os
import asyncio
from better_profanity import profanity
import discord
from .redis import Redis
from .cdn import CDN


def setup_bot(bot):
    @bot.check
    async def globally_block_bots(ctx):
        return not ctx.author.bot

    @bot.check
    async def global_blacklist(ctx):
        blacklists = ctx.bot.blacklists
        return not any(
            (
                ctx.author.id in blacklists["users"],
                ctx.guild.id in blacklists["servers"],
                ctx.channel.id in blacklists["channels"],
            )
        )

    pool = Redis()
    loop = asyncio.get_event_loop()
    rds = os.environ.get("REDISCLOUD_URL", None)
    if rds is not None and rds:
        loop.run_until_complete(pool.connect_pool_url(rds))

    loop.run_until_complete(
        pool.connect_pool(
            bot.config["REDIS"]["host"],
            bot.config["REDIS"]["port"],
            pw=bot.config["REDIS"].get("password", None),
        )
    )
    bot.db = pool

    bot.cdn = None

    # bot.cdn = CDN(
    #     bot.config["CDN"]["host"],
    #     bot.config["CDN"]["space"],
    #     bot.config["CDN"]["client"],
    #     bot.config["CDN"]["secret"],
    # )
    profanity.load_censor_words()
    setattr(bot, "profanity", profanity)
