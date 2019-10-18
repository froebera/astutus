from csv import DictReader
from logging import getLogger
from typing import List

from notbot.context import Context, Module
from notbot.models import TitanInfo, TitanKillPattern

MODULE_NAME = "raid_info_service"

logger = getLogger(__name__)

class RaidInfoService(Module):
    def __init__(self, context: Context):
        self.kill_patterns: List[TitanKillPattern] = []

    def get_name(self):
        return MODULE_NAME

    def start(self):
        self.load_patterns()

    def load_patterns(self):
        with open(f"notbot/data/raid/raid_titan_health.csv", mode="r") as csvfile:
            reader = DictReader(csvfile)
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
                self.kill_patterns.append(self.map_row_to_titan_kill_pattern(titan_info))

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
            sum = 0
            for j in range(len(part_health)):
                if ((i >> j) & 1) == 1:
                    sum += part_health[j]

            if sum >= 100:
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
        
        parts = ["Torso", "Head", "Arm", "Arm", "Arm", "Arm", "Leg", "Leg"]
        p = []
        for part in all_kill_patterns[most_efficient_pattern_idx]:
            p.append(parts[part])
        logger.debug(
            "Most efficient kill pattern for %s (total hp to kill: %s): %s",
                titan_info.name, base_hp_multiplier, ", ".join(p)
            )

        return TitanKillPattern(titan_info.name, ", ".join(p), base_hp_multiplier)

    def get_titan_kill_pattern(self, titan_name: str):
        for pattern in self.kill_patterns:
            if pattern.name == titan_name:
                return pattern

        return None


def get_raid_info_service(context: Context) -> RaidInfoService:
    return context.get_or_register_module(MODULE_NAME, lambda: RaidInfoService(context))
