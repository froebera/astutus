from .model_base import ModelBase


class TitanKillPattern(ModelBase):
    def __init__(self, name, pattern: str, armor_multiplier):
        self.name = name
        self.pattern = pattern
        self.armor_multiplier = armor_multiplier

    def get_total_hp_multiplier(self):
        return self.armor_multiplier + 1