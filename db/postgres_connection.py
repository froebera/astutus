from context import Context, Module
import asyncio
import asyncpg

MODULE_NAME = "postgres_connection"


class PostgresConnection(Module):
    def __init__(self, postgres_configuration):
        self.postgres_configuration = postgres_configuration
        self.pool = None

    def get_name(self):
        return MODULE_NAME

    def start(self, context: Context):
        uri = "{}://{}:{}@{}:{}/{}".format(
            self.postgres_configuration["protocol"] or "postgresql",
            self.postgres_configuration["username"],
            self.postgres_configuration["password"],
            self.postgres_configuration["host"],
            self.postgres_configuration["port"],
            self.postgres_configuration["database"],
        )

        loop = asyncio.get_event_loop()
        pool = loop.run_until_complete(init_db(uri))

        self.pool = pool

    def get_pool(self):
        return self.pool


def get_postgres_connection(context: Context) -> PostgresConnection:
    return context.get_module(MODULE_NAME)


async def init_db(uri):
    pool = await asyncpg.create_pool(
        dsn=uri, command_timeout=60, max_size=5, min_size=1
    )

    async with pool.acquire() as connection:
        await connection.execute(_raid_query)
        await connection.execute(_raid_attack_conclusion)
        await connection.execute(_raid_player_stats)

    return pool


_raid_query = """CREATE TABLE IF NOT EXISTS raid(
    id serial PRIMARY KEY,
    cleared_at DATE,
    guild_id TEXT
);"""

_raid_attack_conclusion = """CREATE TABLE IF NOT EXISTS raid_attack_conclusion(
    player_id TEXT,
    raid_id INTEGER REFERENCES raid(id),
    total_dmg INTEGER,
    total_hits INTEGER,
    PRIMARY KEY (player_id, raid_id)
); """

_raid_player_stats = """CREATE TABLE IF NOT EXISTS raid_player_stats(
    player_id TEXT,
    raid_id INTEGER REFERENCES raid(id),
    total_card_levels INTEGER,
    raid_level INTEGER,
    PRIMARY KEY (player_id, raid_id)
);"""
