import logging
from ..context import Context, Module
from ..models import RaidPlayerAttack, RaidPlayerStat
from typing import List
from ..db import get_postgres_connection

MODULE_NAME = "raid_stat_service"
logger = logging.getLogger(__name__)


class RaidStatService(Module):
    def __init__(self):
        self.postgres_connection = None

    def get_name(self):
        return MODULE_NAME

    def start(self, context: Context):
        self.postgres_connection = get_postgres_connection(context)

    async def save_raid_player_attacks(self, attacks: List[RaidPlayerAttack]):
        async with self.postgres_connection.pool.acquire() as connection:
            # insert_statement = connection.prepare(
            #     """INSERT INTO raid_player_attack
            #            (player_id, raid_id, total_dmg, total_hits)
            #        VALUES (
            #            $1, $2, $3, $4
            #        )
            #     """
            # )

            # for attack in attacks:
            #     logger.debug(attack)
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

    async def save_raid_player_stats(self, stats: List[RaidPlayerStat]):
        async with self.postgres_connection.pool.acquire() as connection:
            await connection.executemany(
                """
                INSERT INTO raid_player_stats
                    (raid_id, player_id, total_card_levels, raid_level)
                VALUES (
                    $1, $2, $3, $4
                )
                """,
                [rps.iter() for rps in stats],
            )


def get_raid_stat_service(context: Context) -> RaidStatService:
    return context.get_module(MODULE_NAME)
