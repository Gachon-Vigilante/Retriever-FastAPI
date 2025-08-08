class ApiIdInvalidError(Exception):
    def __init__(self, message):
        self.message = message or "API ID is invalid."

class ApiHashInvalidError(Exception):
    def __init__(self, message):
        self.message = message or "API Hash is invalid."

class TelegramSessionStringInvalidError(Exception):
    def __init__(self, message):
        self.message = message or "Session string is invalid."