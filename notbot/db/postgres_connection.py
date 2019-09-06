from notbot.context import Context, Module
import asyncio
import asyncpg
from notbot.services.config_service import get_config_service
from asyncpg.pool import Pool

MODULE_NAME = "postgres_connection"


class PostgresConnection(Module):
    def __init__(self, context: Context):
        self.config_service = get_config_service(context)
        self.postgres_configuration = None
        self.pool: Pool = None

    def get_name(self):
        return MODULE_NAME

    def start(self):
        self.postgres_configuration = self.config_service.get_config("POSTGRESQL")
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


def get_postgres_connection(context: Context) -> PostgresConnection:
    return context.get_or_register_module(
        MODULE_NAME, lambda: PostgresConnection(context)
    )


async def init_db(uri):
    pool = await asyncpg.create_pool(
        dsn=uri, command_timeout=60, max_size=5, min_size=1
    )

    async with pool.acquire() as connection:
        await connection.execute(_raid_query)
        await connection.execute(_raid_attack_conclusion)
        await connection.execute(_raid_player_stats)

        for alter_statement in _alter_statements:
            await connection.execute(alter_statement)

    return pool


_raid_query = """CREATE TABLE IF NOT EXISTS raid(
    id serial PRIMARY KEY,
    cleared_at DATE,
    guild_id TEXT
);"""

_raid_attack_conclusion = """CREATE TABLE IF NOT EXISTS raid_player_attack(
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
); """

# _raid_player_bonuses = """CREATE TABLE IF NOT EXISTS raid_player_bonuses(
#     player_id TEXT,
#     raid_id INTEGER REFERENCES raid(id),
#     PRIMARY KEY (player_id, raid_id)
# );"""


_alter_statements = [
    "ALTER TABLE raid ADD COLUMN IF NOT EXISTS started_at DATE",
    "DROP TABLE IF EXISTS raid_attack_conclusion",
    "ALTER TABLE raid_player_attack ADD COLUMN IF NOT EXISTS player_name TEXT",
    "ALTER TABLE raid ALTER COLUMN guild_id SET NOT NULL",
    "ALTER TABLE raid ALTER COLUMN started_at TYPE timestamptz",
    "ALTER TABLE raid ALTER COLUMN cleared_at TYPE timestamptz",
]
