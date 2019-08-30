from math import pow
from ..context import Context, Module

import logging

MODULE_NAME = "efficiency_service"

logger = logging.getLogger(__name__)


class EfficiencyService(Module):
    def __init__(self):
        self.base = 315
        self.card_perc = 1.00795
        self.treshold_1 = 50
        self.treshold_2 = 180
        self.reduction_1 = 0.85
        self.reduction_2 = 0.57
        self.cards_total = 23

    def get_name(self):
        return MODULE_NAME

    def start(self, context: Context):
        pass

    def calculate_estimated_damage(
        self, player_raid_level: int, total_card_levels: int
    ):
        cards_up_to_t1 = (
            self.treshold_1
            if total_card_levels >= self.treshold_1
            else total_card_levels
        )
        cards_between_t1_and_t2 = (
            0
            if total_card_levels <= self.treshold_1
            else (
                self.treshold_2 - self.treshold_1
                if total_card_levels >= self.treshold_2
                else total_card_levels - self.treshold_1
            )
        )
        cards_above_t2 = (
            0
            if total_card_levels <= self.treshold_2
            else total_card_levels - self.treshold_2
        )

        estimated_dmg = (
            self.base
            * (player_raid_level / 100 + 0.99)
            * (
                1
                + pow(self.card_perc, (cards_up_to_t1 - self.cards_total))
                - 1
                + pow(self.card_perc, pow(cards_between_t1_and_t2, self.reduction_1))
                - 1
                + pow(self.card_perc, pow(cards_above_t2, self.reduction_2))
                - 1
            )
        ) * 1000

        logger.debug(
            "Calculate Estimated DMG: PRL: %s, TCL: %s, Cards < Treshold1: %s, Cards between Treshold 1&2: %s, Cards above Treshold2: %s, Estimated DMG: %s",
            player_raid_level,
            total_card_levels,
            cards_up_to_t1,
            cards_between_t1_and_t2,
            cards_above_t2,
            estimated_dmg,
        )

        return estimated_dmg


def get_efficiency_service(context: Context) -> EfficiencyService:
    return context.get_module(MODULE_NAME)
