from typing import Optional
from telethon.errors import (
    ApiIdInvalidError as TelethonApiIdInvalidError,
    InviteHashEmptyError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    ChannelInvalidError,
    ChannelPrivateError,
    FloodWaitError,
)

__all__ = [
    'InviteHashEmptyError',
    'InviteHashExpiredError',
    'InviteHashInvalidError',
    'ChannelInvalidError',
    'ChannelPrivateError',
    'FloodWaitError',
    'ApiIdInvalidError',
    'ApiHashInvalidError',
    'UnknownInvitationTypeError',
    'SessionStringInvalidError',
    'ChannelNotFoundError',
    'UsernameNotFoundError',
    'ChannelKeyInvalidError',
    'ChannelNotWatchedError',
    'ChannelAlreadyWatchedError',
    'NotChannelError',
]


class ApiIdInvalidError(TelethonApiIdInvalidError):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "API ID is invalid."

class ApiHashInvalidError(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "API Hash is invalid."

class UnknownInvitationTypeError(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "Unknown invitation type."

class SessionStringInvalidError(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "Session string is invalid."

class ChannelNotFoundError(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "Channel not found."

class UsernameNotFoundError(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "Username not found."

class ChannelKeyInvalidError(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "Channel key is invalid."

class ChannelNotWatchedError(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "Channel is not being watched."

class ChannelAlreadyWatchedError(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "Channel is already being watched."

class NotChannelError(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "Connected entity is not a channel."