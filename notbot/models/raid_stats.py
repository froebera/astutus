class RaidStats:
    def __init__(
        self,
        min_dmg,
        max_dmg,
        avg_dmg,
        min_avg,
        max_avg,
        total_avg,
        min_hits,
        max_hits,
        total_dmg,
        attackers,
        started_at,
        cleared_at,
    ):
        self.min_dmg = min_dmg
        self.max_dmg = max_dmg
        self.avg_dmg = avg_dmg
        self.min_avg = min_avg
        self.max_avg = max_avg
        self.total_avg = total_avg
        self.min_hits = min_hits
        self.max_hits = max_hits
        self.total_dmg = total_dmg
        self.attackers = attackers
        self.started_at = started_at
        self.cleared_at = cleared_at

    def __str__(self):
        return "RaidStats(started_at: {}, cleared_at: {}, min_dmg: {}, max_dmg: {}, avg_dmg: {}, min_avg: {}, max_avg: {}, total_avg: {}, min_hits: {}, max_hits: {}, total_dmg: {}, attackers: {})".format(
            self.started_at,
            self.cleared_at,
            self.min_dmg,
            self.max_dmg,
            self.avg_dmg,
            self.min_avg,
            self.max_avg,
            self.total_avg,
            self.min_hits,
            self.max_hits,
            self.total_dmg,
            self.attackers,
        )
