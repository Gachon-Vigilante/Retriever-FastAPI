"""크롤러 예외 정의 모듈

검색 엔진 크롤러에서 발생할 수 있는 환경 변수 누락 등의 예외를 정의합니다.
Google Custom Search 사용 시 필수인 API Key/Engine ID 누락을 명확히 식별하기 위해
커스텀 예외를 제공합니다.
"""
from typing import Optional


class GoogleCustomSearchApiKeyMissingError(Exception):
    """Google Custom Search API 키 누락 예외

    환경 변수 GOOGLE_API_KEY가 설정되지 않은 경우 발생합니다.
    """
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Google Custom Search API key is missing. Please set the API key in environment variables.")

class GoogleCustomSearchApiIdMissingError(Exception):
    """Google Custom Search 엔진 ID 누락 예외

    환경 변수 GOOGLE_CUSTOM_SEARCH_API_ID가 설정되지 않은 경우 발생합니다.
    """
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Google Custom Search API ID is missing. Please set the API ID in environment variables.")