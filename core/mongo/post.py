"""Post model and MongoDB operations for web page content."""

from enum import StrEnum
from typing import Any, Self

import pymongo
from bson import ObjectId
from pydantic import Field, BaseModel
from datetime import datetime

from pymongo.errors import DuplicateKeyError

from utils import Logger
from genai.models import prompts

from .base import BaseMongoObject
from .connections import MongoCollections

class TelegramChannelIdentifierInfo(BaseModel):
    identifier: str = Field(
        title="Telegram Channel identifier",
        description="Telegram channel link, username or ID"
    )
    channel_id: int | None = Field(
        default=None,
        title="Telegram Channel ID",
        description="Telegram channel ID"
    )
    is_processed: bool = Field(
        default=False,
        title="Telegram Channel identifier processed",
        description="Whether the Telegram channel identifier has been processed or not."
    )
    error: str | None = Field(
        default=None,
        title="Telegram Channel identifier error",
        description="Error message if processing failed."
    )


class TelegramPromotion(BaseModel):
    content: str = Field(
        default="",
        title="Promotion Content",
        description="Drugs promotions content detected in the post.",
    )
    identifiers: list[TelegramChannelIdentifierInfo] = Field(
        default_factory=list,
        title="Telegram Channel Identifiers",
        description="List of Telegram channel identifiers associated with the promotion content."
    )

class PostSimilarity(BaseModel):
    post_id: str = Field(
        title="Post ID (ObjectID)",
        description="ID of the post to compare with",
    )
    similarity: float = Field(
        title="Similarity",
        description="Similarity score between the post and the comparison post",
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
                            "identifiers": {
                                "type": "array",
                                "description": "List of Telegram channel identifiers associated with the promotion content.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "identifier": {
                                            "type": "string",
                                            "description": prompts["analysis"]["post"]["links"],
                                        },
                                    }
                                }
                            }
                        },
                        "required": ["content", "identifiers"]
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
    similarities = "similarities"

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

    similarities: list[PostSimilarity] = Field(
        default_factory=list,
        title="Similar Posts with Similarity Score",
        description="List of posts and its similarity scores similar to the current post"
    )

    def __eq__(self, other):
        return self.link == other.link and self.text == other.text

    def store(self) -> ObjectId | None:
        post_collection = MongoCollections().posts
        try:
            result = post_collection.update_one(
                filter={"link": self.link},
                update={"$setOnInsert": self.model_dump()}, # 같은 link를 가지는 값이 없을 때에만 값 추가
                upsert=True,
            )
            if result.upserted_id:
                logger.info(f"새로운 웹 게시글을 추가했습니다. "
                            f"Post link: {self.link}")
            else:
                logger.info(f"이미 존재하는 게시글이 발견되었습니다. "
                            f"Post link: {self.link}")
            return result.upserted_id
        except DuplicateKeyError:
            logger.info(f"게시글 정보의 동시 입력이 감지되었습니다. Post link: {self.link}")
            return None

    @classmethod
    def model_validate_dict(
        cls,
        obj: dict,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Self:
        temp_post = cls.from_mongo(obj)
        temp_post.title = temp_post.link = temp_post.domain = ""
        return Post.model_validate(temp_post.model_dump(), strict=strict, from_attributes=from_attributes, context=context, by_alias=by_alias, by_name=by_name)


    @classmethod
    def from_mongo(cls, doc: dict) -> Self:
        return Post.model_validate({k: v for k, v in doc.items() if k != "_id"})

    @classmethod
    def from_dict(cls, doc: dict) -> Self:
        for field in (PostFields.title, PostFields.link, PostFields.domain):
            if field not in doc:
                doc[field] = ""
        doc.pop("_id", None)
        return Post(**doc)
