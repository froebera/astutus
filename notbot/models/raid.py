from .model_base import ModelBase


class Raid(ModelBase):
    def __init__(self, id, started_at, cleared_at, guild_id):
        self.id = id
        self.started_at = started_at
        self.cleared_at = cleared_at
        self.guild_id = guild_id
