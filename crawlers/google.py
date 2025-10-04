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
    def search_all(
            self,
            queries: list[str],
            limit: int,
    ) -> Generator[Post, Any, None]:
        for query in queries:
            # 모든 검색어에 대해 각각 검색을 수행해서 모두 yield
            yield from self.search(query, limit)

    def search(
            self,
            query: str,
            limit: int,
    ) -> Generator[Post, Any, None]:
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