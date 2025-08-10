from typing import Optional


class ApiIdInvalidError(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "API ID is invalid."

class ApiHashInvalidError(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "API Hash is invalid."

class TelegramSessionStringInvalidError(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "Session string is invalid."

class ChannelNotFoundError(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "Channel not found."

class ChannelKeyInvalidError(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "Channel key is invalid."

class ChannelNotWatchedError(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "Channel is not being watched."

class ChannelAlreadyWatchedError(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "Channel is already being watched."