from enum import StrEnum
from bson import ObjectId
from pydantic import Field, BaseModel
from datetime import datetime

from utils import Logger
from genai.models import prompts

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
    )
    promotions: list[TelegramPromotion] = Field(
        default_factory=list,
        title="Telegram Promotions",
        description="List of detected drug promotions with associated Telegram channel information extracted from the content"
    )

    @classmethod
    def gemini_compatible_schema(cls) -> dict:
        """Gemini API 호환 JSON 스키마 생성"""
        return {
            "type": "object",
            "properties": {
                "drugs_related": {
                    "type": "boolean",
                    "description": prompts["analysis"]["post"]["drugs_related"]
                },
                "promotions": {
                    "type": "array",
                    "description": "List of detected drug promotions with associated Telegram channel information",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": prompts["analysis"]["post"]["content"]
                            },
                            "links": {
                                "type": "array",
                                "description": prompts["analysis"]["post"]["links"],
                                "items": {
                                    "type": "string"
                                }
                            }
                        },
                        "required": ["content", "links"]
                    }
                }
            },
            "required": ["drugs_related", "promotions"]
        }

logger = Logger(__name__)

class PostFields(StrEnum):
    """Post fields"""
    title = "title"
    link = "link"
    domain = "domain"
    html = "html"
    text = "text"
    analysis = "analysis"
    analysis_job_id = "analysis_job_id"
    description = "description"
    published_at = "published_at"
    discovered_at = "discovered_at"
    updated_at = "updated_at"

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
    html: str | None = Field(
        default=None,
        title="Page HTML Content",
        description="HTML content of the webpage",
        alias=PostFields.html,
    )
    text: str | None = Field(
        default=None,
        title="Page Text Content",
        description="Full text content of the webpage",
        alias=PostFields.text,
    )
    analysis: PostAnalysisResult | None = Field(
        default=None,
        title="Post Analysis Results",
        description="Analysis results of the post"
    )

    analysis_job_id: ObjectId | None = Field(
        default=None,
        title="Analysis Job ID",
        description="ID of the analysis batch job",
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
    )
    discovered_at: datetime | None = Field(
        default_factory=datetime.now,
        title="Discovered Date",
        description="Date when the content was discovered",
    )
    updated_at: datetime | None = Field(
        default_factory=datetime.now,
        title="Updated Date",
        description="Date when the content was last updated",
    )

    def __eq__(self, other):
        return self.link == other.link and self.text == other.text

    def store(self) -> ObjectId | None:
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
            return post_collection.insert_one(doc).inserted_id

    @classmethod
    def from_mongo(cls, doc: dict) -> 'Post':
        return cls(**{k: v for k, v in doc.items() if k != "_id"})
