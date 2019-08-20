import re
import asyncio
from typing import List, Optional
import arrow
import discord
from discord.ext import commands as cmd
from discord.ext import tasks as tsk
from discord.utils import get
from .utils import checks
from .utils.converters import MemberID, ActionReason
from .utils.time import Duration

PERMANENT = re.compile(r"(in \d{2,3} years)")


async def bulk_mod(ctx, kind: str, members: List[int], reason: str):
    done = []
    for member in members:
        member_object = await ctx.bot.fetch_user(member)
        guild_member = ctx.guild.get_member(member_object.id)
        if guild_member is not None:
            await checks.executable(ctx, guild_member)
        try:
            await getattr(ctx.guild, kind)(member_object, reason=reason)
        except:
            pass
        else:
            done.append(member_object)
    return done


class ModerationModule(cmd.Cog):
    """This module is a beast. Empower your mods with every possible moderation command under the sun and more! A moderator is classified as someone who has the permission to ban other users.\nYou do not have to manually set a mod role - the bot will automatically determine who has moderator privileges."""

    def __init__(self, bot: cmd.Bot):
        self.bot = bot
        self.unmute_timer.start()
        self.unban_timer.start()
        self.unwarn_timer.start()

    def cog_unload(self):
        self.unmute_timer.cancel()
        self.unban_timer.cancel()
        self.unwarn_timer.cancel()

    @tsk.loop(seconds=10)
    async def unmute_timer(self):
        now = arrow.utcnow()
        log = self.bot.get_cog('LoggingModule')
        for guild in self.bot.guilds:
            to_action = await self.bot.db.zbyscore(
                f"{guild.id}:mutes", now.shift(seconds=-11).timestamp, now.timestamp
            )
            if to_action:
                role = await self.get_or_create_muted_role(guild)
                for action in to_action:
                    yes = guild.get_member(int(action))
                    if yes:
                        await yes.remove_roles(role, reason="Mute expired")
                        await log.on_member_unmute(guild, guild.me, yes, 'Mute expired.')
                await self.bot.db.zrembyscore(
                    f"{guild.id}:mutes", now.shift(seconds=-11).timestamp, now.timestamp
                )

    @tsk.loop(seconds=10)
    async def unban_timer(self):
        now = arrow.utcnow()
        log = self.bot.get_cog('LoggingModule')
        for guild in self.bot.guilds:
            to_action = await self.bot.db.zbyscore(
                f"{guild.id}:bans", now.shift(seconds=-11).timestamp, now.timestamp
            )
            if to_action:
                for action in to_action:
                    usr = await self.bot.fetch_user(int(action))
                    await guild.unban(usr, reason="ban expired")
                    await log.on_member_unban(guild, guild.me, usr, 'Ban expired.')
                await self.bot.db.zrembyscore(
                    f"{guild.id}:bans", now.shift(seconds=-11).timestamp, now.timestamp
                )
    
    @tsk.loop(seconds=10)
    async def unwarn_timer(self):
        now = arrow.utcnow()
        log = self.bot.get_cog('LoggingModule')
        for guild in self.bot.guilds:
            to_action = await self.bot.db.zbyscore(
                f"{guild.id}:wrn", now.shift(seconds=-11).timestamp, now.timestamp
            )
            if to_action:
                for action in to_action:
                    mem, _ = action.split('.')
                    usr = await self.bot.fetch_user(int(mem))
                    await self.bot.db.zincrement(f"{guild.id}:wrncnt", usr.id, score=-1)
                    await log.on_member_pardon(guild, guild.me, usr, 'Warning expired.')
                await self.bot.db.zrembyscore(f"{guild.id}:wrn", now.shift(seconds=-11).timestamp, now.timestamp)

    @unban_timer.before_loop
    async def before_unban_timer(self):
        await self.bot.wait_until_ready()

    @unmute_timer.before_loop
    async def before_unmute_timer(self):
        await self.bot.wait_until_ready()
    
    @unwarn_timer.before_loop
    async def before_unwarn_timer(self):
        await self.bot.wait_until_ready()

    async def mute_muted_role(self, role: discord.Role, guild: discord.Guild):
        for channel in guild.channels:
            perms = channel.overwrites_for(role)
            if isinstance(channel, discord.TextChannel) and perms.send_messages:
                await channel.set_permissions(
                    role, send_messages=False, add_reactions=False
                )
            elif isinstance(channel, discord.VoiceChannel) and perms.speak:
                await channel.set_permissions(role, speak=False)

    async def create_muted_role(self, guild):
        perms = discord.Permissions()
        perms.update(
            send_messages=False,
            read_messages=True,
            add_reactions=False,
            create_instant_invite=False,
            embed_links=False,
            attach_files=False,
            mention_everyone=False,
            speak=False,
            connect=True,
        )
        role = await guild.create_role(
            name="Muted",
            permissions=perms,
            colour=discord.Colour(0xE74C3C),
            reason="Creating Muted role since one does not exist already.",
        )
        await self.mute_muted_role(role, guild)
        await self.bot.db.hset(f"{guild.id}:set", "rolemuted", role.id)
        return role

    async def get_muted_role(self, guild):
        r = await self.bot.db.hget(f"{guild.id}:set", "rolemuted") or 0
        if r:
            r = guild.get_role(int(r))
        if r is None:
            r = get(guild.roles, name="Muted")
        if r is None:
            r = get(guild.roles, name="muted")
        return r

    async def get_or_create_muted_role(self, guild):
        r = await self.get_muted_role(guild)
        #if not r:
        #    r = await self.create_muted_role(guild)
        return r

    @cmd.command()
    @cmd.guild_only()
    @checks.can_kick()
    @checks.bot_has_perms(kick_members=True)
    async def kick(
        self,
        ctx: cmd.Context,
        members: cmd.Greedy[MemberID],
        *,
        reason: ActionReason = None,
    ):
        kicked = await bulk_mod(ctx, "kick", members, reason)
        result = ", ".join([f"**{k}**" for k in kicked])
        await ctx.send(f"**{ctx.author}** kicked {result}.")
        log = self.bot.get_cog("LoggingModule")
        for member in kicked:
            await log.on_member_kick(ctx.guild, ctx.author, member, reason)

    async def warn_func(self, guild_id, member_id, warning_id, expiry):
        zs = await self.bot.db.zincrement(f"{guild_id}:wrncnt", member_id)
        await self.bot.db.zadd(f"{guild_id}:wrn", f"{member_id}.{warning_id}", expiry)
        return zs

    @cmd.command()
    @cmd.guild_only()
    @checks.can_kick()
    async def warn(
        self,
        ctx: cmd.Context,
        members: cmd.Greedy[MemberID],
        duration: Optional[Duration],
        *,
        reason: ActionReason = None,
    ):
        wid = arrow.utcnow().timestamp
        if duration is None or not duration:
            duration = arrow.get(9999999999)
        if len(members) > 1:
            warned = []
            for m in members:
                mem = ctx.guild.get_member(m)
                if mem:
                    await checks.executable(ctx, mem)
                    await self.warn_func(ctx.guild.id, m, wid, duration.timestamp)
                    warned.append(mem)
            result = ", ".join([f"**{k}**" for k in warned])
            duration = duration.humanize()
            if duration == "just now":
                duration = "shortly"
            elif PERMANENT.match(duration):
                duration = "permanent"
            await ctx.send(f"**{ctx.author}** warned {result}.")
            log = self.bot.get_cog("LoggingModule")
            for user in warned:
                await log.on_member_warn(ctx.guild, ctx.author, user, reason)
            return
        if not members:
            return
        mem = ctx.guild.get_member(members[0])
        await checks.executable(ctx, mem)
        zs = await self.bot.db.zincrement(f"{ctx.guild.id}:wrncnt", members[0])
        await self.bot.db.zadd(
            f"{ctx.guild.id}:wrn", f"{members[0]}.{wid}", duration.timestamp
        )
        await ctx.send(
            "**{}** warned **{}**. They now have **{}** warning{}.".format(
                ctx.author, mem, zs, int(zs) > 1 and "s" or ""
            )
        )
        log = self.bot.get_cog("LoggingModule")
        duration = duration.humanize()
        if duration == "just now":
            duration = "shortly"
        elif PERMANENT.match(duration):
            duration = "permanent"
        await log.on_member_warn(ctx.guild, ctx.author, mem, reason, duration=duration)

    @cmd.command(name="warnings")
    async def warnings(self, ctx, member: Optional[cmd.MemberConverter]):
        if not member:
            member = ctx.author
        zs = await self.bot.db.zscore(f"{ctx.guild.id}:wrncnt", member.id)
        await ctx.send(
            "**{}** has **{}** warning{}".format(member, zs, int(zs) != 1 and "s" or "")
        )

    @cmd.command(name="mutewarn")
    async def mutewarn(self, ctx):
        await self.mute.invoke(await self.bot.get_context(ctx.message))
        await self.warn.invoke(await self.bot.get_context(ctx.message))

    @cmd.command()
    @cmd.guild_only()
    @checks.can_kick()
    async def pardon(
        self,
        ctx: cmd.Context,
        members: cmd.Greedy[MemberID],
        *,
        reason: ActionReason = None,
    ):
        if len(members) > 1:
            pardoned = []
            for m in members:
                warnings = await self.bot.db.zscore(f"{ctx.guild.id}:wrncnt", m)
                warnings = int(warnings)
                if warnings > 0:
                    await self.bot.db.zincrement(f"{ctx.guild.id}:wrncnt", m, score=-1)
                    to_delete = await self.bot.db.zscan(
                        f"{ctx.guild.id}:wrn", m, count=1
                    )
                    if to_delete:
                        await self.bot.db.zrem(f"{ctx.guild.id}:wrn", to_delete[0])
                    pardoned.append(ctx.guild.get_member(m))
            result = ", ".join([f"**{k}**" for k in pardoned])
            await ctx.send(f"**{ctx.author}** pardoned {result}.")
            log = self.bot.get_cog("LoggingModule")
            for user in pardoned:
                await log.on_member_pardon(ctx.guild, ctx.author, user, reason)
        elif not members:
            return
        m = members[0]
        mem = ctx.guild.get_member(m)
        warnings = await self.bot.db.zscore(f"{ctx.guild.id}:wrncnt", m)
        warnings = int(warnings)
        if warnings > 0:
            zs = await self.bot.db.zincrement(f"{ctx.guild.id}:wrncnt", m, score=-1)
            to_delete = await self.bot.db.zscan(
                f"{ctx.guild.id}:wrn", match=f"{m}.", count=1
            )
            if len(to_delete) / 2 > 1:
                to_delete = to_delete[1][0]
                await self.bot.db.zrem(f"{ctx.guild.id}:wrn", to_delete)
            await ctx.send(
                "**{}** pardoned **{}**. They now have **{}** warning{}.".format(
                    ctx.author, mem, zs, int(zs) != 1 and "s" or ""
                )
            )
            log = self.bot.get_cog("LoggingModule")
            await log.on_member_pardon(ctx.guild, ctx.author, mem, reason)

    async def mute_action(self, guild, member, duration, reason):
        role = await self.get_or_create_muted_role(guild)
        await self.mute_muted_role(role, guild)
        await member.add_roles(role, reason=reason)
        await self.bot.db.zadd(f"{guild.id}:mutes", member.id, duration.timestamp)

    @cmd.command()
    @cmd.guild_only()
    @checks.can_kick()
    @checks.bot_has_perms(manage_roles=True)
    async def mute(
        self,
        ctx: cmd.Context,
        members: cmd.Greedy[MemberID],
        duration: Optional[Duration],
        *,
        reason: ActionReason = None,
    ):
        if duration is None or not duration:
            duration = arrow.get(7559466982)
        role = await self.get_or_create_muted_role(ctx.guild)
        await self.mute_muted_role(role, ctx.guild)
        muted = []

        for m in members:
            if m == ctx.author.id:
                raise cmd.BadArgument('You cannot mute yourself.')
            mem = ctx.guild.get_member(m)
            if mem:
                await checks.executable(ctx, mem)
                await mem.add_roles(role, reason=reason)
                await self.bot.db.zadd(f"{ctx.guild.id}:mutes", m, duration.timestamp)
                muted.append(mem)
        if not muted:
            raise cmd.BadArgument('Did not mute anyone.')

        result = ", ".join([f"**{k}**" for k in muted])
        duration = duration.humanize()
        if duration == "just now":
            duration = "now"
        elif PERMANENT.match(duration):
            duration = "permanent"
        await ctx.send(f"**{ctx.author}** muted {result}.")
        log = self.bot.get_cog("LoggingModule")
        for user in muted:
            await log.on_member_mute(ctx.guild, ctx.author, user, reason, duration)

    @cmd.command()
    @cmd.guild_only()
    @checks.can_kick()
    @checks.bot_has_perms(manage_roles=True)
    async def unmute(
        self,
        ctx: cmd.Context,
        members: cmd.Greedy[MemberID],
        *,
        reason: ActionReason = None,
    ):
        role = await self.get_or_create_muted_role(ctx.guild)
        await self.mute_muted_role(role, ctx.guild)
        unmuted = []
        for m in members:
            mem = ctx.guild.get_member(m)
            if mem:
                await checks.executable(ctx, mem)
                await mem.remove_roles(role)
                await self.bot.db.zrem(f"{ctx.guild.id}:mutes", m)
                unmuted.append(mem)
        result = ", ".join([f"**{k}**" for k in unmuted])
        await ctx.send(f"**{ctx.author}** unmuted {result}.")
        log = self.bot.get_cog("LoggingModule")
        for user in unmuted:
            await log.on_member_unmute(ctx.guild, ctx.author, user, reason)

    @cmd.command()
    @cmd.guild_only()
    @checks.can_ban()
    @checks.bot_has_perms(ban_members=True)
    async def ban(
        self,
        ctx: cmd.Context,
        members: cmd.Greedy[MemberID],
        duration: Optional[Duration],
        *,
        reason: ActionReason = None,
    ):
        if duration is None or not duration:
            duration = arrow.get(7559466982)
        banned = await bulk_mod(ctx, "ban", members, reason)
        if not banned:
            raise cmd.BadArgument("No users to ban.")
        for b in banned:
            await self.bot.db.zadd(f"{ctx.guild.id}:bans", b.id, duration.timestamp)
        result = ", ".join([f"**{k}**" for k in banned])
        duration = duration.humanize()
        if duration == "just now":
            duration = "now"
        if "years" in duration:
            duration = "in a few years"
        await ctx.send(
            f"**{ctx.author}** banned {result}. They will be unbanned **{duration}**."
        )
        log = self.bot.get_cog("LoggingModule")
        for user in banned:
            await log.on_member_ban(ctx.guild, ctx.author, user, reason, duration)

    @cmd.command()
    @cmd.guild_only()
    @checks.can_ban()
    @checks.bot_has_perms(ban_members=True)
    async def unban(
        self,
        ctx: cmd.Context,
        members: cmd.Greedy[MemberID],
        *,
        reason: ActionReason = None,
    ):
        unbanned = await bulk_mod(ctx, "unban", members, reason)
        if not unbanned:
            raise cmd.BadArgument("Nobody to unban.")
        for b in unbanned:
            await self.bot.db.zrem(f"{ctx.guild.id}:bans", b.id)
        result = ", ".join([f"**{k}**" for k in unbanned])
        await ctx.send(f"**{ctx.author}** unbanned {result}.")
        log = self.bot.get_cog("LoggingModule")
        for user in unbanned:
            await log.on_member_unban(ctx.guild, ctx.author, user, reason)
    
    @cmd.command(aliases=['addroles', 'roleadd'])
    @cmd.guild_only()
    @checks.can_ban()
    @checks.bot_has_perms(manage_roles=True)
    async def addrole(
        self,
        ctx: cmd.Context,
        members: cmd.Greedy[cmd.MemberConverter],
        roles: cmd.Greedy[cmd.RoleConverter],
        *,
        reason: ActionReason = None,
    ):
        if not roles:
            raise cmd.BadArgument(
                "You need to specify at least one valid role to add."
            )
        plural = "s" if len(roles) != 1 else ""
        this = "these" if plural == "s" else "this"
        if [r for r in roles if r >= ctx.author.top_role]:
            raise cmd.MissingPermissions([f"You do not have permission to assign {this} role{plural}"])
        log = self.bot.get_cog('LoggingModule')
        for member in members:
            await member.add_roles(*roles)
            await log.on_member_role_add(ctx.guild, ctx.author, member, reason, roles)

        await ctx.send(':white_check_mark: Roles updated successfully!')
    
    @cmd.command(aliases=['removeroles', 'roleremove'])
    @cmd.guild_only()
    @checks.can_ban()
    @checks.bot_has_perms(manage_roles=True)
    async def removerole(
        self,
        ctx: cmd.Context,
        members: cmd.Greedy[cmd.MemberConverter],
        roles: cmd.Greedy[cmd.RoleConverter],
        *,
        reason: ActionReason = None,
    ):
        if not roles:
            raise cmd.BadArgument(
                "You need to specify at least one valid role to remove."
            )
        plural = "s" if len(roles) != 1 else ""
        this = "these" if plural == "s" else "this"
        if [r for r in roles if r >= ctx.author.top_role]:
            raise cmd.MissingPermissions([f"You do not have permission to remove {this} role{plural}"])
        log = self.bot.get_cog('LoggingModule')
        for member in members:
            await member.remove_roles(*roles)
            await log.on_member_role_remove(ctx.guild, ctx.author, member, reason, roles)

        await ctx.send(':white_check_mark: Roles updated successfully!')

    @cmd.command(aliases=["nick"])
    @cmd.guild_only()
    @checks.can_manage_nicknames()
    @checks.bot_has_perms(manage_nicknames=True)
    async def nickname(
        self, ctx, member: MemberID, nickname, *, reason: ActionReason = None
    ):
        member = discord.utils.get(ctx.guild.members, id=member)
        await checks.executable(ctx, member)
        old_nick = str(member.display_name)
        nickname = (" ".join(nickname.split()))[:32]
        if not nickname:
            nickname = member.name
        await member.edit(reason=reason, nick=nickname)
        await ctx.send(
            f"Changed **{member}**'s nick from **{old_nick}** to **{nickname}**."
        )
        log = self.bot.get_cog("LoggingModule")
        await log.on_member_nickname_update(ctx.guild, ctx.author, member, reason)

    @cmd.command(name="reason")
    @cmd.guild_only()
    @checks.is_mod()
    async def reason(self, ctx, case: int, *reason):
        if not reason:
            raise cmd.BadArgument("You must supply a valid reason.")
        cases = await self.bot.db.zscore("cases", ctx.guild.id)
        if int(case) > int(cases):
            plural = "s" if int(cases) != 1 else ""
            plural2 = "" if plural == "s" else "s"
            raise cmd.BadArgument(
                f"Invalid case #. **{cases}** case{plural} exist{plural2}."
            )
        case_file = await self.bot.db.hget(f"{ctx.guild.id}:case", case)
        chan = await self.bot.db.hget(f"{ctx.guild.id}:set", "logmod")
        chan = ctx.guild.get_channel(int(chan))
        if chan is None:
            raise cmd.BadArgument("Moderation channel is missing.")
        message = await chan.fetch_message(int(case_file))
        embed = message.embeds[0]
        embed.remove_field(2)
        embed.insert_field_at(2, name="Reason", value=" ".join(reason))
        await message.edit(embed=embed)
        await ctx.send(f":white_check_mark: Set case #**{case}** reason.")

    @cmd.Cog.listener()
    async def on_member_join(self, member):
        result = await self.bot.db.zscore(f"{member.guild.id}:mutes", member.id)
        if result is None:
            return
        if int(result) == 0:
            return
        role = await self.get_or_create_muted_role(member.guild)
        await self.mute_muted_role(role, member.guild)
        await member.add_roles(role)

    @cmd.Cog.listener()
    async def on_guild_role_update(self, b, a):
        r = await self.get_or_create_muted_role(b.guild)
        try:
            if b.id == r.id:
                await self.mute_muted_role(r, b.guild)
        except AttributeError:
            print("No muted role defined")

    @cmd.Cog.listener()
    async def on_guild_role_delete(self, r):
        r2 = await self.get_or_create_muted_role(r.guild)
        await self.mute_muted_role(r2, r.guild)


def setup(bot):
    cog = ModerationModule(bot)
    bot.add_cog(cog)
