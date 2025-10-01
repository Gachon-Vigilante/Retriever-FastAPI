import threading

from pydantic import Field, BaseModel
from datetime import datetime

from utils import Logger

from .base import BaseMongoObject
from .connections import MongoCollections


class TelegramPromotion(BaseModel):
    content: str = Field(
        default="",
        title="Promotion Content",
        description="Drugs promotions content detected in the post.",
    )
    links: list[str] = Field(
        default_factory=list,
        title="Telegram Links",
        description="List of detected telegram links from content."
    )

class PostAnalysisResult(BaseModel):
    drugs_related: bool = Field(
        default=False,
        title="Drug Detection",
        description="Whether the post is related to drugs promotions or not.",
        serialization_alias="drugRelated"
    )
    promotions: list[TelegramPromotion] = Field(
        default_factory=list,
        title="Telegram Promotions",
        description="List of detected drug promotions with associated Telegram channel information extracted from the content"
    )

logger = Logger(__name__)

class Post(BaseMongoObject):
    title: str = Field(
        title="Page Title",
        description="Title of the webpage shown in search results"
    )
    link: str = Field(
        title="Page URL",
        description="URL/link to the webpage"
    )
    domain: str = Field(
        title="Page Domain",
        description="Domain of the webpage (e.g. google.com)"
    )
    text: str | None = Field(
        default=None,
        title="Page Text Content",
        description="Full text content of the webpage"
    )
    analysis: PostAnalysisResult | None = Field(
        default=None,
        title="Post Analysis Results",
        description="Analysis results of the post"
    )

    description: str | None = Field(
        default=None,
        title="Page Description",
        description="Brief description or snippet of the webpage content"
    )
    published_at: datetime | None = Field(
        default=None,
        title="Published Date",
        description="Date when the content was published",
        serialization_alias="publishedAt",
    )
    discovered_at: datetime | None = Field(
        default_factory=datetime.now,
        title="Discovered Date",
        description="Date when the content was discovered",
        serialization_alias = "discoveredAt",
    )

    def __eq__(self, other):
        return self.link == other.link and self.text == other.text

    def store(self):
        post_collection = MongoCollections().posts
        with self._lock:
            existing_post = post_collection.find_one({"link": self.link})
            if existing_post and existing_post.pop("_id", None):
                logger.debug(f"이미 수집된 웹 게시글을 발견했습니다. "
                             f"Post link: {self.link}")
                return
            # 요구사항: 판매글 여부가 확정되기 전에는 본문(text)을 저장하지 않음
            doc = self.model_dump()
            if 'text' in doc:
                doc.pop('text')
            post_collection.insert_one(doc)
