from typing import List
from .model_base import ModelBase


class RaidInfo(ModelBase):
    def __init__(
        self,
        tier: int,
        level: int,
        ticket_cost: int,
        ticket_reward: int,
        clan_xp_reward: int,
        player_xp_reward: int,
        dust_reward: int,
        cards_reward: int,
        scroll_reward: int,
        fortune_scroll_reward: int,
        attacks_per_reset: int,
        titan_base_hp: int,
        titan_count: int,
        total_hp: int,
        titan_lord_type: List[str],
    ):
        self.tier = tier
        self.level = level
        self.ticket_cost = ticket_cost
        self.ticket_reward = ticket_reward
        self.clan_xp_reward = clan_xp_reward
        self.player_xp_reward = player_xp_reward
        self.dust_reward = dust_reward
        self.cards_reward = cards_reward
        self.scroll_reward = scroll_reward
        self.fortune_scroll_reward = fortune_scroll_reward
        self.attacks_per_reset = attacks_per_reset
        self.titan_base_hp = titan_base_hp
        self.titan_count = titan_count
        self.total_hp = total_hp
        self.titan_lord_type = titan_lord_type
