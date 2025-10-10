import os
import requests
from typing import List

from core.mongo.post import Post
from crawlers.base import SearchEngine


class SerpApiSearchEngine(SearchEngine):
    def search(
            self,
            keyword: str,
            limit: int,
    ) -> List[Post]:
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
            return []

        results: List[Post] = []
        for item in data.get("organic_results", [])[:limit]:
            link = item.get("link")
            title = item.get("title") or ""
            domain = None
            if isinstance(item.get("source"), str):
                domain = item.get("source")
            if not domain and isinstance(item.get("displayed_link"), str):
                domain = item.get("displayed_link")
            if link:
                results.append(Post(title=title, link=link, domain=domain or ""))
        return results

