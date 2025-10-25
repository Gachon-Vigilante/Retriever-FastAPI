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
from typing import List

from core.mongo.post import Post
from crawlers.base import SearchEngine


class SerpApiSearchEngine(SearchEngine):
    """SerpApi Google 검색 엔진 구현체

    SearchEngine 추상 클래스를 구현하여 주어진 키워드에 대한 Google 검색 결과를
    Post 모델 리스트로 변환합니다.
    """

    def search(
            self,
            keyword: str,
            limit: int,
    ) -> List[Post]:
        """키워드로 SerpApi 검색을 수행합니다.

        Args:
            keyword (str): 검색어(키워드).
            limit (int): 최대 결과 개수(최대 100까지 num 파라미터로 요청).

        Returns:
            list[Post]: 검색 결과를 Post 모델로 정규화한 리스트. 실패 시 빈 리스트.

        Note:
            - SERPAPI_API_KEY가 없으면 빈 리스트를 반환합니다.
            - 요청 타임아웃은 15초로 설정되어 있습니다.
        """
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            # 간단한 예외 처리: 키가 없으면 빈 결과 반환 (라우트에서 처리)
            return []

        params = {
            "engine": "google",
            "q": keyword,
            "hl": "ko",
            "gl": "kr",
            "api_key": api_key,
            "num": min(limit, 100),
        }
        try:
            resp = requests.get("https://serpapi.com/search.json", params=params, timeout=15)
            data = resp.json()
        except Exception:
            # 네트워크 오류 또는 JSON 파싱 실패 등은 상위에서 재시도할 수 있도록 빈 결과 반환
            return []

        results: List[Post] = []
        for item in data.get("organic_results", [])[:limit]:
            link = item.get("link")
            title = item.get("title") or ""
            # 도메인 정규화: source 우선, 없으면 displayed_link 사용
            domain = None
            if isinstance(item.get("source"), str):
                domain = item.get("source")
            if not domain and isinstance(item.get("displayed_link"), str):
                domain = item.get("displayed_link")
            if link:
                results.append(Post(title=title, link=link, domain=domain or ""))
        return results

