from typing import List

from .raid import Raid
from .model_base import ModelBase
from .raid_player_attack import RaidPlayerAttack


class RaidAttacks(Raid):
    def __init__(
        self,
        id,
        started_at,
        cleared_at,
        guild_id,
        raid_player_attacks: List[RaidPlayerAttack],
    ):
        super().__init__(id, started_at, cleared_at, guild_id)
        self.raid_player_attacks = raid_player_attacks
