"""Neo4j OGM 모델

이 모듈은 네트워크 그래프(게시글-채널-은어-약물) 관계를 표현하기 위한 neomodel 기반의
OGM(Object Graph Mapping) 모델을 제공합니다. 수집된 MongoDB 문서를 그래프 노드로 변환하고,
비즈니스 규칙에 맞는 관계를 연결합니다.

핵심 관계:
- Post --PROMOTES--> Channel: 게시글이 특정 텔레그램 채널을 홍보/유도할 때
- Channel --SELLS{message_ids}--> Argot: 채널이 특정 은어로 판매 정황을 보일 때(메시지 ID 수집)
- Argot --REFERS_TO--> Drug: 은어가 어떤 약물을 지칭하는지
- Post --SIMILAR_TO(score)--> Post: 게시글 간 유사도 링크(시간 순 방향성)
"""

import os
from typing import Self
from dotenv import load_dotenv
from datetime import datetime

from neomodel import (
    db,
    config,
    StructuredNode,
    BooleanProperty,
    DateTimeProperty,
    StringProperty,
    IntegerProperty,
    RelationshipTo,
    StructuredRel,
    FloatProperty,
    ArrayProperty, RelationshipFrom
)

from core.mongo.channel import ChannelFields
from core.mongo.post import PostFields

load_dotenv()
config.DATABASE_URL = os.getenv("NEO4J_URL")

class Promotes(StructuredRel):
    """게시글이 채널을 홍보/유도하는 관계 모델(PROMOTES)."""

    @classmethod
    def merge(
            cls,
            post: 'PostNode',
            channel: 'ChannelNode',
    ):
        """두 노드를 업서트한 후 PROMOTES 관계를 연결합니다.

        Args:
            post (PostNode): 원 게시글 노드(오브젝트 상태여도 됨).
            channel (ChannelNode): 대상 채널 노드.
        """
        merged_post = post.merge()
        merged_channel = channel.merge()
        merged_post.promotes.connect(merged_channel)


class SimilarTo(StructuredRel):
    """게시글 간 유사 관계(SIMILAR_TO). 시간 순 방향성을 가집니다."""

    score = FloatProperty()

    @classmethod
    def merge(
            cls,
            post: 'PostNode',
            post_to_compare: 'PostNode',
    ):
        """두 게시글 노드를 업서트하고 시간 순으로 방향성 있는 유사 관계를 연결합니다.

        로직:
        - discovered_at가 더 늦은 게시글에서 더 이른 게시글로 향하도록 연결합니다.
        - 타임스탬프가 없는 경우는 연결하지 않습니다.
        """
        merged_post = post.merge()
        merged_post_to_compare = post_to_compare.merge()
        if merged_post.discovered_at and merged_post_to_compare.discovered_at:
            if merged_post.discovered_at > merged_post_to_compare.discovered_at:
                # post가 post_to_compare보다 나중에 생성되었을 경우 post -> post_to_compare
                merged_post.similar_to.connect(merged_post_to_compare)
            else:
                # post가 post_to_compare보다 먼저 생성되었을 경우 post_to_compare -> post
                merged_post_to_compare.similar_to.connect(merged_post)


class Sells(StructuredRel):
    """채널이 특정 은어로 판매 정황을 보이는 관계(SELLS).

    message_ids 배열로 해당 정황이 관측된 텔레그램 메시지 ID를 누적합니다.
    """
    message_ids = ArrayProperty(IntegerProperty(), default=[])

    @classmethod
    def merge(
            cls,
            channel: 'ChannelNode',
            argot: 'ArgotNode',
            message_id: int,
    ):
        """채널과 은어 노드를 업서트하고 메시지 ID를 관계 속성에 누적합니다.

        트랜잭션으로 관계를 조회/갱신하여 동시성 이슈를 완화합니다.
        """
        merged_channel = channel.merge()
        merged_argot = argot.merge()
        with db.transaction:
            rel = merged_channel.sells.relationship(merged_argot)
            if rel:
                # 관계가 이미 존재할 경우
                rel.message_ids.append(message_id)
                rel.save()
            else:
                # 관계가 없으면 새로운 관계를 생성하고 배열 초기화
                merged_channel.sells.connect(merged_argot, {"message_ids": [message_id]})


class RefersTo(StructuredRel):
    """은어가 특정 약물을 지칭하는 관계(REFERS_TO)."""

    @classmethod
    def merge(
            cls,
            argot: 'ArgotNode',
            drug: 'DrugNode',
    ):
        """은어와 약물 노드를 업서트하고 REFERS_TO 관계를 연결합니다."""
        merged_argot = argot.merge()
        merged_drug = drug.merge()
        merged_argot.refers_to.connect(merged_drug)


class PostNode(StructuredNode):
    """웹 게시글 노드.

    MongoDB의 posts 문서를 그래프 노드로 투영합니다.
    """
    __label__ = "Post"
    post_id = StringProperty(index=True)
    title = StringProperty()
    link = StringProperty(unique_index=True, required=True)
    domain = StringProperty()
    site_name = StringProperty()
    content = StringProperty()
    cluster = IntegerProperty()
    discovered_at = DateTimeProperty()
    updated_at = DateTimeProperty(default_now=True)
    is_deleted = BooleanProperty(default=False)

    promotes = RelationshipTo("ChannelNode", "PROMOTES", model=Promotes)
    similar_to = RelationshipTo("PostNode", "SIMILAR_TO", model=SimilarTo)
    similar_posts = RelationshipFrom("PostNode", "SIMILAR_TO")

    def merge(self) -> Self:
        """자신을 속성값 기준으로 업서트하고 upsert된 노드를 반환합니다."""
        self.updated_at = datetime.now()
        properties = {k: v for k, v in self.__properties__.items() if v is not None}
        upserted = self.__class__.create_or_update(properties)[0]
        return upserted

    @classmethod
    def from_mongo(cls, post: dict) -> Self:
        """MongoDB 포스트 문서에서 PostNode 인스턴스를 생성합니다."""
        return cls(
            post_id=post.get("_id"),
            title=post.get(PostFields.title),
            link=post.get(PostFields.link),
            domain=post.get(PostFields.domain),
            site_name=post.get(PostFields.site_name),
            content=post.get(PostFields.text),
            cluster=post.get(PostFields.cluster),
            discovered_at=post.get(PostFields.discovered_at),
        )


class ChannelNode(StructuredNode):
    """텔레그램 채널 노드.

    MongoDB의 channels 문서를 그래프 노드로 투영합니다.
    """
    __label__ = "Channel"
    channel_id = StringProperty(unique_index=True, required=True)
    status = StringProperty()
    title = StringProperty()
    username = StringProperty()

    sells = RelationshipTo("ArgotNode", "SELLS", model=Sells)

    posts = RelationshipFrom("PostNode", "PROMOTES")

    def merge(self) -> Self:
        """자신을 속성값 기준으로 업서트하고 upsert된 노드를 반환합니다."""
        channel: ChannelNode
        properties = {k: v for k, v in self.__properties__.items() if v is not None}
        upserted = self.__class__.create_or_update(properties)[0]
        return upserted

    @classmethod
    def from_mongo(cls, channel: dict) -> Self:
        """MongoDB 채널 문서에서 ChannelNode 인스턴스를 생성합니다."""
        return cls(
            channel_id=channel.get(ChannelFields.channel_id),
            status=channel.get(ChannelFields.status),
            title=channel.get(ChannelFields.title),
            username=channel.get(ChannelFields.username),
        )


class ArgotNode(StructuredNode):
    """은어(은어/속어) 노드.

    판매 정황 탐지 시 채널이 사용하는 용어를 표준화하여 수집합니다.
    """
    __label__ = "Argot"
    name = StringProperty(unique_index=True)
    description = StringProperty()

    refers_to = RelationshipTo("DrugNode", "REFERS_TO", model=RefersTo)

    channels = RelationshipFrom("ChannelNode", "SELLS")

    def merge(self) -> 'ArgotNode':
        """자신을 속성값 기준으로 업서트하고 upsert된 노드를 반환합니다."""
        properties = {k: v for k, v in self.__properties__.items() if v is not None}
        upserted = self.__class__.create_or_update(properties)[0]
        return upserted


class DrugNode(StructuredNode):
    """약물 엔티티 노드.

    외부 레퍼런스(drugbank_id)와 한/영 이름, 타입 등의 속성을 가집니다.
    """
    __label__ = "Drug"
    drugbank_id = StringProperty(unique_index=True)
    name = StringProperty(index=True)
    english_name = StringProperty()
    drug_type = StringProperty()

    argots = RelationshipFrom("ArgotNode", "REFERS_TO")

    def merge(self) -> 'DrugNode':
        """자신을 속성값 기준으로 업서트하고 upsert된 노드를 반환합니다."""
        properties = {k: v for k, v in self.__properties__.items() if v is not None}
        upserted = self.__class__.create_or_update(properties)[0]
        return upserted

    @classmethod
    def from_mongo(cls, drug: dict) -> Self:
        """MongoDB 약물 문서에서 DrugNode 인스턴스를 생성합니다."""
        return cls(
            drug_id=drug.get("drugbank_id"),
            english_name=drug.get("english_name"),
            drug_type=drug.get("drug_type")
        )
