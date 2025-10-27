"""Google Custom Search 기반 크롤러 모듈

이 모듈은 Google Custom Search API를 사용하여 키워드 검색을 수행하고,
검색 결과를 Post 모델로 정규화하여 스트리밍 방식으로 반환합니다.

주의 사항:
- 환경 변수 GOOGLE_API_KEY, GOOGLE_CUSTOM_SEARCH_API_ID가 필요합니다.
- 네트워크 오류 발생 시 로깅 후 다음 페이지 요청으로 진행합니다.

Google 스타일의 한국어 docstring을 사용합니다.
"""

import os
from typing import Any, Generator

import requests
from dotenv import load_dotenv

from core.mongo.post import Post
from utils import Logger
from crawlers.errors import *
from .base import SearchEngine

logger = Logger(__name__)


load_dotenv()
_search_endpoint = "https://www.googleapis.com/customsearch/v1"


class GoogleSearchEngine(SearchEngine):
    """Google Custom Search 엔진 구현체.

    SearchEngine 추상 클래스를 구현하며, 검색 결과를 제너레이터로 반환하여
    소비자가 스트리밍 처리할 수 있도록 합니다.
    """
    def search(
            self,
            query: str,
            limit: int,
    ) -> Generator[Post, Any, None]:
        """단일 검색어로 Google Custom Search 수행.

        Args:
            query (str): 검색어.
            limit (int): 최대 결과 개수(페이지네이션으로 누적 수집).

        Raises:
            GoogleCustomSearchApiKeyMissingError: GOOGLE_API_KEY 누락 시.
            GoogleCustomSearchApiIdMissingError: GOOGLE_CUSTOM_SEARCH_API_ID 누락 시.

        Yields:
            Post: 검색 결과 항목을 Post 모델로 정규화하여 순차 반환.
        """
        search_engine_id = os.getenv("GOOGLE_CUSTOM_SEARCH_API_ID")
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise GoogleCustomSearchApiKeyMissingError
        if not search_engine_id:
            raise GoogleCustomSearchApiIdMissingError

        start: int = 1
        params = {
            "key": api_key,
            "cx": search_engine_id,
            "q": query,
            "gl": "kr",  # 지역을 한국으로 설정 (검색 결과 향상을 목표로 했으나 달라지는 게 없어 보임)
            "hl": "ko",  # 지역을 한국으로 설정 (검색 결과 향상을 목표로 했으나 달라지는 게 없어 보임)
            "num": min(limit, 10),  # 최대 10개까지 가능
            "start": start  # 검색 시작 위치
        }
        posts = []
        max_retries = 3

        while len(posts) < limit and start <= 1000:
            params["start"] = start  # 검색할 페이지로 이동
            try:
                data = {}
                for retry in range(max_retries):
                    response = requests.get(_search_endpoint, params=params, timeout=10)
                    data = response.json()
                    break
            except Exception as e:
                logger.error(f"Error occurred while searching: {e}")
                continue
            else:
                start += 10
                # 검색 결과가 없을 경우(검색 결과의 끝에 도달했을 경우) 검색 중단
                if "items" not in data:
                    break

                # 검색 결과가 있을 경우 검색 결과로 나온 링크를 순회
                for item in data["items"]:
                    yield Post(
                        title=item["title"],
                        link=item["link"],
                        domain=item["displayLink"],
                    )
                    if len(posts) >= limit:
                        break