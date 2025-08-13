from typing import Optional


class GoogleCustomSearchApiKeyMissingError(Exception):
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Google Custom Search API key is missing. Please set the API key in environment variables.")

class GoogleCustomSearchApiIdMissingError(Exception):
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Google Custom Search API ID is missing. Please set the API ID in environment variables.")