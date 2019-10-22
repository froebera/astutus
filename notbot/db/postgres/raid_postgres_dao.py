import logging
import arrow
from notbot.context import Context, Module
from .postgres_connection import get_postgres_connection
from .postgres_dao_base import PostgresDaoBase
from notbot.models import Raid, RaidPlayerAttack
from typing import List, Awaitable

MODULE_NAME = "raid_postgres_dao"
logger = logging.getLogger(__name__)


class RaidPostgresDao(PostgresDaoBase, Module):
    def get_name(self):
        return MODULE_NAME

    async def get_last_completed_raid(self, guild_id):
        async with self.connection() as connection:
            row = await connection.fetchrow(
                """
                SELECT r.*
                FROM raid r
                JOIN raid_player_attack rpa on rpa.raid_id = r.id
                WHERE
                    guild_id = $1
                GROUP BY r.id
                ORDER BY cleared_at DESC
                """,
                str(guild_id),
            )
            if not row:
                return None

            return self._map_row_to_raid_model(row)

    async def create_start_raid_stat_entry(self, guild_id, started_at: arrow.Arrow):
        async with self.connection() as connection:
            val: int = await connection.fetchval(
                """INSERT INTO raid(
                guild_id, started_at
            ) VALUES ($1, $2)
            RETURNING id;
            """,
                str(guild_id),
                started_at.datetime,
            )
            logger.debug("Created new raid stat entry with id %s", val)
            return val

    async def create_raid_stat_entry(
        self, guild_id, started_at: arrow.Arrow, cleared_at: arrow.Arrow
    ):
        async with self.connection() as connection:
            val: int = await connection.fetchval(
                """INSERT INTO raid(
                guild_id, started_at, cleared_at
            ) VALUES ($1, $2, $3)
            RETURNING id;
            """,
                str(guild_id),
                started_at.datetime,
                cleared_at.datetime,
            )
            logger.debug("Created new raid stat entry with id %s", val)
            return val

    async def complete_last_raid_stat_entry(self, guild_id, cleared_at: arrow.Arrow):
        async with self.connection() as connection:
            res = await connection.execute(
                """UPDATE raid
            SET cleared_at = $1
            WHERE guild_id = $2
            AND cleared_at IS NULL
            AND started_at IS NOT NULL;
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
            async with connection.transaction():
                result: List[Raid] = []
                async for row in connection.cursor(
                    """
                    SELECT r.*
                    FROM raid r
                    WHERE
                        r.guild_id = $1
                        AND NOT EXISTS (
                            SELECT DISTINCT raid_id FROM raid_player_attack WHERE raid_id = r.id
                        )
                        OR r.cleared_at IS NULL
                        OR r.started_at IS NULL
                    ORDER BY r.cleared_at DESC
                    LIMIT 10;
                    """,
                    str(guild_id),
                ):
                    result.append(self._map_row_to_raid_model(row))
                return result

    async def get_last_completed_raids(self, guild_id):
        async with self.connection() as connection:
            async with connection.transaction():
                result: List[Raid] = []
                async for row in connection.cursor(
                    """
                        SELECT r.*
                        FROM raid r
                        JOIN raid_player_attack rpa on rpa.raid_id = r.id
                        WHERE
                            r.guild_id = $1
                            AND r.cleared_at IS NOT NULL
                            AND r.started_at IS NOT NULL
                        GROUP BY r.id
                        ORDER BY r.started_at DESC
                        LIMIT 10;
                    """,
                    str(guild_id),
                ):
                    result.append(self._map_row_to_raid_model(row))

                return result

    async def has_raid_permission_and_raid_exists(self, guild_id, raid_id):
        async with self.connection() as connection:
            res = await connection.fetchval(
                """
                SELECT 1
                FROM raid
                WHERE
                guild_id = $1
                AND id = $2
                """,
                str(guild_id),
                raid_id,
            )
            return res == True

    async def get_raid_for_id(self, raid_id):
        async with self.connection() as connection:
            res = await connection.fetchrow(
                """
                SELECT *
                FROM raid
                WHERE
                    id = $1            
            """,
                raid_id,
            )

            return self._map_row_to_raid_model(res)

    async def delete_raid_entry(self, raid_id):
        async with self.connection() as connection:
            res = await connection.execute(
                """
                    DELETE
                    FROM raid
                    WHERE
                        id = $1
                """,
                raid_id,
            )
            print(res)

    def _map_row_to_raid_model(self, row) -> Raid:
        return Raid(
            int(row["id"]),
            arrow.get(row["started_at"]) if row["started_at"] else None,
            arrow.get(row["cleared_at"]) if row["cleared_at"] else None,
            row["guild_id"],
        )


def get_raid_postgres_dao(context: Context) -> RaidPostgresDao:
    return context.get_or_register_module(MODULE_NAME, lambda: RaidPostgresDao(context))
