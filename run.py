from notbot import NOTBOT, context
import discord

intents = discord.Intents.default()
intents.members = True
bot = NOTBOT(context, intents)
bot.run()
