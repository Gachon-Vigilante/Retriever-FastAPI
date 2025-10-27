"""웹 게시글(Post) MongoDB 모델 및 저장 로직

이 모듈은 웹 검색/크롤링으로 수집된 게시글 문서를 표현하는 Pydantic 모델과
MongoDB 영속화 유틸리티를 제공합니다. 비즈니스 규칙은 다음과 같습니다.
- 초기 저장 시 본문(text)은 저장하지 않습니다. 분석 결과에서 drugs_related=true일 때에만 저장합니다.
- 링크(link)를 고유 식별자로 간주하여 업서트합니다.
- 분석 결과 스키마는 Gemini Batch API 응답(JSON)과 호환되도록 설계되어 있습니다.

Google 스타일의 한국어 docstring을 사용합니다. 기능 변경 없이 문서화만 제공합니다.
"""

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
    """텔레그램 채널 식별자 모델

    웹 게시글에서 추출된 텔레그램 채널 식별자(링크, @username, ID)의 처리 상태를 보관합니다.

    Attributes:
        identifier (str): 원본 식별자 문자열.
        channel_id (int | None): 정규화된 채널 ID. 아직 미확정이면 None.
        is_processed (bool): 식별자 처리 여부.
        error (str | None): 처리 실패 시 에러 메시지.
    """
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
    """텔레그램 프로모션 감지 결과 모델

    게시글 본문에서 탐지된 마약 판매 관련 프로모션 텍스트와 연관 텔레그램 식별자 목록을 담습니다.

    Attributes:
        content (str): 감지된 프로모션 원문 텍스트 일부.
        identifiers (list[TelegramChannelIdentifierInfo]): 프로모션과 연관된 텔레그램 채널 식별자 목록.
    """
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
    """유사 게시글 항목 모델

    게시글 간 코사인 유사도 등으로 계산된 유사 항목을 표현합니다.

    Attributes:
        post_id (str): 비교 대상 게시글의 ObjectId 문자열.
        similarity (float): 유사도 점수(0.0~1.0).
    """
    post_id: str = Field(
        title="Post ID (ObjectID)",
        description="ID of the post to compare with",
    )
    similarity: float = Field(
        title="Similarity",
        description="Similarity score between the post and the comparison post",
    )

class PostAnalysisResult(BaseModel):
    """게시글 분석 결과 모델

    LLM 분석(Gemini Batch)의 결과를 게시글 문서에 저장하기 위한 모델입니다.

    Attributes:
        drugs_related (bool): 마약 판매 관련성 여부.
        promotions (list[TelegramPromotion]): 감지된 프로모션과 텔레그램 식별자 목록.
    """
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
    """Post 문서 필드 상수

    MongoDB posts 컬렉션에서 사용하는 키 이름을 열거형으로 관리합니다.
    코드 전역에서 하드코딩을 줄이고 오타를 방지하기 위함입니다.
    """
    title = "title"
    link = "link"
    domain = "domain"
    site_name = "site_name"
    cluster = "cluster"
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
    """웹 게시글(Post) 모델

    검색 결과로 수집된 웹 페이지 문서를 표현합니다. 초기 저장 시에는 텍스트 본문을 저장하지 않고,
    LLM 분석 결과에 따라 조건부로 본문(text)과 analysis를 채웁니다.

    Attributes:
        title (str): 검색 결과의 제목.
        link (str): 원문 링크 URL. 업서트의 고유 키.
        domain (str): 도메인명.
        site_name (str | None): 사이트 표시명.
        cluster (int | None): 오프라인 클러스터링 ID.
        html (str | None): 원문 HTML.
        text (str | None): 본문 텍스트(조건부 저장).
        analysis (PostAnalysisResult | None): 분석 결과.
        analysis_job_id (ObjectId | None): 배치 분석 작업 ID.
        description (str | None): 스니펫/요약.
        published_at (datetime | None): 게시 시각.
        discovered_at (datetime | None): 발견 시각.
        updated_at (datetime | None): 갱신 시각.
        similarities (list[PostSimilarity]): 유사 게시글 목록.
    """
    title: str = Field(
        title="Page Title",
        description="Title of the webpage shown in search results",
        alias=PostFields.title,
    )
    link: str = Field(
        title="Page URL",
        description="URL/link to the webpage",
        alias=PostFields.link,
    )
    domain: str = Field(
        title="Page Domain",
        description="Domain of the webpage (e.g. google.com)",
        alias=PostFields.domain,
    )
    site_name: str | None = Field(
        default=None,
        title="Page Site Name",
        description="Name of the website shown in search results",
        alias=PostFields.site_name,
    )
    cluster: int | None = Field(
        default=None,
        title="Page Cluster ID",
        description="Cluster ID of the webpage",
        alias=PostFields.cluster,
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
        description="Analysis results of the post",
        alias=PostFields.analysis,
    )

    analysis_job_id: ObjectId | None = Field(
        default=None,
        title="Analysis Job ID",
        description="ID of the analysis batch job",
        alias=PostFields.analysis_job_id,
    )
    description: str | None = Field(
        default=None,
        title="Page Description",
        description="Brief description or snippet of the webpage content",
        alias=PostFields.description,
    )
    published_at: datetime | None = Field(
        default=None,
        title="Published Date",
        description="Date when the content was published",
        alias=PostFields.published_at,
    )
    discovered_at: datetime | None = Field(
        default_factory=datetime.now,
        title="Discovered Date",
        description="Date when the content was discovered",
        alias=PostFields.discovered_at,
    )
    updated_at: datetime | None = Field(
        default_factory=datetime.now,
        title="Updated Date",
        description="Date when the content was last updated",
        alias=PostFields.updated_at,
    )

    similarities: list[PostSimilarity] = Field(
        default_factory=list,
        title="Similar Posts with Similarity Score",
        description="List of posts and its similarity scores similar to the current post",
        alias=PostFields.similarities,
    )

    def model_dump_only_insert(self):
        return {k: v for k, v in self.model_dump().items() if k != "similarities"}

    def model_dump_only_update(self):
        return {k: v for k, v in self.model_dump().items() if k == "similarities"}


    def __eq__(self, other):
        return self.link == other.link and self.text == other.text

    def __str__(self):
        return f"Post(title={self.title}, link={self.link})"

    def store(self) -> ObjectId | None:
        """게시글 문서를 MongoDB에 업서트합니다.

        비즈니스 규칙:
        - link 필드를 고유키로 간주하고 존재하지 않을 때만 새 문서를 생성합니다.
        - 초기 저장은 수집 시점의 메타 정보(제목/링크/도메인/요약 등) 위주이며, text는 저장하지 않습니다.
        - 동시성에 의한 DuplicateKeyError는 안전하게 무시하고 로그만 남깁니다.

        Returns:
            ObjectId | None: 새로 삽입된 경우 upserted_id, 이미 존재하거나 중복 충돌이면 None.
        """
        post_collection = MongoCollections().posts
        try:
            result = post_collection.update_one(
                filter={"link": self.link},
                update={
                    "$set": self.model_dump_only_update(),
                    "$setOnInsert": self.model_dump_only_insert(),
                }, # 같은 link를 가지는 값이 없을 때에만 값 추가
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
        """사전(dict)으로부터 Post 모델을 안전 검증/생성합니다.

        일부 필수 필드는 임시 기본값으로 채운 뒤 Pydantic 검증을 수행합니다.
        MongoDB 문서를 직접 모델로 변환할 때 유용합니다.

        Args:
            obj (dict): 원본 딕셔너리 문서.
            strict (bool | None): Pydantic strict 모드.
            from_attributes (bool | None): 속성 기반 로딩 여부.
            context (Any | None): 컨텍스트.
            by_alias (bool | None): alias 사용 여부.
            by_name (bool | None): 이름 기반 사용 여부.

        Returns:
            Self: 검증된 Post 모델 인스턴스.
        """
        temp_post = cls.from_mongo(obj)
        temp_post.title = temp_post.link = temp_post.domain = ""
        return Post.model_validate(temp_post.model_dump(), strict=strict, from_attributes=from_attributes, context=context, by_alias=by_alias, by_name=by_name)


    @classmethod
    def from_mongo(cls, doc: dict, autofill: bool = False) -> Self:
        """MongoDB 문서(dict)에서 Post 모델을 생성합니다.

        Args:
            doc (dict): MongoDB에서 읽은 원본 문서.
            autofill (bool): 필수 필드(title, link, domain)가 누락된 경우 공백으로 채울지 여부.

        Returns:
            Self: 변환된 Post 모델 인스턴스.
        """
        if autofill:
            for field in (PostFields.title, PostFields.link, PostFields.domain):
                if field not in doc:
                    doc[field] = ""
        return Post.model_validate({k: v for k, v in doc.items() if k != "_id"})
