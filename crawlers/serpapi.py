"""SerpApi 기반 Google 검색 크롤러 모듈

이 모듈은 SerpApi를 사용하여 Google 검색 결과를 가져와 웹 게시글(Post) 리스트로
변환합니다. 네트워크 호출 실패나 키 누락 시 조용히 빈 결과를 반환하여 상위 계층에서
처리할 수 있도록 설계되었습니다.

주의 사항:
- 환경 변수 SERPAPI_API_KEY가 필요합니다(README 참조).
- 네트워크 오류/쿼터 초과 등 예외 상황에서는 빈 리스트를 반환합니다.

Google 스타일의 한국어 docstring을 사용합니다.
"""

import os
import requests
from typing import List, Generator, Any
import serpapi

from core.mongo.post import Post
from crawlers.base import SearchEngine
from urllib.parse import urlparse

from utils import Logger

logger = Logger(__name__)

class SerpApiSearchEngine(SearchEngine):
    """SerpApi Google 검색 엔진 구현체

    SearchEngine 추상 클래스를 구현하여 주어진 키워드에 대한 Google 검색 결과를
    Post 모델 리스트로 변환합니다.
    """
    def search(
            self,
            keyword: str,
            limit: int = 10,
            engine: str = "google",
    ) -> Generator[Post, Any, None]:
        """키워드로 SerpApi 검색을 수행합니다.

        Args:
            keyword (str): 검색어(키워드).
            limit (int): 최대 결과 개수(최대 10까지 num 파라미터로 요청).

        Returns:
            list[Post]: 검색 결과를 Post 모델로 정규화한 리스트. 실패 시 빈 리스트.

        Note:
            - SERPAPI_API_KEY가 없으면 빈 리스트를 반환합니다.
            - 요청 타임아웃은 15초로 설정되어 있습니다.
        """
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            # 간단한 예외 처리: 키가 없으면 빈 결과 반환 (라우트에서 처리)
            return None

        params = {
            "api_key": api_key,  # SerpAPI 키
            "engine": engine,
            "q": keyword,
            "hl": "ko",  # 한국어로 검색
            "gl": "kr",  # 한국 지역에서 검색
            "nfpr": 1,  # 자동 교정된 검색 제외
            "lr": "lang_ko",  # 검색 결과에서 한국어만 반환
            "safe": "off",  # 성인 콘텐츠 검열 안함
        }

        serpapi_result = serpapi.search(
            q=keyword,
            engine=engine,
            location="Seoul,Seoul,South Korea",
            hl="ko",
            gl="kr",
            nfpr=1,
            lr="lang_ko",
            safe="off",
            api_key=api_key,
        )

        while serpapi_result and serpapi_result.get("organic_results"):
            for item in serpapi_result["organic_results"]:
                if limit < 1: break
                if item.get("link"):
                    yield Post(
                        title=item.get("title", "Unknown Title"),
                        link=item.get("link"),
                        domain=urlparse(item.get("link")).netloc,
                        site_name=item.get("displayLink"),
                    )

                limit -= 1

            if limit < 1: break
            # 다음 페이지가 있고, 검색 가능 결과 수가 남았을 경우 다음 페이지로 다시 검색
            if next_link := serpapi_result["serpapi_pagination"].get("next"):
                try:
                    response = requests.get(next_link, params={"api_key": api_key}, timeout=30) # "serpapi의 "next"에는 API KEY는 빠져 있으므로, 다시 지정해 주어야 함.
                except Exception as e:
                    logger.error(e)
                    break
                if response.status_code == 200:
                    serpapi_result = response.json()
                else:
                    logger.warning(f"SerpApi returned with an error message: {response.text}")
                    return None
            else:  # 다음 페이지가 없거나 최대 검색 수에 도달했을 경우 검색 중단
                return None
        return None
