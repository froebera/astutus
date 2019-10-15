from notbot.context import Context, Module
from .postgres_dao_base import PostgresDaoBase
from notbot.models import RaidPlayerAttack
from typing import List

MODULE_NAME = "raid_stats_dao"


class RaidStatsDao(PostgresDaoBase, Module):
    def get_name(self):
        return MODULE_NAME

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

    async def get_raid_player_attacks_for_raid_id(self, raid_id):
        result: List[RaidPlayerAttack] = []
        async with self.connection() as connection:
            res = await connection.fetch(
                """
                SELECT *
                FROM raid_player_attack
                WHERE raid_id = $1
                """,
                raid_id,
            )
            for row in res:
                result.append(self._map_row_to_rpa_model(row))

        return result

    def _map_row_to_rpa_model(self, row) -> RaidPlayerAttack:
        return RaidPlayerAttack(
            row["raid_id"],
            row["player_id"],
            row["player_name"],
            row["total_hits"],
            row["total_dmg"],
        )


def get_raid_stats_dao(context: Context) -> RaidStatsDao:
    return context.get_or_register_module(MODULE_NAME, lambda: RaidStatsDao(context))
