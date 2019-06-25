"""Tap titans module."""
from typing import Optional
from decimal import Decimal, getcontext
import asyncio
import re
from datetime import datetime
from itertools import zip_longest
import difflib
import json
from string import ascii_lowercase, digits
from csv import DictReader
from math import floor
from random import choice
import arrow
import humanfriendly
import discord
from discord.ext import commands as cmd
from discord.ext import tasks as tsk
from discord.utils import get
from enum import Enum, unique
from .utils import checks
from .utils.time import Duration, get_hms
from .utils.converters import Truthy, MemberID
from .utils.etc import (
    ttconvert_discover,
    ttconvert_from_scientific,
    ttconvert_to_scientific,
    snake,
    rotate,
    lget,
    snake_get,
    get_closest_match,
)
from .utils import tt2

getcontext().prec = 4

TIER_LIST = "SABCD"
with open("modules/data/RaidDecks.json", "r") as jf:
    RAID_DECKS = json.load(jf)
with open("modules/data/RaidCards.json", "r") as jf:
    RAID_CARDS = json.load(jf)
with open("modules/data/GoldSources.json", "r") as jf:
    GOLD_SOURCES = json.load(jf)
with open("modules/data/TourneyData.json", "r") as jf:
    BONUSES = json.load(jf)
with open("modules/data/ArtifactColours.json", "r") as jf:
    COLOURS = json.load(jf)
with open("modules/data/SkillTree.json", "r") as jf:
    SKILL_TREE = json.load(jf)
BONUS_MAP = dict(
    Boost="General",
    Dmg="Damage",
    CostRed="Cost Reduction",
    Equip="Equipment",
    Chance="Chance",
    Mana="Mana",
    Duration="Duration",
    Gold="Gold",
)
TREE_MAP = dict(Red="Knight", Blue="Sorcerer", Yellow="Warlord", Green="Assassin")
SKILL_COLOURS = dict(red="FF6034", yellow="F7D530", blue="51B7EF", green="5BC65B")
TIMER_TEXT = "Raid {} **{:02}**h **{:02}**m **{:02}**s."


class TTDeck(cmd.Converter):
    async def convert(self, ctx, arg):
        arg = arg.lower()
        closest_match = difflib.get_close_matches(
            arg, list(RAID_DECKS.keys()), n=1, cutoff=0.85
        )
        if closest_match:
            return closest_match[0], RAID_DECKS.get(closest_match[0])
        if not closest_match and arg.strip():
            closest_match = next(
                (k for k in list(RAID_DECKS.keys()) if k.startswith(arg)), None
            )
            if closest_match:
                return closest_match, RAID_DECKS.get(closest_match)
        return None, None


TT_ROLES = dict(G="gm", M="master", C="captain", K="knight", R="recruit", T="timer")
TT_CSV_FILES = dict(
    cards="RaidSkill",
    zones="RaidLevel",
    titans="RaidEnemy",
    arts="Artifact",
    equips="Equipment",
    skills="SkillTree",
)
TT_TITAN_LORDS = ["Lojak", "Takedar", "Jukk", "Sterl", "Mohaca", "Terro"]


class TapTitansModule(cmd.Cog):
    """Tap Titans 2 is an idle RPG game on iOS and Android that lets you take the battle to the titans! Level up heroes, participate in Clan Raids, and stomp on other players in Tournaments!\nI am working hard to make improvements to this module. It's nearly a thousand lines long and that's just with decks and raids!"""

    def __init__(self, bot: cmd.Bot):
        self.bot = bot
        self.aliases = ["tt"]

        self.raid_timer.start()
        self.em = 440785686438871040
        for k, val in TT_CSV_FILES.items():
            setattr(self, k, [])
            with open(f"modules/data/{val}Info.csv") as csvfile:
                reader = DictReader(csvfile)
                for row in reader:
                    getattr(self, k).append(row)

    def snake(self, text):
        return text.lower().replace(" ", "_").replace("'", "").replace("-", "")

    def emoji(self, search):
        "Get an emoji from the bot's guild."
        return get(self.bot.emojis, name=self.snake(search), guild_id=self.em)

    def cog_unload(self):
        self.raid_timer.cancel()

    async def get_roles(self, groupdict, *roles):
        return [int(groupdict.get(r, 0)) for r in roles]

    async def get_raid_group_or_break(self, group, ctx):
        test = await self.bot.db.exists(group)
        if not test:
            raise cmd.BadArgument(
                f"No raid groups. Set one up by **{ctx.prefix}setup tt2**"
            )
        return group

    async def has_timer_permissions(self, ctx, groupdict):
        "Check if the user has permission to change the raid timer."
        roles = await self.get_roles(groupdict, *["gm", "master", "timer"])
        if not any(roles):
            raise cmd.BadArgument("No clan roles are set up.")
        if not await checks.user_has_role([r.id for r in ctx.author.roles], *roles):
            raise cmd.BadArgument

    async def has_clan_permissions(self, ctx, groupdict):
        "Check if the user has any clan role."
        roles = await self.get_roles(
            groupdict, *["gm", "master", "captain", "knight", "recruit"]
        )
        if not any(roles):
            raise cmd.BadArgument("No clan roles are set up.")
        if not await checks.user_has_role([r.id for r in ctx.author.roles], *roles):
            raise cmd.BadArgument("You do not have permission.")

    async def has_admin_or_mod_or_master(self, ctx, groupdict):
        "Check if the user is admin/mod/gm/master."
        is_admin = await checks.user_has_admin_perms(ctx.author, ctx.guild)
        if is_admin:
            return True
        is_mod = await checks.user_has_mod_perms(ctx.author, ctx.guild)
        if is_mod:
            return True
        roles = await self.get_roles(groupdict, *["gm", "master"])
        if not await checks.user_has_role((r.id for r in ctx.author.roles), *roles):
            raise cmd.BadArgument("You need gm/master role.")
        if not is_mod and not is_admin:
            raise cmd.BadArgument("You need admin or mod permissions.")

    @tsk.loop(seconds=10)
    async def raid_timer(self):
        "Task for updating raid timers."
        now = arrow.utcnow()
        future = now.shift(hours=50)
        await asyncio.gather(
            *(self.update_raid_timer(guild, now, future) for guild in self.bot.guilds)
        )

    async def update_raid_timer(self, guild, now, future):
        "Updates all raid timers for a guild."
        await asyncio.gather(
            *(self.update_timer_group(guild, now, future, g) for g in [1, 2, 3]),
            return_exceptions=True,
        )

    async def update_timer_group(self, guild, now, future, group):
        "Updates raid timer for a group."
        g = await self.bot.db.hgetall(f"{guild.id}:tt:{group}")
        if not g:
            raise asyncio.CancelledError
        spawn = g.get("spawn", 0)
        cd = g.get("cd", 0)
        if not any([spawn, cd]):
            raise asyncio.CancelledError
        if (
            spawn
            and not now < arrow.get(spawn or future.timestamp)
            or cd
            and not now < arrow.get(cd or future.timestamp)
        ):
            await self.update_timer_queue(guild, now, group, g)
            raise asyncio.CancelledError
        chan = guild.get_channel(int(g.get("announce", 0)))
        if chan is None:
            raise asyncio.CancelledError
        reset = g.get("reset", 0)
        if not reset and not cd:
            reset = "starts in"
        elif cd:
            reset = "cooldown ends in"
            dt = arrow.get(cd) - now
        else:
            reset = f"reset #**{reset}** starts in"
        if spawn:
            dt = arrow.get(spawn) - now
        hms = await get_hms(dt)
        content = TIMER_TEXT.format(reset, hms[0], hms[1], hms[2])
        message = int(g.get("edit", 0))
        if message:
            await self.update_timer_message(chan, message, content)
        else:
            await chan.send(content)

    async def update_timer_queue(self, guild, now, group, g):
        fmt_group = f"{guild.id}:tt:{group}"
        q = await self.bot.db.lrange(f"{fmt_group}:q")
        spawn = g.get("spawn", 0)
        cd = g.get("cd", 0)
        c = int(g.get("announce", 0))
        chan = guild.get_channel(c)
        current = g.get("current", "").strip().split()
        qmode = int(g.get("mode", 1))
        upnext = q[0:qmode]
        depl = int(g.get("depl", 0))
        reset = int(g.get("reset", 0))
        if (not current and not q and spawn) or depl:
            arr = arrow.get(spawn).shift(hours=12 * (reset + 1)) - now
            hms = await get_hms(arr)
            if any([x < 0 for x in hms]):
                reset = reset + 1
                await self.bot.db.hset(fmt_group, "depl", 0)
                await self.bot.db.hset(fmt_group, "reset", reset)
                hms = await get_hms(arr)
                arr = arrow.get(spawn).shift(hours=12 * (reset + 1)) - now
            content = TIMER_TEXT.format(
                f"reset #**{reset+1}** starts in", hms[0], hms[1], hms[2]
            )
            message = int(g.get("edit", 0))
            await self.update_timer_message(chan, message, content)
        elif not current and not q and cd:
            arr = now - arrow.get(cd)
            hms = await get_hms(arr)
            content = TIMER_TEXT.format("cooldown ended", hms[0], hms[1], hms[2])
            message = int(g.get("edit", 0))
            await self.update_timer_message(chan, message, content)

        if current or depl:
            return

        if not q and not current and not depl:
            await chan.send(f"Queue done! You may queue for reset #**{reset+1}**.")
            edit = await chan.send("Preparing next reset timer...")
            await self.bot.db.hset(fmt_group, "edit", edit.id)
            await self.bot.db.hset(fmt_group, "depl", 1)
            await self.bot.db.delete(f"{fmt_group}:q")
            return

        members = [guild.get_member(int(m)) for m in upnext]
        cnt = 0
        while cnt < len(upnext):
            await self.bot.db.lrem(f"{fmt_group}:q", upnext[cnt])
            cnt += 1
        await self.bot.db.hset(
            fmt_group, "current", " ".join([str(m.id) for m in members])
        )
        await chan.send(
            "It's {}'s turn to attack the raid!".format(
                ", ".join([f"{m.mention}" for m in members])
            )
        )

    async def update_timer_message(self, channel, message, content):
        """Update raid timer message."""
        msg = await channel.fetch_message(message)
        await msg.edit(content=content)

    @raid_timer.before_loop
    async def before_raid_timer(self):
        """wait until the bot is connected to update timers"""
        await self.bot.wait_until_ready()

    @cmd.group(name="taptitans", aliases=["tt"], case_insensitive=True, hidden=True)
    async def taptitans(self, ctx):
        pass

    async def show_slots(self, action, group, guild, res):
        "Show the raid group slots in the current guild."
        return "{} group **{}** {} ~**{}**. Currently used slots: [{}] [{}] [{}]".format(
            action,
            group,
            "Deleted" in action and "from" or "to",
            guild,
            res["1"] and "x" or "",
            res["2"] and "x" or "",
            res["3"] and "x" or "",
        )

    @taptitans.command(name="groupadd", aliases=["gadd"], usage="slot")
    @cmd.guild_only()
    @checks.is_mod()
    async def tt_groupadd(self, ctx):
        "Add a raid group."
        res = dict(
            zip(
                ["1", "2", "3"],
                await asyncio.gather(
                    *(self.bot.db.hgetall(f"{ctx.guild.id}:tt:{x}") for x in [1, 2, 3])
                ),
            )
        )
        count = len([k for k in res if res[k]])
        if count < 3:
            slot = next((x for x in res if not res[x]), "3")
            group = f"{ctx.guild.id}:tt:{slot}"
            r1 = await self.bot.db.hset(group, "tier", 1)
            r2 = await self.bot.db.hset(group, "zone", 1)
            if not r1 and not r2:
                await ctx.send("Could not add group right now. Try again later.")
                return
            res[slot] = {"tier": 1}
            txt = await self.show_slots("Added", slot, ctx.guild, res)
            await ctx.send(txt)
        elif count == 3:
            await ctx.send(
                f"Max group count reached. Use **{ctx.prefix}groupdel <x>** to delete a group."
            )

    @taptitans.command(name="groupdel", aliases=["gdel"], usage="slot")
    @cmd.guild_only()
    @checks.is_mod()
    async def tt_groupdel(self, ctx, slot: Optional[int]):
        "Delete a raid group."
        if slot not in [1, 2, 3]:
            raise cmd.BadArgument("Specify a slot between **1** and **3** to delete.")
        result = await self.bot.db.delete(f"{ctx.guild.id}:tt:{slot}")
        res = dict(
            zip(
                ["1", "2", "3"],
                await asyncio.gather(
                    *(self.bot.db.hgetall(f"{ctx.guild.id}:tt:{x}") for x in [1, 2, 3])
                ),
            )
        )
        if result:
            txt = await self.show_slots("Deleted", slot, ctx.guild, res)
            await ctx.send(txt)
            return
        await ctx.send(
            "There's no group in that slot. Currently used slots: [{}] [{}] [{}]".format(
                res["1"] and "x" or "", res["2"] and "x" or "", res["3"] and "x" or ""
            )
        )

    @taptitans.command(
        name="groupget", aliases=["gshow", "groupshow", "gget"], usage="slot"
    )
    @cmd.guild_only()
    @checks.is_mod()
    async def tt_groupget(self, ctx, slot: Optional[int] = 1):
        "Display a raid group."
        if slot not in [1, 2, 3]:
            raise cmd.BadArgument(
                "You must specify a slot between **1** and **3** to show."
            )
        r = await self.bot.db.hgetall(f"{ctx.guild.id}:tt:{slot}")
        roles = "\n".join(
            [
                "`{}` @**{}**".format(
                    n, discord.utils.get(ctx.guild.roles, id=int(r.get(m, 0)))
                )
                for n, m in TT_ROLES.items()
            ]
        )
        await ctx.send(
            f"**{r.get('name', '<clanname>')}** [{r.get('code', '00000')}] "
            f"T{r.get('tier', 1)}Z{r.get('zone', 1)}\n"
            f"{roles}\n"
            f"Messages are broadcast in #**{discord.utils.get(ctx.guild.channels, id=int(r.get('announce', 0)))}** and queue size is **{r.get('mode', 1)}**."
        )

    @taptitans.group(name="set", usage="key val")
    @cmd.guild_only()
    @checks.is_mod()
    async def tt_set(self, ctx, group: Optional[tt2.TTRaidGroup], key: tt2.TTKey, val):
        "Set a settings key for tap titans clan."
        if group is None:
            group = f"{ctx.guild.id}:tt:1"
        group = await self.get_raid_group_or_break(group, ctx)
        groupdict = await self.bot.db.hgetall(group)
        await self.has_admin_or_mod_or_master(ctx, groupdict)
        if key in "gmmastercaptainknightrecruitapplicantguesttimer":
            val = await cmd.RoleConverter().convert(ctx, val)
            await self.bot.db.hset(group, key, val.id)
        elif key == "announce":
            val = await cmd.TextChannelConverter().convert(ctx, val)
            await self.bot.db.hset(group, key, val.id)
        elif key in "zonetier":
            try:
                val = int(val)
            except:
                raise cmd.BadArgument(f"Bad value for raid {key}")
            else:
                if not 1 <= val <= 10:
                    raise cmd.BadArgument()
                await self.bot.db.hset(group, key, val)
        elif key == "farm":
            val = await Truthy().convert(ctx, val)
            await self.bot.db.hset(group, key, val)
        elif key == "depl":
            val = await Truthy().convert(ctx, val)
            await self.bot.db.hset(group, key, val)
        elif key == "name":
            await self.bot.db.hset(group, key, val)
        elif key == "code":
            val = val.lower()
            if len(val) > 7 or len(val) < 5:
                return
            _, db = await self.bot.db.hscan("cc", match=val)
            cc = groupdict.get(key, None)
            if val == cc:
                await ctx.send("You are already using this clan code.")
                return
            in_use = lget(db, 1, 0)
            if in_use and in_use != str(ctx.guild.id):
                raise cmd.BadArgument(
                    "Code in use. Appeal to bot owner if someone stole your clan code."
                )
            if not cc:
                await self.bot.db.hdel("cc", cc)
            await self.bot.db.hset("cc", val, ctx.guild.id)
            await self.bot.db.hset(group, key, val)
        elif key == "mode":
            try:
                val = int(val)
            except:
                raise cmd.BadArgument("You must supply a number between 1 and 5.")
            if not 1 <= val <= 5:
                raise cmd.BadArgument("Queue mode must be between 1 and 5.")
            await self.bot.db.hset(group, key, val)
        else:
            await self.bot.db.hset(group, key, val)
        await ctx.send(f"Set the TT2 **{key}** key to **{val}**")

    @taptitans.group(
        name="raid",
        aliases=["boss", "rd"],
        case_insensitive=True,
        invoke_without_command=True,
        usage="0h0m0s",
    )
    async def tt_raid(
        self,
        ctx,
        group: Optional[tt2.TTRaidGroup],
        level: cmd.Greedy[int],
        time: Optional[Duration],
    ):
        "Sets a raid to spawn after the given time."
        if group is None:
            group = f"{ctx.guild.id}:tt:1"
        group = await self.get_raid_group_or_break(group, ctx)
        groupdict = await self.bot.db.hgetall(group)
        await self.has_timer_permissions(ctx, groupdict)
        is_live = groupdict.get("spawn", 0)
        cd = groupdict.get("cd", 0)
        reset = int(groupdict.get("reset", 0))
        if not reset and not cd:
            rs_txt = "starts"
        elif cd:
            rs_txt = "cooldown ends"
        else:
            rs_txt = f"reset #**{reset}** is"
        if is_live or cd:
            arr_x = arrow.get(is_live or cd)
            arr_n = arrow.utcnow()
            if arr_n > arr_x and is_live and not cd:
                arr_x = arr_x.shift(hours=12 * (reset + 1))
                dt = arr_x - arr_n
                rs_txt = f"reset #**{reset+1}** is"
            elif arr_x >= arr_n:
                dt = arr_x - arr_n
            _h, _m, _s = await get_hms(dt)
            await ctx.send(f"Raid {rs_txt} in **{_h}**h **{_m}**m **{_s}**s.")
            return
        if not level or len(level) == 0 or level is None:
            tier = groupdict.get("tier", 1)
            zone = groupdict.get("zone", 1)
        elif not all(1 <= x <= 10 for x in level):
            raise cmd.BadArgument("Tier/zone must be between **1** and **10**.")
        elif len(level) == 2:
            tier, zone = level
        elif len(level) == 1:
            tier, zone = level, 1
        await self.bot.db.hset(group, "depl", 0)
        if not time or time is None:
            time = await Duration().convert(ctx, "24h")
        await self.bot.db.hset(group, "spawn", time.timestamp)
        time = time.humanize()
        if time == "just now":
            time = "now"
        edit = await ctx.send(
            f"Tier **{tier}**, zone **{zone}** raid starts **{time}**."
        )
        announce = int(groupdict.get("announce", 0))
        if announce and announce != ctx.channel.id:
            chan = self.bot.get_channel(announce)
            if chan:
                edit = await chan.send(
                    f"Tier **{tier}**, zone **{zone}** raid starts **{time}**."
                )
                await self.bot.db.hset(group, "edit", edit.id)
        elif announce:
            await self.bot.db.hset(group, "edit", edit.id)
        elif not announce:
            announce = await self.bot.db.hset(group, "announce", ctx.channel.id)
            await self.bot.db.hset(group, "edit", edit.id)

    @tt_raid.command(name="upload", aliases=["u"])
    async def tt_raid_upload(self, ctx, group: int, date, level, *, data):
        if not len(level.split("/")) == 2:
            raise cmd.BadArgument("Level must be in the format 0/0")
        if not len(date.split(".")) == 3:
            raise cmd.BadArgument("You must specify a date in the format yyyy.mm.dd")
        result = []
        for row in DictReader(data.split("\n")):
            result.append(row)
        res_dict = {}
        for r in result:
            res_dict[r["ID"]] = {"attacks": r["Attacks"], "damage": r["Damage"]}
        print(res_dict)
        data = dict(
            id=ctx.guild.id, date=date, gid=group, export_data=res_dict, level=level
        )
        postie = self.bot.get_cog("PostgreModule")
        await postie.sql_insert("raidgroup", data)
        await ctx.send("Successfully uploaded data.")

    async def num_to_hum(self, num):
        num = humanfriendly.format_number(round(num))
        print(num)
        nmap = "K M B T".split()
        commas = num.count(",")
        points = num.split(",")
        if not commas:
            return num
        return f"{points[0]}.{points[1]}{nmap[commas-1]}"

    @tt_raid.command(name="average", aliases=["avg"])
    async def tt_raid_average(
        self, ctx, kind: Optional[str] = "player", player: Optional[MemberID] = None
    ):
        if kind.lower() not in ["player", "clan"]:
            raise cmd.BadArgument(f"Average type must be one of: **player**, **clan**")
        code = None
        if kind == "player":
            if player is None:
                player = ctx.author.id
            player = await self.bot.fetch_user(player)
            code = await self.bot.db.hget(f"{player.id}:tt", "sc")
            if code is None or not code:
                raise cmd.BadArgument("You do not have a support code set.")
        postie = self.bot.get_cog("PostgreModule")
        data = await postie.sql_query_db(
            f"SELECT * FROM raidgroup WHEREALL id = {ctx.guild.id}"
        )
        sum_hits = []
        sum_dmg = []
        async with ctx.typing():
            for datapoint in data:
                ddict = dict(datapoint)["export_data"]
                if kind == "player":
                    sum_hits.append(int(ddict.get(code, {}).get("attacks", 0)))
                    sum_dmg.append(int(ddict.get(code, {}).get("damage", 0)))
                else:
                    for key in ddict:
                        sum_dmg.append(int(ddict[key].get("damage", 0)))
                        sum_hits.append(int(ddict[key].get("attacks", 0)))

            hf_sum_hits = await self.num_to_hum(sum(sum_hits))
            hf_sum_dmg = await self.num_to_hum(sum(sum_dmg))
            print(hf_sum_dmg)
            title = "Raid data for clan"
            if kind == "player":
                title = f"Raid data for player {player}"
            embed = discord.Embed(title=title)
            average = await self.num_to_hum(sum(sum_dmg) / sum(sum_hits))
            embed.add_field(name="Average", value=average, inline=False)
            embed.add_field(name="Hits", value=hf_sum_hits)
            embed.add_field(name="Damage", value=hf_sum_dmg)
            await ctx.send(embed=embed)

    @tt_raid.command(name="clear", aliases=["end", "ended", "cleared", "cd"])
    async def tt_raid_clear(
        self, ctx, group: Optional[tt2.TTRaidGroup], cd: Optional[Duration]
    ):
        "Clears a raid. Use this only when completing a raid. Use cancel to wipe the timer."
        if group is None:
            group = f"{ctx.guild.id}:tt:1"
        group = await self.get_raid_group_or_break(group, ctx)
        groupdict = await self.bot.db.hgetall(group)
        spawn = groupdict.get("spawn", 0)
        if not spawn and not groupdict.get("cd", 0):
            raise cmd.BadArgument("No raid to clear.")
        elif groupdict.get("cd", 0):
            raise cmd.BadArgument(f"Raid on cooldown. Use **{ctx.prefix}cancel**.")
        await self.has_timer_permissions(ctx, groupdict)

        now = arrow.utcnow()
        spwn_arrow = arrow.get(spawn)
        if now < spwn_arrow:
            raise cmd.BadArgument(
                f"Can't clear unspawned raid. Use **{ctx.prefix}cancel**."
            )
        if cd is None:
            cd = now.shift(minutes=59, seconds=59)
        delta = cd - now
        _h, _m, _s = await get_hms(delta)
        shifter = {}
        if _m not in [0, 59]:
            shifter["minutes"] = 60 - _m
        if _s not in [0, 59]:
            shifter["seconds"] = 60 - _s
        if cd < spwn_arrow.shift(minutes=60):
            await ctx.send(
                "You cannot timetravel. Cooldown end must be 60 minutes after raid."
            )
            raise cmd.BadArgument

        total_time = now.shift(**shifter) - spwn_arrow
        g = groupdict
        _h2, _m2, _s2 = await get_hms(total_time)
        cleared = f"**{_h2}**h **{_m2}**m **{_s2}**s"
        await ctx.send(
            "Tier **{}**, Zone **{}** raid **cleared** in {}.".format(
                g.get("tier", 1), g.get("zone", 1), cleared
            )
        )
        shft_arrow = now.shift(minutes=_m > 0 and _m or 0, seconds=_s > 0 and _s or 0)
        await self.bot.db.hset(group, "cd", shft_arrow.timestamp)
        await self.bot.db.hdel(group, "spawn")
        await self.bot.db.hdel(group, "edit")
        cleared = f"**{_h}**h **{_m}**m **{_s}**s"
        msg = await ctx.send(f"Raid cooldown ends in {cleared}.")
        await self.bot.db.hset(group, "edit", msg.id)

    @tt_raid.command(name="cancel", aliases=["abort", "stop"])
    async def tt_raid_cancel(self, ctx, group: Optional[tt2.TTRaidGroup]):
        "Cancels a currently scheduled raid."
        if group is None:
            group = f"{ctx.guild.id}:tt:1"
        group = await self.get_raid_group_or_break(group, ctx)
        groupdict = await self.bot.db.hgetall(group)
        await self.has_timer_permissions(ctx, groupdict)
        spawn = groupdict.get("spawn", None)
        cd = groupdict.get("cd", None)
        if not any([spawn, cd]):
            await ctx.send("No raid to cancel.")
            return
        else:
            for k in "edit spawn cd current depl reset".split():
                await self.bot.db.hdel(group, k)
        await self.bot.db.delete(f"{group}:q")
        await ctx.send("Cancelled the current raid.")

    @tt_raid.command(name="info", aliases=["i"])
    async def tt_raid_info(self, ctx, tier: Optional[int] = 1, zone: Optional[int] = 1):
        count = len(set([z["TierID"] for z in self.zones]))
        if tier > count:
            raise cmd.BadArgument(f"There are **{count}** tiers.")
        elif zone > tier * 10:
            raise cmd.BadArgument(f"There are **{tier*10}** zones in tier **{tier}**.")
        raid = next(
            (
                z
                for z in self.zones
                if z["TierID"] == str(tier) and z["LevelID"] == str(zone)
            )
        )
        enemies = raid["EnemyIDs"].split(",")
        titans = [t for t in self.titans if t["EnemyID"] in enemies]
        has_armor = raid["HasArmor"] == "TRUE"
        for t in titans:
            if has_armor:
                t["armor_calc"] = Decimal(t["Total in Armour"]) * Decimal(
                    raid["BaseHP"]
                )
            t["hp_calc"] = Decimal(t["Total in Body"]) * Decimal(raid["BaseHP"])
            t["friendly_name"] = TT_TITAN_LORDS[int(t["EnemyID"][-1]) - 1]
        embed = discord.Embed(
            title=f"Info for Raid - Tier {tier} Zone {zone}",
            description="Spawns **{}**{} titans: \n{}".format(
                raid["TitanCount"],
                has_armor and " **armored**" or "",
                "\n".join(
                    "{} {} **{}**{}".format(
                        discord.utils.get(
                            self.bot.emojis, name=t["friendly_name"].lower()
                        ),
                        t["friendly_name"],
                        humanfriendly.format_size(t["hp_calc"])[0:-1],
                        has_armor
                        and " (armour: **"
                        + humanfriendly.format_size(t.get("armor_calc"))[0:-1]
                        + "**)",
                    )
                    for t in titans
                ),
            ),
            color=0x186281,
        )
        embed.add_field(
            name=f"{self.emoji('ticket')} Tickets",
            value="Cost - **{}** Reward - **{}** on first clear".format(
                raid["TicketCost"], raid["TicketClanReward"]
            ),
            inline=False,
        )
        embed.add_field(
            name=f"{self.emoji('xp')} XP",
            value="Clan - **{}** Player - **{}**".format(
                raid["XPClanReward"], raid["XPPlayerReward"]
            ),
            inline=False,
        )
        embed.add_field(
            name="{} Dust & Cards".format(self.emoji("cards_and_dust")),
            value="Dust - **{}** Cards - **{}**".format(
                raid["DustPlayerReward"], raid["CardPlayerReward"]
            ),
            inline=False,
        )
        embed.add_field(
            name=f"{self.emoji('hero_scroll')} Scrolls",
            value="Scrolls - **{}** Fortune Scrolls - **{}**".format(
                raid["ScrollPlayerReward"], raid["FortuneScrollPlayerReward"]
            ),
            inline=False,
        )
        embed.add_field(name="Attacks/Reset", value=raid["AttacksPerReset"])
        await ctx.send("", embed=embed)

    @taptitans.command(
        name="queue", aliases=["q"], case_insensitive=True, usage="show|clear|skip"
    )
    async def tt_queue(self, ctx, group: Optional[tt2.TTRaidGroup], list=None):
        "Enter into the tap titans raid queue."
        if group is None:
            group = f"{ctx.guild.id}:tt:1"
        group = await self.get_raid_group_or_break(group, ctx)
        groupdict = await self.bot.db.hgetall(group)
        await self.has_clan_permissions(ctx, groupdict)
        result = groupdict.get("spawn", 0)
        if not result:
            raise cmd.BadArgument("No raid/reset to queue for.")
        resets = int(groupdict.get("reset", 0))
        depl = int(groupdict.get("depl", 0))
        if not resets and not depl:
            resets = "first spawn"
        elif resets and not depl:
            resets = f"reset #{resets}"
        elif depl:
            resets = f"reset #{resets+1}"
        q = f"{group}:q"
        users = await self.bot.db.lrange(q)
        current = groupdict.get("current", "").split()
        if not list:
            if not str(ctx.author.id) in users:
                await self.bot.db.rpush(q, ctx.author.id)
                users.append(ctx.author.id)
            else:
                await ctx.send(
                    f"You're already #**{users.index(str(ctx.author.id))+1}** in the queue."
                )
                return
        elif list in ["clear", "wipe", "erase"]:
            await self.has_timer_permissions(ctx, groupdict)
            await self.bot.db.delete(q)
            await self.bot.hdel(group, "current")
            await ctx.send(":white_check_mark: Queue has been cleared!")
            return
        elif list in ["skip"]:
            await self.has_timer_permissions(ctx, groupdict)
            await self.bot.hdel(group, "current")
        if str(ctx.author.id) in current:
            raise cmd.BadArgument(f"You're attacking. Use **{ctx.prefix}tt d**")
        u = []

        mode = int(groupdict.get("mode", 1))
        clusters = zip_longest(*[iter(users)] * mode, fillvalue=None)
        result = []
        for c in clusters:
            temp = str(len(result) + 1)
            r = []
            for u in c:
                if u is not None:
                    ux = await self.bot.fetch_user(int(u))
                    r.append(f"{ux}")
            result.append(temp + ". " + ", ".join(r))

        if result:
            await ctx.send(
                "**Queue** for **{}**:\n```css\n{}```\nUse **;tt unqueue** to cancel.".format(
                    resets, result and "\n".join(result) or " "
                )
            )
            return
        await ctx.send(f"**Queue** for **{resets}** is currently **empty**.")

    @taptitans.command(name="unqueue", aliases=["unq", "uq"], case_insensitive=True)
    async def tt_unqueue(
        self, ctx, group: Optional[tt2.TTRaidGroup], members: cmd.Greedy[MemberID]
    ):
        "Remove yourself from the tap titans raid queue."
        if group is None:
            group = f"{ctx.guild.id}:tt:1"
        group = await self.get_raid_group_or_break(group, ctx)
        g = await self.bot.db.hgetall(group)
        await self.has_clan_permissions(ctx, g)
        result = g.get("spawn", 0)
        depl = g.get("depl", 0)
        if not result:
            raise cmd.BadArgument("No raid/reset to queue for.")
        resets = g.get("resets", 0)
        if not resets and not depl:
            resets = "first spawn"
        elif resets and not depl:
            resets = f"reset #{resets}"
        elif depl:
            resets = f"reset #{resets}+1"
        q = await self.bot.db.lrange(f"{group}:q")
        current = g.get("current", "").split()
        if str(ctx.author.id) in current:
            raise cmd.BadArgument(f"Try **{ctx.prefix}tt done** instead.")
        if not str(ctx.author.id) in q:
            raise cmd.BadArgument(f"You're not in the queue, **{ctx.author}**.")
        res = await self.bot.db.lrem(f"{group}:q", ctx.author.id)
        if res:
            await ctx.send(f"Ok **{ctx.author}**, I removed you from the queue.")

    @taptitans.command(name="done", aliases=["d"])
    async def tt_done(self, ctx, group: Optional[tt2.TTRaidGroup]):
        "Mark yourself as done in the raid queue. Will only work if you're currently attacking."
        if group is None:
            group = f"{ctx.guild.id}:tt:1"
        group = await self.get_raid_group_or_break(group, ctx)
        g = await self.bot.db.hgetall(group)
        await self.has_clan_permissions(ctx, g)
        if not g.get("spawn", 0):
            raise cmd.BadArgument("No raid/reset rn.")
        current = g.get("current", "").split()
        if not str(ctx.author.id) in current:
            q = await self.bot.db.lrange(f"{group}:q")
            if not str(ctx.author.id) in q:
                raise cmd.BadArgument("It's not your turn & you're not queued.")
            else:
                raise cmd.BadArgument(f"Not your go. Do **{ctx.prefix}tt uq** instead.")
        else:
            current = " ".join(current)
            current = current.replace(str(ctx.author.id), "")
            await self.bot.db.hset(group, "current", current.strip())
            await ctx.send(f"**{ctx.author}** has finished their turn.")

    @taptitans.command(name="card", aliases=["cards"], case_insensitive=True)
    async def tt_card(self, ctx, *card):
        "Shows you information about tap titans cards."
        card, data = await tt2.TTRaidCard().convert(ctx, " ".join(card))
        if not card or card is None:
            card = self.emoji("tt2_card")
            embed = discord.Embed(
                title=f"{card} Avaliable Cards",
                description="List of cards in TT2 raids, sorted by category.",
                color=int("0x186281", 16),
            )
            for category in ["Burst", "Affliction", "Support"]:
                emoji = self.emoji(category)
                embed.add_field(
                    name=f"{emoji} {category}",
                    value="\n".join(
                        [
                            f"{self.emoji(c['Name'])} {c['Name']}"
                            for c in self.cards
                            if c["Category"] == category and c["Name"] in RAID_CARDS
                        ]
                    ),
                )
            embed.set_thumbnail(url=card.url)
        else:
            jcard = [RAID_CARDS[c] for c in RAID_CARDS.keys() if snake(c) == card][0]
            icx = self.emoji(data["Category"])
            embed = discord.Embed(
                title=f"{icx} {data['Name']}",
                description="Taps have a chance to {}".format(jcard["d"]),
                color=int("0x" + data["Color"][1:], 16),
            )

            embed.set_thumbnail(url=self.emoji(data["Name"]).url)
            embed.add_field(name="Tier", value=TIER_LIST[jcard["t"]])
            embed.add_field(name="Max Stacks", value=data["MaxStacks"])
            embed.add_field(
                name="Base Chance", value=str(round(float(data["Chance"]) * 100)) + "%"
            )
            embed.add_field(name="Max Level", value=data["MaxLevel"])
        await ctx.send("", embed=embed)

    @taptitans.command(
        name="deck", aliases=["decks"], case_insensitive=True, usage="deckname"
    )
    async def tt_deck(self, ctx, *deck):
        "Shows you some of the best tap titans deck combinations available."
        crimtain = await self.bot.fetch_user(190222871254007808)
        deck, data = await TTDeck().convert(ctx, " ".join(deck))
        if not deck or deck is None:
            embed = discord.Embed(
                title="Avaliable Decks",
                description=f"Thanks to {crimtain} for helping to come up with these decks.",
                color=0x186281,
            )
            for key in RAID_DECKS.keys():
                embed.add_field(
                    name=f"{key.title()} Deck",
                    value="\n".join(f"{self.emoji(c)} {c}" for c in RAID_DECKS[key][0]),
                )
        else:
            embed = discord.Embed(title=deck.title(), description=data[2])
            embed.add_field(
                name="Core Cards",
                value=", ".join([f"{self.emoji(d)} {d}" for d in data[0]]),
                inline=False,
            )
            if data[1]:
                embed.add_field(
                    name="Optional Cards",
                    value=", ".join([f"{self.emoji(d)} {d}" for d in data[1]]),
                    inline=False,
                )
        await ctx.send("", embed=embed)

    @taptitans.command(name="optimizers", aliases=["opti", "optimisers", "optis"])
    async def tt_opti(self, ctx):
        "Displays a link to TT2 optimisers."
        t_url = "<https://tinyurl.com/{}>"
        await ctx.send(
            "**List of TapTitans2 Optimizers**\nThese links should be useful in helping you best level your skill tree and artifacts.\n**Mmlh Skill Point Optimizer:** {}\n**Mmlh Artifact Optimizer:** {}\n**Parrot SP/Arti Optimizer:** {}".format(
                t_url.format("spoptimiser"),
                t_url.format("artoptimiser"),
                t_url.format("TT2Optimizer"),
            )
        )

    @taptitans.command(name="compendium", aliases=["comp"])
    async def tt_compendium(self, ctx):
        "Displays a link to the TT2 Compendium site."
        await ctx.send(
            "**TapTitans2 Compendium**\nThis site made by the Compendium Team provides great sample builds, guides, & tools, whether you're new or a veteran player.\n<https://tt2-compendium.herokuapp.com>"
        )

    @taptitans.group(name="hero", case_insensitive=True)
    async def tt_hero(self):
        return

    @taptitans.group(name="equip", case_insensitive=True)
    async def tt_equip(self):
        return

    @taptitans.group(
        name="artifact",
        aliases=["arti", "arts", "artifacts", "a", "art"],
        invoke_without_command=True,
    )
    async def tt_artifacts(
        self,
        ctx,
        artifact: Optional[tt2.TTArtifact],
        lvl_from: Optional[str],
        lvl_to: Optional[str],
    ):
        if not artifact or artifact is None:
            embed = discord.Embed(
                title="TT2 Artifacts",
                description="A list of artifacts from Tap Titans 2, sorted by boost type.",
            )
            for bonus_type in set([x["BonusIcon"] for x in self.arts]):
                embed.add_field(
                    name=BONUS_MAP.get(bonus_type, bonus_type),
                    value=", ".join(
                        [a["Name"] for a in self.arts if a["BonusIcon"] == bonus_type]
                    ),
                    inline=False,
                )
            await ctx.send("", embed=embed)
        arti, data = artifact
        emoji = self.emoji(data["Name"])
        id = data["ArtifactID"].replace("Artifact", "")
        b, g, r = COLOURS[self.snake(arti)]
        embed = discord.Embed(
            title=f"{emoji} {data['Name']} (ID: {id})",
            description="{} is a **{}** artifact.".format(
                data["Name"], BONUS_MAP.get(data["BonusIcon"])
            ),
            color=discord.Color.from_rgb(*[floor(c) for c in [r, g, b]]),
        )
        embed.set_thumbnail(url=str(emoji.url).replace(".gif", ".png"))
        embed.add_field(
            name="Max Level", value=str(int(data["MaxLevel"]) or "∞"), inline=False
        )
        embed.add_field(
            name="Bonus Type",
            value=" ".join(re.findall("[A-Z][^A-Z]*", data["BonusType"])),
            inline=False,
        )
        if lvl_from is not None:
            lvl_from = Decimal(lvl_from)
            effect1 = await tt2.artifact_boost(
                lvl_from,
                Decimal(data["EffectPerLevel"]),
                Decimal(data["GrowthExpo"]),
                bos=data["Name"] == "Book of Shadows" and True or False,
            )
            embed.add_field(
                name=f"Effect at lvl {lvl_from}", value=str(effect1), inline=False
            )
        if lvl_to is not None:
            lvl_to = Decimal(lvl_to)
            effect2 = await tt2.artifact_boost(
                lvl_to,
                Decimal(data["EffectPerLevel"]),
                Decimal(data["GrowthExpo"]),
                bos=data["Name"] == "Book of Shadows" and True or False,
            )
            embed.add_field(
                name=f"Effect at lvl {lvl_to}", value=str(effect2), inline=False
            )
            embed.add_field(name="Difference", value=f"{lvl_to/lvl_from}x boost")
        await ctx.send("", embed=embed)

    @tt_artifacts.command(name="bonus", aliases=["b"])
    async def tt_artifacts_bonus(self, ctx, *bonus: Optional[str]):
        bonuses = set([x["BonusIcon"] for x in self.arts])
        if not bonus or bonus is None:
            bonus = ""
        else:
            bonus = " ".join(bonus)
        if not bonus.lower() in [BONUS_MAP.get(b, b).lower() for b in bonuses]:
            raise cmd.BadArgument(
                "Valid bonus types are: {}".format(
                    ", ".join([f"**{BONUS_MAP.get(b, b)}**" for b in bonuses])
                )
            )
        bonus = next(
            (b for b, v in BONUS_MAP.items() if v.lower() == bonus.lower()), None
        )
        arts = [a for a in self.arts if a["BonusIcon"] == bonus]
        embed = discord.Embed(
            title=f"{BONUS_MAP.get(bonus, bonus)} Artifacts",
            description="\n".join(f"{self.emoji(a['Name'])} {a['Name']}" for a in arts),
        )
        await ctx.send("", embed=embed)

    # @tt_artifacts.command(name="build")
    # async def tt_artifacts_build(self, ctx, build: Optional[str]):
    #     if not build:
    #         await ctx.send("List of builds for searching: ")

    # @taptitans.group(name="enhancement", case_insensitive=True)
    # async def tt_enhance(self):
    #     return

    # @taptitans.group(name="enchant", case_insensitive=True)
    # async def tt_enchant(self):
    #     return

    async def titancount(self, stage, ip_, ab_, snap):
        "calculate titancount at any given stage"
        return round(max((stage // 500 * 2 + 8 - (ip_ + ab_)) / max(2 * snap, 1), 1))

    @taptitans.command(
        name="titancount",
        aliases=["titans", "count"],
        case_insensitive=True,
        usage="stage ip ab snaps",
    )
    async def tt_titancount(
        self, ctx, stage: int = 10000, ip: int = 30, ab: int = 5, snap: int = 0
    ):
        "Shows you how many titans there would be at any given stage."
        if any([x for x in [stage, ip, ab] if x < 0]):
            raise cmd.BadArgument
        count = await self.titancount(stage, ip, ab, snap)
        await ctx.send(
            "Titan count at stage {} (IP {}, AB {}, {} Snap{} active) would be: {}".format(
                stage, ip, ab, snap, snap != 1 and "s", count
            )
        )

    @taptitans.command(
        name="edskip",
        aliases=["ed"],
        usage="stage ip mystic_impact arcain_bargain anni_plat",
    )
    async def tt_ed(
        self,
        ctx,
        stage: int = 1,
        ip: Optional[int] = 0,
        mystic_impact: Optional[int] = 0,
        arcane_bargain: Optional[int] = 0,
        anniversary_platinum: Optional[float] = 1.0,
    ):
        "Optimal ed calculator"
        count = await self.titancount(stage, ip, arcane_bargain, 0)
        count2 = floor(count / 2)
        current_skip = mystic_impact + arcane_bargain
        ed_boosts = [
            0,
            1,
            2,
            3,
            4,
            6,
            8,
            10,
            12,
            14,
            16,
            18,
            20,
            23,
            26,
            29,
            33,
            38,
            44,
            51,
            59,
            68,
            78,
            89,
            101,
        ]
        result = 0
        while current_skip * anniversary_platinum < count2 and result < 25:
            current_skip = mystic_impact + arcane_bargain + ed_boosts[result]
            result += 1
        icon = self.emoji("edskip")
        await ctx.send(
            f"{icon} Optimal ED at stage **{stage}** ({count} titans) is: **{result}**."
        )

    # @taptitans.group(name="titanlord", case_insensitive=True)
    # async def tt_titanlord(self):
    #     return

    @taptitans.group(name="skill", case_insensitive=True, aliases=["skills", "s"])
    async def tt_skill(self, ctx, skill: Optional[tt2.TTSkill], lvl: Optional[int] = 0):
        "Shows you info about tap titans skills."
        if not skill or skill is None:
            emoji = self.emoji("skill_tree")
            embed = discord.Embed(
                title=f"{emoji} List of TT2 Skills",
                description="TT2 Skills sorted by skill tree.",
                color=int("0x{}".format(choice(list(SKILL_COLOURS.values()))), 16),
            )
            embed.set_thumbnail(url=emoji.url)
            for branch in ["Red", "Yellow", "Blue", "Green"]:
                embed.add_field(
                    name=TREE_MAP[branch],
                    value="\n".join(
                        [
                            f"{self.emoji(s['Name'])} {s['Name']}"
                            for s in self.skills
                            if s["Branch"] == f"Branch{branch}"
                        ]
                    ),
                )
        else:
            skill, data = skill
            desc = [x for x in SKILL_TREE if x.lower() == data["TalentID"].lower()][0]
            emoji = self.emoji(data["Name"])
            embed = discord.Embed(
                title=f"{emoji} {data['Name']}",
                description="\n".join(SKILL_TREE[desc]),
                color=int(
                    f'0x{SKILL_COLOURS[data["Branch"].lower().replace("branch", "")]}',
                    16,
                ),
            )
            embed.add_field(name="Tier", value=data["Tier"])
            embed.add_field(name="Max Level", value=data["MaxLevel"])
            embed.add_field(name="SP required to unlock", value=data["SPReq"])
            embed.set_thumbnail(url=emoji.url)
            if lvl:
                level = data.get(f"A{lvl}", None)
                if level and Decimal(level):
                    embed.add_field(
                        name=f"Effect at level {lvl}", value=level, inline=False
                    )
                    embed.add_field(
                        name=f"SP Cost for level {lvl}", value=data[f"C{lvl-1}"]
                    )
                    embed.add_field(
                        name=f"Cumulative SP cost for level {lvl}",
                        value="{}".format(
                            sum([int(data[f"C{x}"]) for x in range(0, lvl)])
                        ),
                    )
        await ctx.send("", embed=embed)

    @taptitans.command(name="bonuses", aliases=["bonus"])
    async def tt_bonuses(self, ctx):
        result = []
        icon = self.emoji("tourney_green")
        for b in BONUSES:
            result.append(f"{self.emoji(b[1])} {b[0]}")
        embed = discord.Embed(
            title=f"{icon} TT2 Tournament Bonuses",
            description="\n".join(result),
            color=0x75D950,
        )
        embed.set_thumbnail(url=icon.url)
        await ctx.send("", embed=embed)

    @taptitans.command(
        name="tournament", aliases=["tournaments", "tourneys", "tourney"], usage="next"
    )
    async def tt_tournaments(self, ctx, last: Optional[int] = 3):
        (
            "Displays a forecast of upcoming Tap Titans 2 tournaments.\n"
            "Icon colour will indicate tournament status. Live = blue. Not live = red.\n"
            "You can extend the forecast up to 10 future tournaments with the <next> parameter."
        )
        if last not in range(1, 11):
            raise cmd.BadArgument("Prediction is too far into the future.")
        if ctx.invoked_with[-1] != "s":
            last = 1
        prizes = "hero_weapon skill_point crafting_shard"
        result, i, now = [], 0, arrow.utcnow()
        origin = arrow.get(1532242116)
        tourneys, _ = divmod((now - origin).days, 3.5)
        tourneys = int(round(tourneys)) + 1
        current = int(now.format("d"))
        icon = "tourney_red"
        nxt = "opens"
        clr = 0xED2110
        if current in [1, 5]:
            shifter = 2
        elif current in [2, 6]:
            shifter = 1
        elif current in [3, 7]:
            shifter = 0
            icon = "tourney"
            nxt = "closes"
            clr = 0x1C7CA1
            tourneys = tourneys - 1
        elif current in [4]:
            shifter = 3
        desc = ""
        if last == 1:
            start_date = now.shift(days=shifter).replace(hour=0, minute=0, second=0)
            end_date = start_date.shift(days=1)
            if shifter == 0:
                delta = end_date - now
            else:
                delta = start_date - now
            _h, _m, _s = await get_hms(delta)
            desc = "Tournament **{}** in **{:02}**h **{:02}**m **{:02}**s.".format(
                nxt, _h, _m, _s
            )
        icon = self.emoji(icon)
        prizes = rotate(prizes.split(), tourneys % 3)
        bonuses = rotate(BONUSES, tourneys % 10)
        flipper = lambda i: current <= 3 and i % 2 or 0
        result = [
            (
                now.shift(days=i * 3.5 + shifter + flipper(i)).format("ddd DD MMM"),
                bonuses[i],
                prizes[i % 3],
            )
            for i in range(last)
        ]
        embed = discord.Embed(
            title=f"{icon} TT2 Tournament Forecast", description=desc, color=clr
        )
        for r in result:
            embed.add_field(
                name=r[0],
                value="{} {}\n{} {}".format(
                    self.emoji(r[1][1]),
                    r[1][0],
                    self.emoji(r[2]),
                    r[2].replace("_", " ").title() + "s",
                ),
                inline=False,
            )
        embed.set_thumbnail(url=icon.url)
        await ctx.send("", embed=embed)

    @taptitans.command(name="convert", aliases=["cvt"], usage="value")
    async def tt_convert(self, ctx, val: Optional[str] = "1e+5000"):
        (
            "Allows you to convert a scientific/letter notation into the opposite version.\n"
            "The bot will automagically figure out which way you want to convert.\n"
        )

        result, f, t = None, "scientific", "letter"
        mode = await ttconvert_discover(val)
        if mode == 0:
            result = await ttconvert_from_scientific(val)
        elif mode == 1:
            result = await ttconvert_to_scientific(val)
            f, t = "letter", "scientific"
        icon = self.emoji("orange_equals")
        embed = discord.Embed(title="TT2 notation conversion", color=0xF89D2A)
        embed.add_field(name=f"From {f}", value=val)
        embed.add_field(name=f"To {t}", value=result)
        embed.set_thumbnail(url=icon.url)
        await ctx.send("", embed=embed)

    @taptitans.command(
        name="gold", aliases=["goldsource", "goldsources"], usage="<kind>"
    )
    async def tt_gold(self, ctx, kind: Optional[str]):
        "Displays optimal artifacts required for a specific gold source."
        taco = await self.bot.fetch_user(381376462189625344)
        if not kind or kind.lower() not in GOLD_SOURCES.keys():
            ebizu = self.emoji("coins of ebizu")
            embed = discord.Embed(
                title=f"{ebizu} TT2 gold sources",
                description="\n".join(
                    [f"{self.emoji(val[2])} {k}" for k, val in GOLD_SOURCES.items()]
                ),
                color=0xE2BB39,
            )
            embed.set_thumbnail(url=str(ebizu.url).replace(".gif", ".png"))
        else:
            desc, arts, img, color = GOLD_SOURCES[kind.lower()]
            img = self.emoji(img)
            embed = discord.Embed(
                title=f"{img} Gold artifacts for {kind.title()} build",
                description=desc,
                color=int(f"0x{color}", 16),
            )
            embed.add_field(
                name="Artifacts",
                value="\n".join([f"{self.emoji(a)} - {a}" for a in arts]),
            )
            embed.set_thumbnail(url=img.url)
        await ctx.send("", embed=embed)

    @taptitans.group(name="my", invoke_without_command=True)
    async def tt_my(self, ctx):
        return

    @tt_my.command(name="code", aliases=["sc"])
    async def tt_my_code(self, ctx, code):
        code = code.lower().strip()
        if not 4 < len(code) < 10:
            raise cmd.BadArgument("Invalid code supplied.")
        dbc = await self.bot.db.hget("tt:psc", code)
        if dbc is not None:
            raise cmd.BadArgument(
                "Code already clamed. Visit <https://discord.gg/WvcryZW>!"
            )
        await self.bot.db.hset("tt:psc", code, ctx.author.id)
        await self.bot.db.hset(f"{ctx.author.id}:tt", "sc", code)
        await ctx.send(
            f":white_check_mark: Registered code **{code}** to **{ctx.author}**."
        )

    @tt_my.command(name="raidlevel", aliases=["prl"])
    async def tt_my_prl(self, ctx, prl: Optional[int]):
        if prl is not None:
            await self.bot.db.hset(f"{ctx.author.id}:tt", "prl", prl)
            await ctx.send(
                f":white_check_mark: Set **{ctx.author}**'s raid level to **{prl}**."
            )
        else:
            prl = await self.bot.db.hget(f"{ctx.author.id}:tt", "prl")
            if not prl or prl is None:
                raise cmd.BadArgument(f"**{ctx.author}** has no raid level set.")
            await ctx.send(f"{ctx.author}'s raid level is **{prl}**.")

    @tt_my.command(name="totalcardlevel", aliases=["tcl", "cardlevel"])
    async def tt_my_prl(self, ctx, prl: Optional[int]):
        if prl is not None:
            await self.bot.db.hset(f"{ctx.author.id}:tt", "tcl", prl)
            await ctx.send(
                f":white_check_mark: Set **{ctx.author}**'s total card level to **{prl}**."
            )
        else:
            prl = await self.bot.db.hget(f"{ctx.author.id}:tt", "tcl")
            if not prl or prl is None:
                raise cmd.BadArgument(f"**{ctx.author}** has no total card level set.")
            await ctx.send(f"{ctx.author}'s total card level is **{prl}**.")


def setup(bot):
    bot.add_cog(TapTitansModule(bot))
