import logging
import arrow
from ..context import Context, Module
from .postgres_connection import get_postgres_connection

MODULE_NAME = "raid_postgres_dao"
logger = logging.getLogger(__name__)


class RaidPostgresDao(Module):
    def __init__(self, context: Context):
        self.postgres_connection = get_postgres_connection(context)

    def get_name(self):
        return MODULE_NAME

    async def create_raid_stat_entry(self, guild_id, started_at: arrow.Arrow):
        async with self.postgres_connection.pool.acquire() as connection:
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
        async with self.postgres_connection.pool.acquire() as connection:
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
        async with self.postgres_connection.pool.acquire() as connection:
            await connection.execute(
                """DELETE FROM raid
            WHERE guild_id = $1
            AND cleared_at IS NULL;
            """,
                str(guild_id),
            )
            logger.debug("Deleted all uncompleted raid entries for guild %s", guild_id)


def get_raid_postgres_dao(context: Context):
    return context.get_or_register_module(MODULE_NAME, lambda: RaidPostgresDao(context))
