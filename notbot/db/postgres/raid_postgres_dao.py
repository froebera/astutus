import logging
import arrow
from notbot.context import Context, Module
from .postgres_connection import get_postgres_connection
from .postgres_dao_base import PostgresDaoBase

MODULE_NAME = "raid_postgres_dao"
logger = logging.getLogger(__name__)


class RaidPostgresDao(PostgresDaoBase, Module):
    def get_name(self):
        return MODULE_NAME

    async def create_raid_stat_entry(self, guild_id, started_at: arrow.Arrow):
        async with self.connection() as connection:
            val = await connection.fetchval(
                """INSERT INTO raid(
                guild_id, started_at
            ) VALUES ($1, $2)
            RETURNING id;
            """,
                str(guild_id),
                started_at.datetime,
            )
            logger.debug("Created new raid stat entry with id %s", val)

    async def complete_last_raid_stat_entry(self, guild_id, cleared_at: arrow.Arrow):
        async with self.connection() as connection:
            res = await connection.execute(
                """UPDATE raid
            SET cleared_at = $1
            WHERE guild_id = $2
            AND cleared_at IS NULL;
            """,
                cleared_at.datetime,
                str(guild_id),
            )
            logger.debug("Update result: %s", res)

    async def delete_last_raid_entry(self, guild_id):
        async with self.connection() as connection:
            await connection.execute(
                """DELETE FROM raid
            WHERE guild_id = $1
            AND cleared_at IS NULL;
            """,
                str(guild_id),
            )
            logger.debug("Deleted all uncompleted raid entries for guild %s", guild_id)

    async def get_uncompleted_raids(self, guild_id):
        async with self.connection() as connection:
            result = await connection.fetch(
                """
                SELECT r.*, count(rpa.*) as count_rpa, count(rps.*) as count_rps FROM raid r
                    LEFT JOIN raid_player_attack rpa on rpa.raid_id = r.id
                    LEFT JOIN raid_player_stats rps on rps.raid_id = r.id
                    WHERE r.guild_id = $1
                    GROUP by r.id
                    HAVING count(rpa.*) > 0
                    OR count(rps.*) > 0;
                """,
                str(guild_id),
            )

            return result


def get_raid_postgres_dao(context: Context):
    return context.get_or_register_module(MODULE_NAME, lambda: RaidPostgresDao(context))
