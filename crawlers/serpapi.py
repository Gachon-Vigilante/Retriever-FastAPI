from core.mongo.post import Post
from .base import Crawler


class SerpApiCrawler(Crawler):
    def search(
            self,
            keyword: str,
            limit: int,
    ) -> list[Post]:
        raise NotImplementedError("search() method is not implemented.")

