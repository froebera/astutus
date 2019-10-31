"""
This type stub file was generated by pyright.
"""

from .object import Object
from typing import Any, Optional

"""
The MIT License (MIT)

Copyright (c) 2015-2019 Rapptz

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""
OLDEST_OBJECT = Object(id=0)
class _AsyncIterator:
    __slots__ = ...
    def get(self, **attrs):
        ...
    
    async def find(self, predicate):
        ...
    
    def map(self, func):
        ...
    
    def filter(self, predicate):
        ...
    
    async def flatten(self):
        ...
    
    def __aiter__(self):
        ...
    
    async def __anext__(self):
        ...
    


def _identity(x):
    ...

class _MappedAsyncIterator(_AsyncIterator):
    def __init__(self, iterator, func):
        self.iterator = ...
        self.func = ...
    
    async def next(self):
        ...
    


class _FilteredAsyncIterator(_AsyncIterator):
    def __init__(self, iterator, predicate):
        self.iterator = ...
        self.predicate = ...
    
    async def next(self):
        ...
    


class ReactionIterator(_AsyncIterator):
    def __init__(self, message, emoji, limit=..., after: Optional[Any] = ...):
        self.message = ...
        self.limit = ...
        self.after = ...
        self.getter = ...
        self.state = ...
        self.emoji = ...
        self.guild = ...
        self.channel_id = ...
        self.users = ...
    
    async def next(self):
        ...
    
    async def fill_users(self):
        ...
    


class HistoryIterator(_AsyncIterator):
    """Iterator for receiving a channel's message history.

    The messages endpoint has two behaviours we care about here:
    If `before` is specified, the messages endpoint returns the `limit`
    newest messages before `before`, sorted with newest first. For filling over
    100 messages, update the `before` parameter to the oldest message received.
    Messages will be returned in order by time.
    If `after` is specified, it returns the `limit` oldest messages after
    `after`, sorted with newest first. For filling over 100 messages, update the
    `after` parameter to the newest message received. If messages are not
    reversed, they will be out of order (99-0, 199-100, so on)

    A note that if both before and after are specified, before is ignored by the
    messages endpoint.

    Parameters
    -----------
    messageable: :class:`abc.Messageable`
        Messageable class to retrieve message history from.
    limit: :class:`int`
        Maximum number of messages to retrieve
    before: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
        Message before which all messages must be.
    after: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
        Message after which all messages must be.
    around: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
        Message around which all messages must be. Limit max 101. Note that if
        limit is an even number, this will return at most limit+1 messages.
    oldest_first: Optional[:class:`bool`]
        If set to ``True``, return messages in oldest->newest order. Defaults to
        True if ``after`` is specified, otherwise ``False``.
    """
    def __init__(self, messageable, limit, before: Optional[Any] = ..., after: Optional[Any] = ..., around: Optional[Any] = ..., oldest_first: Optional[Any] = ...):
        self.messageable = ...
        self.limit = ...
        self.before = ...
        self.after = ...
        self.around = ...
        self.state = ...
        self.logs_from = ...
        self.messages = ...
    
    async def next(self):
        ...
    
    def _get_retrieve(self):
        self.retrieve = ...
    
    async def flatten(self):
        self.channel = ...
    
    async def fill_messages(self):
        ...
    
    async def _retrieve_messages(self, retrieve):
        """Retrieve messages and update next parameters."""
        ...
    
    async def _retrieve_messages_before_strategy(self, retrieve):
        """Retrieve messages using before parameter."""
        ...
    
    async def _retrieve_messages_after_strategy(self, retrieve):
        """Retrieve messages using after parameter."""
        ...
    
    async def _retrieve_messages_around_strategy(self, retrieve):
        """Retrieve messages using around parameter."""
        ...
    


class AuditLogIterator(_AsyncIterator):
    def __init__(self, guild, limit: Optional[Any] = ..., before: Optional[Any] = ..., after: Optional[Any] = ..., oldest_first: Optional[Any] = ..., user_id: Optional[Any] = ..., action_type: Optional[Any] = ...):
        self.guild = ...
        self.loop = ...
        self.request = ...
        self.limit = ...
        self.before = ...
        self.user_id = ...
        self.action_type = ...
        self.after = ...
        self.entries = ...
    
    async def _before_strategy(self, retrieve):
        ...
    
    async def _after_strategy(self, retrieve):
        ...
    
    async def next(self):
        ...
    
    def _get_retrieve(self):
        self.retrieve = ...
    
    async def _fill(self):
        ...
    


class GuildIterator(_AsyncIterator):
    """Iterator for receiving the client's guilds.

    The guilds endpoint has the same two behaviours as described
    in :class:`HistoryIterator`:
    If `before` is specified, the guilds endpoint returns the `limit`
    newest guilds before `before`, sorted with newest first. For filling over
    100 guilds, update the `before` parameter to the oldest guild received.
    Guilds will be returned in order by time.
    If `after` is specified, it returns the `limit` oldest guilds after `after`,
    sorted with newest first. For filling over 100 guilds, update the `after`
    parameter to the newest guild received, If guilds are not reversed, they
    will be out of order (99-0, 199-100, so on)

    Not that if both before and after are specified, before is ignored by the
    guilds endpoint.

    Parameters
    -----------
    bot: :class:`discord.Client`
        The client to retrieve the guilds from.
    limit: :class:`int`
        Maximum number of guilds to retrieve.
    before: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
        Object before which all guilds must be.
    after: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
        Object after which all guilds must be.
    """
    def __init__(self, bot, limit, before: Optional[Any] = ..., after: Optional[Any] = ...):
        self.bot = ...
        self.limit = ...
        self.before = ...
        self.after = ...
        self.state = ...
        self.get_guilds = ...
        self.guilds = ...
    
    async def next(self):
        ...
    
    def _get_retrieve(self):
        self.retrieve = ...
    
    def create_guild(self, data):
        ...
    
    async def flatten(self):
        ...
    
    async def fill_guilds(self):
        ...
    
    async def _retrieve_guilds(self, retrieve):
        """Retrieve guilds and update next parameters."""
        ...
    
    async def _retrieve_guilds_before_strategy(self, retrieve):
        """Retrieve guilds using before parameter."""
        ...
    
    async def _retrieve_guilds_after_strategy(self, retrieve):
        """Retrieve guilds using after parameter."""
        ...
    


