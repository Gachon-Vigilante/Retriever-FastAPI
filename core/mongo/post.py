import threading

from pydantic import Field
from datetime import datetime

from utils import Logger

from .base import BaseMongoObject
from .connections import MongoCollections


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
    content: str | None = Field(
        default=None,
        title="Page Content",
        description="Full text content of the webpage"
    )
    drug_related: bool | None = Field(
        default=None,
        title="Drug",
        description="Indicates whether it is drug-related content"
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
        return self.link == other.link and self.content == other.content

    def store(self):
        post_collection = MongoCollections().posts
        with self._lock:
            existing_post = post_collection.find_one({"link": self.link})
            if existing_post and existing_post.pop("_id", None):
                logger.debug(f"이미 수집된 웹 게시글을 발견했습니다. "
                             f"Post link: {self.link}")
                return
            post_collection.insert_one(self.model_dump())
