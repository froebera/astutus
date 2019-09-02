class RaidPlayerAttack:
    def __init__(
        self,
        raid_id: int,
        player_id: str,
        player_name: str,
        total_hits: int,
        total_dmg: int,
    ):
        self.raid_id = raid_id
        self.player_id = player_id
        self.player_name = player_name
        self.total_hits = total_hits
        self.total_dmg = total_dmg

    def iter(self):
        return (
            self.raid_id,
            self.player_id,
            self.player_name,
            self.total_hits,
            self.total_dmg,
        )
