from .model_base import ModelBase


class TitanInfo(ModelBase):
    def __init__(
        self,
        name,
        torso_health,
        head_health,
        arm_health,
        leg_health,
        torso_armor,
        head_armor,
        arm_armor,
        leg_armor,
    ):
        self.name = name
        self.torso_health = torso_health
        self.head_health = head_health
        self.arm_health = arm_health
        self.leg_health = leg_health

        # Armor stuff
        self.torso_armor = torso_armor
        self.head_armor = head_armor
        self.arm_armor = arm_armor
        self.leg_armor = leg_armor
