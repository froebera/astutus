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

    async def get_last_cleared_raid(self, guild_id):
        pass

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

    async def save_raid_player_attacks(self, attacks: List[RaidPlayerAttack]):
        async with self.connection() as connection:
            await connection.executemany(
                """
                INSERT INTO raid_player_attack
                    (raid_id, player_id, player_name, total_hits, total_dmg)
                VALUES (
                    $1, $2, $3, $4, $5
                ) 
                """,
                [rpa.iter() for rpa in attacks],
            )

    async def check_if_attacks_exist(self, guild_id, raid_id):
        async with self.connection() as connection:
            res = await connection.fetchval(
                """
                SELECT 1
                FROM raid r
                JOIN raid_player_attack rpa
                    on rpa.raid_id = r.id
                WHERE
                r.guild_id = $1
                AND r.id = $2
                GROUP BY 1
                """,
                str(guild_id),
                raid_id,
            )
            return res == True

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

    def _map_row_to_raid_model(self, row) -> Raid:
        return Raid(
            row["id"],
            arrow.get(row["started_at"]) if row["started_at"] else None,
            arrow.get(row["cleared_at"]) if row["cleared_at"] else None,
            row["guild_id"],
        )


def get_raid_postgres_dao(context: Context) -> RaidPostgresDao:
    return context.get_or_register_module(MODULE_NAME, lambda: RaidPostgresDao(context))
