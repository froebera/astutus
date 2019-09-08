import logging
import arrow

from ..context import Context, Module
from ..db import (
    RaidDao,
    get_raid_dao,
    get_raid_postgres_dao,
    get_postgres_connection,
    get_redis_connection,
)
from .queue_service import QueueService, get_queue_service
from ..exceptions import (
    RaidOnCooldown,
    RaidActive,
    NoRaidActive,
    RaidAlreadyCleared,
    RaidUnspawned,
)
from ..cogs.util import (
    RAID_COOLDOWN,
    RAID_SPAWN,
    RAID_ANNOUNCEMENTCHANNEL,
    RAID_COUNTDOWNMESSAGE,
    RAID_RESET,
    RAID_REMINDED,
)

from ..cogs.util import get_hms

MODULE_NAME = "raid_service"
logger = logging.getLogger(__name__)


class RaidService(Module):
    def __init__(self, context: Context):
        self.raid_dao = get_raid_dao(context)
        self.queue_service = get_queue_service(context)
        self.raid_postgres_dao = get_raid_postgres_dao(context)
        self.postgres_connection = get_postgres_connection(context)
        self.redis_connection = get_redis_connection(context)

    def get_name(self):
        return MODULE_NAME

    async def get_announcement_channel_id(self, guild_id):
        return await self.raid_dao.get_announcement_channel_id(guild_id)

    async def start_raid(self, guild_id, raid_start: arrow.Arrow):
        logger.debug("start_raid, raid_start: %s", raid_start)
        raid_config = await self.raid_dao.get_raid_configuration(guild_id)
        now = arrow.utcnow()

        cooldown_timestamp = raid_config.get(RAID_COOLDOWN, None)
        spawn = raid_config.get(RAID_SPAWN, None)

        if cooldown_timestamp:
            cooldown = arrow.get(cooldown_timestamp)
            if cooldown > now:
                raise RaidOnCooldown()

        if spawn:
            raise RaidActive()

        await self.raid_postgres_dao.create_raid_stat_entry(guild_id, raid_start)
        await self._clear_current_raid_data(guild_id)
        await self.raid_dao.set_raid_spawn(guild_id, raid_start.timestamp)

    async def clear_raid(self, guild_id, raid_cooldown_end: arrow.Arrow):
        """
        cleares the current raid ( resets redis stuff )
        sets the cleared at for the current active raid in postgres ( used for the stat upload,
        since that is bound to a specific raid )
        """
        logger.debug("clear_raid: raid_cooldown_end: %s", raid_cooldown_end)
        raid_config = await self.raid_dao.get_raid_configuration(guild_id)
        spawn_timestamp = raid_config.get(RAID_SPAWN, 0)
        cooldown_timestamp = raid_config.get(RAID_COOLDOWN, 0)

        now = arrow.utcnow()
        spawn = arrow.get(spawn_timestamp)

        if not spawn_timestamp and not cooldown_timestamp:
            raise NoRaidActive()

        if cooldown_timestamp:
            raise RaidAlreadyCleared()

        if now < spawn:
            raise RaidUnspawned()

        delta_now_cd = raid_cooldown_end - now
        logger.debug(
            "clear_raid: time until raid cooldown ends from now %s", delta_now_cd
        )

        # ~2 secs for delays and stuff
        raid_cooldown_start = raid_cooldown_end.shift(minutes=-59, seconds=-59)
        time_needed_to_clear = raid_cooldown_start - spawn

        logger.debug(
            "clear_raid: raid cooldown started at %s, time needed to clear raid: %s",
            raid_cooldown_start,
            time_needed_to_clear,
        )

        if spawn > raid_cooldown_start:
            logger.warning(
                "clear_raid: something went wrong :o spawn %s is after raid cooldown start %s",
                spawn,
                raid_cooldown_start,
            )
            raise ValueError("Raid cooldown must be 60m after spawn")

        await self.raid_postgres_dao.complete_last_raid_stat_entry(
            guild_id, raid_cooldown_start
        )

        await self._clear_current_raid_data(guild_id)
        await self.raid_dao.set_raid_cooldown(guild_id, raid_cooldown_end.timestamp)

        return time_needed_to_clear

    async def cancel_raid(self, guild_id):
        raid_config = await self.get_raid_configuration(guild_id)
        spawn = raid_config.get(RAID_SPAWN, None)
        cooldown = raid_config.get(RAID_COOLDOWN, None)
        if not any([spawn, cooldown]):
            raise NoRaidActive()

        await self.raid_postgres_dao.delete_last_raid_entry(guild_id)
        await self._clear_current_raid_data(guild_id)

    async def get_raid_configuration(self, guild_id):
        return await self.raid_dao.get_raid_configuration(guild_id)

    async def _clear_current_raid_data(self, guild_id):
        for k in [
            RAID_COUNTDOWNMESSAGE,
            RAID_SPAWN,
            RAID_RESET,
            RAID_REMINDED,
            RAID_COOLDOWN,
        ]:
            await self.raid_dao.del_key(guild_id, k)

        await self.queue_service.reset_queue(guild_id, "default")


def get_raid_service(context: Context) -> RaidService:
    return context.get_or_register_module(MODULE_NAME, lambda: RaidService(context))
