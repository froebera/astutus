class RaidPlayerStat:
    def __init__(self, raid_id, player_id, total_card_levels, raid_level):
        self.player_id = player_id
        self.raid_id = raid_id
        self.total_card_levels = total_card_levels
        self.raid_level = raid_level

    def iter(self):
        return (self.raid_id, self.player_id, self.total_card_levels, self.raid_level)

