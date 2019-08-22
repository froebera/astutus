from discord.ext import commands
import discord


class HelpModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="help",
        description="The help command!",
        aliases=["commands", "command"],
        usage="cog",
    )
    async def help_command(self, ctx, cog="all"):

        # The third parameter comes into play when
        # only one word argument has to be passed by the user

        # Prepare the embed

        # color_list = [c for c in colors.values()]
        help_embed = discord.Embed(title="Help", color=int("0x186281", 16))
        help_embed.set_thumbnail(url=self.bot.user.avatar_url)
        help_embed.set_footer(
            text=f"Requested by {ctx.message.author.name}",
            icon_url=self.bot.user.avatar_url,
        )

        # Get a list of all cogs
        cogs = [c for c in self.bot.cogs.keys()]

        # If cog is not specified by the user, we list all cogs and commands

        if cog == "all":
            for cog in cogs:
                # Get a list of all commands under each cog

                cog_commands = self.bot.get_cog(cog).get_commands()
                commands_list = ""
                for comm in cog_commands:
                    commands_list += f"**{comm.name}** - *{comm.description}*\n"

                # Add the cog's details to the embed.

                help_embed.add_field(
                    name=cog, value=commands_list, inline=False
                ).add_field(name="\u200b", value="\u200b", inline=False)

                # Also added a blank field '\u200b' is a whitespace character.
            pass
        else:

            # If the cog was specified

            lower_cogs = [c.lower() for c in cogs]

            # If the cog actually exists.
            if cog.lower() in lower_cogs:

                # Get a list of all commands in the specified cog
                commands_list = self.bot.get_cog(
                    cogs[lower_cogs.index(cog.lower())]
                ).get_commands()
                help_text = ""

                # Add details of each command to the help text
                # Command Name
                # Description
                # [Aliases]
                #
                # Format
                for command in commands_list:
                    help_text += (
                        f"```{command.name}```\n" f"**{command.description}**\n\n"
                    )

                    # Also add aliases, if there are any
                    if len(command.aliases) > 0:
                        help_text += (
                            f'**Aliases :** `{"`, `".join(command.aliases)}`\n\n\n'
                        )
                    else:
                        # Add a newline character to keep it pretty
                        # That IS the whole purpose of custom help
                        help_text += "\n"

                    # Finally the format
                    help_text += (
                        f"Format: `@{self.bot.user.name}#{self.bot.user.discriminator}"
                        f' {command.name} {command.usage if command.usage is not None else ""}`\n\n\n\n'
                    )

                help_embed.description = help_text
            else:
                # Notify the user of invalid cog and finish the command
                await ctx.send(
                    "Invalid cog specified.\nUse `help` command to list all cogs."
                )
                return

        await ctx.send(embed=help_embed)

        return


def setup(bot):
    bot.add_cog(HelpModule(bot))
