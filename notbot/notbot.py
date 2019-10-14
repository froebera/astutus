import logging
import contextvars
from contextvars import ContextVar
import traceback
import discord
from discord.ext import commands
from discord.utils import get
from .services import get_config_service, get_command_restriction_service
from .context import Context
import arrow
from datetime import timedelta
from .cogs.util import create_embed

extension_prefix = "notbot."
extensions = [
    "cogs.raid",
    "cogs.info",
    "cogs.admin",
    "cogs.efficiency",
    "cogs.restriction",
    "cogs.raid_stats",
]

logger = logging.getLogger(__name__)

command_execution_start: ContextVar[arrow.Arrow] = ContextVar("command_execution_start")


async def prefix_callable(bot, message) -> list:
    user_id = bot.user.id
    prefix_base = [f"<@!{user_id}> ", f"<@{user_id}> "]
    if message.guild is not None:
        prefix_base.append(bot.default_prefix)
    #     custom = await bot.db.hget(f"{message.guild.id}:set", "pfx")
    #     if custom or custom is not None:
    #         prefix_base.append(custom)
    #     pprefix_enabled = await bot.db.hget(f"{message.guild.id}:toggle", "pprefix")
    #     if pprefix_enabled is not None and pprefix_enabled != "0":
    #         pprefix = await bot.db.hget("pprefix", message.author.id)
    #         if pprefix is not None:
    #             prefix_base.append(pprefix)
    return prefix_base
    # return "?"


class NOTBOT(commands.AutoShardedBot):
    def __init__(self, ctx: Context):
        super().__init__(
            command_prefix=prefix_callable,
            description="",
            pm_help=None,
            fetch_offline_members=True,
        )
        self.before_invoke(self._before_invoke_callback)
        self.after_invoke(self._after_invoke_callback)

        self.context: Context = ctx
        self.context.set_bot(self)
        self.context.start()
        config_service = get_config_service(ctx)
        self.command_restriction_service = get_command_restriction_service(ctx)
        self.default_prefix: str = config_service.get_config("DEFAULT")["prefix"]
        # self.remove_command("help")
        for extension in extensions:
            e = extension_prefix + extension
            try:
                logger.info("Loading cog %s", e)
                self.load_extension(e)
            except (discord.ClientException):
                logger.error("Failed to load cog %s", e)

    async def on_ready(self):
        logger.info("Ready: %s (ID: %s)", self.user, self.user.id)

    async def on_message(self, message: discord.Message):
        """
        global on message hook to route all command calls to process_commands
        """
        await self.process_commands(message)

    async def process_commands(self, message: discord.Message):
        """
        global handler to process all commands

        checks for channel/guild/user permissions before executing any commanc
        """
        ctx = await self.get_context(message)
        if ctx.command is None:
            return

        command_name = self.get_full_name_for_called_command(ctx)
        logger.debug("Full command name: %s", command_name)

        cmd_name = command_name
        inherited = False

        user_res = None
        channel_res = None
        role_res = None

        # Loop over all parent commands, until any restrictions are found
        # Ingores higher level restrictions if any restriction is set
        user_res, channel_res, role_res = await self.command_restriction_service.get_all_restrictions(
            ctx.guild.id, cmd_name
        )

        while not user_res and not channel_res and not role_res:
            pref, _, _ = cmd_name.rpartition(" ")
            if pref:
                cmd_name = pref
                inherited = True
            else:
                break
            user_res, channel_res, role_res = await self.command_restriction_service.get_all_restrictions(
                ctx.guild.id, cmd_name
            )

        channel_restrictions = [get(ctx.guild.channels, id=int(c)) for c in channel_res]
        role_restrictions = [get(ctx.guild.roles, id=int(c)) for c in role_res]
        user_restrictions = [get(ctx.guild.members, id=int(c)) for c in user_res]

        if channel_restrictions or role_restrictions or user_restrictions:
            logger.debug("Found restrictions for command %s", command_name)
            channel_permission = ctx.channel in channel_restrictions or False
            member_permission = ctx.author in user_restrictions or False
            role_permission = bool(
                next(
                    (role for role in role_restrictions if role in ctx.author.roles),
                    None,
                )
            )

            if not any([channel_permission, member_permission, role_permission]):
                logger.debug(
                    "%s is not allowed to use %s here", ctx.author, command_name
                )
                embed = create_embed(self)
                embed.title = f"Command **{command_name}** { f'( inherited from **{cmd_name}** ) ' if inherited else '' }can only be used if"
                if user_restrictions:
                    embed.add_field(
                        name="you are",
                        value=", ".join(
                            [member.mention for member in user_restrictions]
                        ),
                    )
                if channel_restrictions:
                    embed.add_field(
                        name="you are in",
                        value=", ".join(
                            [channel.mention for channel in channel_restrictions]
                        ),
                    )
                if role_restrictions:
                    embed.add_field(
                        name="you have the role",
                        value=", ".join([role.mention for role in role_restrictions]),
                    )

                embed.colour = 0xED133F
                await ctx.send(embed=embed)
                return

        await self.invoke(ctx)

    def run(self):
        config_service = get_config_service(self.context)
        token = config_service.get_config("DEFAULT")["token"]
        super().run(token, reconnect=True)

    def get_full_name_for_called_command(self, ctx):
        command_name = ctx.command.name
        if isinstance(ctx.command, commands.Group):
            view = ctx.view
            previous = view.index

            command_name = f"{command_name} {self.get_full_name_for_called_subcommands(ctx.command, view)}"

            view.index = previous
            view.previous = previous

        return command_name

    def get_full_name_for_called_subcommands(self, command, view) -> str:
        subcommand_name = ""
        view.skip_ws()
        trigger = view.get_word()
        subcommand = command.all_commands.get(trigger, None)

        if subcommand:
            subcommand_name += subcommand.name
            if isinstance(subcommand, commands.Group):
                subcommand_name += " " + self.get_full_name_for_called_subcommands(
                    subcommand, view
                )

        return subcommand_name

    async def on_command_error(self, ctx, error):
        """Hooks for discord.py command errors."""
        if isinstance(error, commands.CommandOnCooldown):
            cooldown = round(error.retry_after)
            await ctx.send(
                "Woah **{}**, please cool down. Try **{}{}** again in **{}**s.".format(
                    ctx.author, ctx.prefix, ctx.invoked_with, cooldown
                )
            )
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f":negative_squared_cross_mark: {error}")

        elif isinstance(error, commands.BadUnionArgument):
            await ctx.send(
                f":negative_squred_cross_mark: You didn't supply any valid items! {ctx.prefix}help {ctx.command.qualified_name}"
            )
        elif isinstance(error, commands.MissingPermissions):
            perms = ", ".join(error.missing_perms)
            await ctx.send(f":no_entry: {perms}.")

        elif isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join([f"**{perm}**" for perm in error.missing_perms])
            await ctx.send(f":warning: I need permission to {perms} for this to work.")

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f":negative_squared_cross_mark: {error}")

        elif isinstance(error, commands.CommandNotFound):
            await ctx.send(f":negative_squared_cross_mark: {error}")

        else:
            if ctx.command:
                logger.error(
                    "An unexpected exception occured while invoking %s", ctx.command
                )
            else:
                logger.error("An unexpected exception occured")

            logger.error(
                "".join(
                    traceback.format_exception(type(error), error, error.__traceback__)
                )
            )

            await ctx.send(
                f":negative_squared_cross_mark: Something went wrong ;( Please contact the bot author:\n {str(error)}"
            )

    async def _before_invoke_callback(self, context):
        command_execution_start.set(arrow.utcnow())

    async def _after_invoke_callback(self, context):
        now = arrow.utcnow()
        cmd_exec_start: arrow.Arrow = command_execution_start.get()

        exec_delta = now - cmd_exec_start

        if exec_delta > timedelta(milliseconds=1000):
            logger.warning("Command execution took: %s", exec_delta)
        else:
            logger.debug("Command execution took: %s", exec_delta)

    @commands.check
    async def globally_block_bots(self, ctx):
        return not ctx.author.bot
