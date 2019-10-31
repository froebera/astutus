"""
This type stub file was generated by pyright.
"""

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
class DiscordException(Exception):
    """Base exception class for discord.py

    Ideally speaking, this could be caught to handle any exceptions thrown from this library.
    """
    ...


class ClientException(DiscordException):
    """Exception that's thrown when an operation in the :class:`Client` fails.

    These are usually for exceptions that happened due to user input.
    """
    ...


class NoMoreItems(DiscordException):
    """Exception that is thrown when an async iteration operation has no more
    items."""
    ...


class GatewayNotFound(DiscordException):
    """An exception that is usually thrown when the gateway hub
    for the :class:`Client` websocket is not found."""
    def __init__(self):
        ...
    


def flatten_error_dict(d, key=...):
    ...

class HTTPException(DiscordException):
    """Exception that's thrown when an HTTP request operation fails.

    Attributes
    ------------
    response: :class:`aiohttp.ClientResponse`
        The response of the failed HTTP request. This is an
        instance of :class:`aiohttp.ClientResponse`. In some cases
        this could also be a :class:`requests.Response`.

    text: :class:`str`
        The text of the error. Could be an empty string.
    status: :class:`int`
        The status code of the HTTP request.
    code: :class:`int`
        The Discord specific error code for the failure.
    """
    def __init__(self, response, message):
        self.response = ...
        self.status = ...
    


class Forbidden(HTTPException):
    """Exception that's thrown for when status code 403 occurs.

    Subclass of :exc:`HTTPException`
    """
    ...


class NotFound(HTTPException):
    """Exception that's thrown for when status code 404 occurs.

    Subclass of :exc:`HTTPException`
    """
    ...


class InvalidData(ClientException):
    """Exception that's raised when the library encounters unknown
    or invalid data from Discord.
    """
    ...


class InvalidArgument(ClientException):
    """Exception that's thrown when an argument to a function
    is invalid some way (e.g. wrong value or wrong type).

    This could be considered the analogous of ``ValueError`` and
    ``TypeError`` except inherited from :exc:`ClientException` and thus
    :exc:`DiscordException`.
    """
    ...


class LoginFailure(ClientException):
    """Exception that's thrown when the :meth:`Client.login` function
    fails to log you in from improper credentials or some other misc.
    failure.
    """
    ...


class ConnectionClosed(ClientException):
    """Exception that's thrown when the gateway connection is
    closed for reasons that could not be handled internally.

    Attributes
    -----------
    code: :class:`int`
        The close code of the websocket.
    reason: :class:`str`
        The reason provided for the closure.
    shard_id: Optional[:class:`int`]
        The shard ID that got closed if applicable.
    """
    def __init__(self, original, *, shard_id):
        self.code = ...
        self.reason = ...
        self.shard_id = ...
    


