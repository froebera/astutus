import logging
import asyncio
from math import pow
from ..context import Context, Module
from ..db import get_redis_connection, Redis
from notbot.cogs.util import (
    EFFICIENCY_KEY,
    EFFICIENCY_BASE,
    EFFICIENCY_CARD_PERC,
    EFFICIENCY_TRESHOLD1,
    EFFICIENCY_TRESHOLD2,
    EFFICIENCY_REDUCTION1,
    EFFICIENCY_REDUCTION2,
    EFFICIENCY_CARDS_TOTAL,
    EFFICIENCY_LETHAL_BONUS,
)


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
        self.redis_connection: Redis

        self.efficiency_config = {}

    def get_name(self):
        return MODULE_NAME

    def start(self):
        self.redis_connection = self.redis_connection_module.get_connection()

        loop = asyncio.get_event_loop()

        efficiency_config = loop.run_until_complete(
            self.redis_connection.hgetall(EFFICIENCY_KEY)
        )

        self.efficiency_config[EFFICIENCY_BASE] = int(
            efficiency_config.get(
                EFFICIENCY_BASE, 320
            )
        )
        self.efficiency_config[EFFICIENCY_CARD_PERC] = float(
            efficiency_config.get(
                EFFICIENCY_CARD_PERC, 1.00795
            )
        )
        self.efficiency_config[EFFICIENCY_TRESHOLD1] = int(
            efficiency_config.get(
                EFFICIENCY_TRESHOLD1, 50
            )
        )
        self.efficiency_config[EFFICIENCY_TRESHOLD2] = int(
            efficiency_config.get(
                EFFICIENCY_TRESHOLD2, 180
            )
        )
        self.efficiency_config[EFFICIENCY_REDUCTION1] = float(
            efficiency_config.get(
                EFFICIENCY_REDUCTION1, 0.85
            )
        )
        self.efficiency_config[EFFICIENCY_REDUCTION2] = float(
            efficiency_config.get(
                EFFICIENCY_REDUCTION2, 0.57
            )
        )
        self.efficiency_config[EFFICIENCY_CARDS_TOTAL] = int(
            efficiency_config.get(
                EFFICIENCY_CARDS_TOTAL, 23
            )
        )
        self.efficiency_config[EFFICIENCY_LETHAL_BONUS] = float(
            efficiency_config.get(
                EFFICIENCY_LETHAL_BONUS, 0.32
            )
        )

        logger.debug("cached efficiency configuration: %s", self.efficiency_config)

    def get_efficiency_config(self):
        return self.efficiency_config

    async def set_efficiency_config_value(self, key, value):
        await self.redis_connection.hset(EFFICIENCY_KEY, key, value)
        self.efficiency_config[key] = value

    def calculate_estimated_damage(
        self, player_raid_level: int, total_card_levels: int
    ) -> int:
        cards_up_to_t1 = (
            self.efficiency_config[EFFICIENCY_TRESHOLD1]
            if total_card_levels >= self.efficiency_config[EFFICIENCY_TRESHOLD1]
            else total_card_levels
        )
        cards_between_t1_and_t2 = (
            0
            if total_card_levels <= self.efficiency_config[EFFICIENCY_TRESHOLD1]
            else (
                self.efficiency_config[EFFICIENCY_TRESHOLD2]
                - self.efficiency_config[EFFICIENCY_TRESHOLD1]
                if total_card_levels >= self.efficiency_config[EFFICIENCY_TRESHOLD2]
                else total_card_levels - self.efficiency_config[EFFICIENCY_TRESHOLD1]
            )
        )
        cards_above_t2 = (
            0
            if total_card_levels <= self.efficiency_config[EFFICIENCY_TRESHOLD2]
            else total_card_levels - self.efficiency_config[EFFICIENCY_TRESHOLD2]
        )

        estimated_dmg = (
            self.efficiency_config[EFFICIENCY_BASE]
            * (player_raid_level / 100 + 0.99)
            * (
                1
                + pow(
                    self.efficiency_config[EFFICIENCY_CARD_PERC],
                    (cards_up_to_t1 - self.efficiency_config[EFFICIENCY_CARDS_TOTAL]),
                )
                - 1
                + pow(
                    self.efficiency_config[EFFICIENCY_CARD_PERC],
                    pow(
                        cards_between_t1_and_t2,
                        self.efficiency_config[EFFICIENCY_REDUCTION1],
                    ),
                )
                - 1
                + pow(
                    self.efficiency_config[EFFICIENCY_CARD_PERC],
                    pow(cards_above_t2, self.efficiency_config[EFFICIENCY_REDUCTION2]),
                )
                - 1
            )
        ) * 1000

        estimated_dmg: int = round(estimated_dmg)

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

    def calculate_efficiency(
        self, player_raid_level: int, total_card_levels: int, player_average_damage: int
    ) -> float:
        estimated_damage = self.calculate_estimated_damage(
            player_raid_level, total_card_levels
        )

        efficiency = player_average_damage / estimated_damage
        logger.debug(
            "Efficiency for avg dmg %s and estimated dmg %s = %s",
            player_average_damage,
            estimated_damage,
            efficiency,
        )

        return efficiency

    def calculate_efficiency_with_lethal_bonus(
        self,
        player_raid_level: int,
        total_card_levels: int,
        player_average_damage: int,
        max_attacks: int,
        player_attacks: int,
    ) -> float:
        bonus = self.calcualte_lethal_bonus(max_attacks, player_attacks)
        estimated_damage = self.calculate_estimated_damage(
            player_raid_level, total_card_levels
        )

        efficiency = player_average_damage * bonus / estimated_damage

        logger.debug(
            "Efficiency for avg dmg %s and estimated dmg %s ( with lethal bonus %s ) = %s",
            player_average_damage,
            estimated_damage,
            bonus,
            efficiency,
        )

        return efficiency

    def calcualte_lethal_bonus(self, max_attacks: int, player_attacks) -> int:
        gets_lethal_bonus = (
            player_attacks
            - max_attacks
            + (4 if max_attacks % 4 == 0 else max_attacks % 4)
            == 4
        )

        logger.debug(
            "Lethal bonus: Player with %s attacks ( max %s ) recieves lethal bonus ? %s",
            player_attacks,
            max_attacks,
            gets_lethal_bonus,
        )

        if max_attacks == 0 or player_attacks == 0:
            bonus = 1
        else:
            bonus = 1 + (self.efficiency_config[EFFICIENCY_LETHAL_BONUS] / max_attacks)

        logger.debug("Lethal bonus for %s attacks: %s ", max_attacks, bonus)

        if not gets_lethal_bonus:
            return 1

        return bonus


def get_efficiency_service(context: Context) -> EfficiencyService:
    return context.get_or_register_module(
        MODULE_NAME, lambda: EfficiencyService(context)
    )
