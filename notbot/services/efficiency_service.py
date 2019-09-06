from math import pow
from ..context import Context, Module
from ..db import get_redis_connection, Redis
import asyncio
from notbot.cogs.util import (
    EFFICIENCY_KEY
    EFFICIENCY_BASE
    EFFICIENCY_CARD_PERC
    EFFICIENCY_TRESHOLD1
    EFFICIENCY_TRESHOLD2
    EFFICIENCY_REDUCTION1
    EFFICIENCY_REDUCTION2
    EFFICIENCY_CARDS_TOTAL
)

import logging

MODULE_NAME = "efficiency_service"

logger = logging.getLogger(__name__)


EFFICIENCY_CONFIG_KEYS = [
    EFFICIENCY_BASE,
    EFFICIENCY_CARD_PERC,
    EFFICIENCY_TRESHOLD1,
    EFFICIENCY_TRESHOLD2,
    EFFICIENCY_REDUCTION1,
    EFFICIENCY_REDUCTION2,
    EFFICIENCY_CARDS_TOTAL,
]


class EfficiencyService(Module):
    def __init__(self, context: Context):
        self.redis_connection_module = get_redis_connection(context)
        self.redis_connection: Redis = None

        self.efficiency_config = {}

    def get_name(self):
        return MODULE_NAME

    def start(self):
        self.redis_connection = self.redis_connection_module.get_connection()

        loop = asyncio.get_event_loop()

        efficiency_config = loop.run_until_complete(
            self.redis_connection.hgetall(EFFICIENCY_KEY)
        )

        self.efficiency_config[EFFICIENCY_BASE] = efficiency_config.get(
            EFFICIENCY_BASE, 320
        )
        self.efficiency_config[EFFICIENCY_CARD_PERC] = efficiency_config.get(
            EFFICIENCY_CARD_PERC, 1.00795
        )
        self.efficiency_config[EFFICIENCY_TRESHOLD1] = efficiency_config.get(
            EFFICIENCY_TRESHOLD1, 50
        )
        self.efficiency_config[EFFICIENCY_TRESHOLD2] = efficiency_config.get(
            EFFICIENCY_TRESHOLD2, 180
        )
        self.efficiency_config[EFFICIENCY_REDUCTION1] = efficiency_config.get(
            EFFICIENCY_REDUCTION1, 0.85
        )
        self.efficiency_config[EFFICIENCY_REDUCTION2] = efficiency_config.get(
            EFFICIENCY_REDUCTION2, 0.57
        )
        self.efficiency_config[EFFICIENCY_CARDS_TOTAL] = efficiency_config.get(
            EFFICIENCY_CARDS_TOTAL, 23
        )

        logger.debug("cached efficiency configuration: %s", self.efficiency_config)

    def get_efficiency_config(self):
        return self.efficiency_config

    async def set_efficiency_config_value(self, key, value):
        await self.redis_connection.hset(EFFICIENCY_KEY, key, value)
        self.efficiency_config.update[key] = value


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
    return context.get_or_register_module(
        MODULE_NAME, lambda: EfficiencyService(context)
    )
