from csv import DictReader
from logging import getLogger
from typing import List

from notbot.context import Context, Module
from notbot.models import TitanInfo, TitanKillPattern, RaidInfo
from notbot.exceptions import RaidInfoNotFound, InvalidTitanCount, InvalidTitansForRaid

MODULE_NAME = "raid_info_service"

logger = getLogger(__name__)


class RaidInfoService(Module):
    def __init__(self, context: Context):
        self.kill_patterns: List[TitanKillPattern] = []
        self.raid_infos: List[RaidInfo] = []

    def get_name(self):
        return MODULE_NAME

    def start(self):
        self.create_cache()

    def create_cache(self):
        logger.debug("Loading titan kill patterns")
        with open(f"notbot/data/raid/raid_titan_health.csv", mode="r") as csvfile:
            reader = DictReader(csvfile, delimiter=";")
            for row in reader:
                titan_info = TitanInfo(
                    row["Name"],
                    int(row["BodyTorso"]),
                    int(row["BodyHead"]),
                    int(row["BodyArms"]),
                    int(row["BodyLegs"]),
                    int(row["ArmourTorso"]),
                    int(row["ArmourHead"]),
                    int(row["ArmourArms"]),
                    int(row["ArmourLegs"]),
                )
                self.kill_patterns.append(
                    self.map_row_to_titan_kill_pattern(titan_info)
                )

        logger.debug("Loading raid info")
        with open("notbot/data/raid/raid_info.csv") as csvfile:
            reader = DictReader(csvfile, delimiter=";")
            for row in reader:
                raid_info = RaidInfo(
                    int(row["Tier"]),
                    int(row["Level"]),
                    int(row["Ticket Cost"]),
                    int(row["Ticket Reward"]),
                    int(row["Clan XP Rewards"]),
                    int(row["Player XP Reward"]),
                    int(row["Dust Reward"]),
                    int(row["Cards reward"]),
                    int(row["Scroll Reward"]),
                    int(row["Fortune Scroll Reward"]),
                    int(row["Attacks Per Rest"]),
                    int(row["Titan Base HP"].replace(",", "")),
                    int(row["Titan Count"]),
                    int(row["Total HP"].replace(",", "")),
                    row["Titan Lord Type"].split(","),
                )
                self.raid_infos.append(raid_info)

    def map_row_to_titan_kill_pattern(self, titan_info: TitanInfo):
        part_health = []
        part_armor = []

        part_health.append(titan_info.torso_health)
        part_health.append(titan_info.head_health)

        part_armor.append(titan_info.torso_armor)
        part_armor.append(titan_info.head_armor)

        for i in range(4):
            part_health.append(titan_info.arm_health / 4)
            part_armor.append(titan_info.arm_armor / 4)

        for i in range(2):
            part_health.append(titan_info.leg_health / 2)
            part_armor.append(titan_info.leg_armor / 2)

        all_kill_patterns = []
        for i in range(1, 1 << len(part_health)):
            _sum = 0
            for j in range(len(part_health)):
                if ((i >> j) & 1) == 1:
                    _sum += part_health[j]

            if _sum >= 100:
                parts = []
                for j in range(len(part_health)):
                    if (i & (1 << j)) > 0:
                        parts.append(j)
                all_kill_patterns.append(parts)

        patterns_base_health_scaling = []
        for idx, pattern in enumerate(all_kill_patterns):
            total_pattern_hitpoints = 0
            for part in pattern:
                p = part
                p_hp = part_health[p]
                p_armor = part_armor[p]

                total_pattern_hitpoints = total_pattern_hitpoints + p_hp + p_armor
            patterns_base_health_scaling.append((idx, total_pattern_hitpoints))

        patterns_sorted = sorted(patterns_base_health_scaling, key=lambda x: x[1])
        most_efficient_pattern_idx, base_hp_multiplier = patterns_sorted[0]
        base_hp_multiplier /= 100

        parts = ["Torso", "Head", "Arm", "Arm", "Arm", "Arm", "Leg", "Leg"]
        p = []
        for part in all_kill_patterns[most_efficient_pattern_idx]:
            p.append(parts[part])

        logger.debug(
            "Most efficient kill pattern for %s (total hp to kill: %s): %s",
            titan_info.name,
            base_hp_multiplier,
            ", ".join(p),
        )

        return TitanKillPattern(titan_info.name, ", ".join(p), base_hp_multiplier)

    def get_titan_kill_pattern(self, titan_name: str):
        for pattern in self.kill_patterns:
            if pattern.name == titan_name:
                return pattern

        return None

    def get_raid_info(self, tier: int, level: int):
        return next(
            (ri for ri in self.raid_infos if (ri.tier == tier and ri.level == level)),
            None,
        )

    def get_damage_needed_to_clear(self, tier: int, level: int, titan_types: List[str]):
        raid_info = self.get_raid_info(tier, level)

        if not raid_info:
            raise RaidInfoNotFound(f"Could not find raid {tier}-{level}")
        else:
            if raid_info.titan_count != len(titan_types):
                raise InvalidTitanCount(
                    f"Raid {tier}-{level} has {raid_info.titan_count} titans ({', '.join(raid_info.titan_lord_type)})"
                )

            if any(tl not in raid_info.titan_lord_type for tl in titan_types):
                raise InvalidTitansForRaid(
                    f"Invalid titan supplied. Valid titans for raid {tier}-{level}: {raid_info.titan_lord_type}"
                )

            patterns = list(
                map(
                    lambda x: next(kp for kp in self.kill_patterns if kp.name == x),
                    titan_types,
                )
            )

            total_hp_to_kill = 0
            for p in patterns:
                damage_needed = raid_info.titan_base_hp * p.base_hp_multiplier
                total_hp_to_kill += damage_needed

            total_hp_to_kill = int(total_hp_to_kill)
            return total_hp_to_kill


def get_raid_info_service(context: Context) -> RaidInfoService:
    return context.get_or_register_module(MODULE_NAME, lambda: RaidInfoService(context))
