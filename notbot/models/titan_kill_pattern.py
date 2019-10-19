from .model_base import ModelBase


class TitanKillPattern(ModelBase):
    def __init__(self, name, pattern: str, base_hp_multiplier):
        self.name = name
        self.pattern = pattern
        self.base_hp_multiplier = base_hp_multiplier
