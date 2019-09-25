from notbot.context import Context
from .postgres_connection import get_postgres_connection
from contextlib import asynccontextmanager
from contextvars import ContextVar

connection_ctx: ContextVar = ContextVar("connection")


class PostgresDaoBase:
    def __init__(self, context: Context):
        self.postgres_connection = get_postgres_connection(context)

    @asynccontextmanager
    async def connection(self):
        con = connection_ctx.get(None)
        token = None
        if not con:
            con = await self.postgres_connection.pool.acquire()
            token = connection_ctx.set(con)

        try:
            yield con
        finally:
            if token:
                connection_ctx.reset(token)
            await self.postgres_connection.pool.release(con)
