from notbot.context import Context, Module
from .redis_connection import RedisConnection, get_redis_connection

MODULE_NAME = "raid_stats_dao"


class RaidStatDao(Module):
    def __init__(self):
        self.redis_connection: RedisConnection = None

    def get_name(self):
        return MODULE_NAME

    def start(self, context):
        self.redis_connection = get_redis_connection(context).get_connection()

    def save_raid_stats(self, raid_stats):
        pass


def get_raid_stats_dao(context: Context) -> RaidStatDao:
    return context.get_module(MODULE_NAME)
