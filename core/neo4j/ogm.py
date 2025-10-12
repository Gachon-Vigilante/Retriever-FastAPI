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
    @classmethod
    def merge(
            cls,
            post: 'PostNode',
            channel: 'ChannelNode',
    ):
        merged_post = post.merge()
        merged_channel = channel.merge()
        merged_post.promotes.connect(merged_channel)


class SimilarTo(StructuredRel):
    score = FloatProperty()

    @classmethod
    def merge(
            cls,
            post: 'PostNode',
            post_to_compare: 'PostNode',
    ):
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
    message_ids = ArrayProperty(IntegerProperty(), default=[])

    @classmethod
    def merge(
            cls,
            channel: 'ChannelNode',
            argot: 'ArgotNode',
            message_id: int,
    ):
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
    @classmethod
    def merge(
            cls,
            argot: 'ArgotNode',
            drug: 'DrugNode',
    ):
        merged_argot = argot.merge()
        merged_drug = drug.merge()
        merged_argot.refers_to.connect(merged_drug)


class PostNode(StructuredNode):
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
    is_deleted = BooleanProperty(default=False, db_property="deleted")

    promotes = RelationshipTo("ChannelNode", "PROMOTES", model=Promotes)
    similar_to = RelationshipTo("PostNode", "SIMILAR_TO", model=SimilarTo)
    similar_posts = RelationshipFrom("PostNode", "SIMILAR_TO")

    def merge(self) -> Self:
        self.updated_at = datetime.now()
        properties = {k: v for k, v in self.__properties__.items() if v is not None}
        upserted = self.__class__.create_or_update(properties)[0]
        return upserted

    @classmethod
    def from_mongo(cls, post: dict) -> Self:
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
    __label__ = "Channel"
    channel_id = StringProperty(unique_index=True, required=True)
    status = StringProperty()
    title = StringProperty()
    username = StringProperty()

    sells = RelationshipTo("ArgotNode", "SELLS", model=Sells)

    posts = RelationshipFrom("PostNode", "PROMOTES")

    def merge(self) -> Self:
        channel: ChannelNode
        properties = {k: v for k, v in self.__properties__.items() if v is not None}
        upserted = self.__class__.create_or_update(properties)[0]
        return upserted

    @classmethod
    def from_mongo(cls, channel: dict) -> Self:
        return cls(
            channel_id=channel.get(ChannelFields.channel_id),
            status=channel.get(ChannelFields.status),
            title=channel.get(ChannelFields.title),
            username=channel.get(ChannelFields.username),
        )


class ArgotNode(StructuredNode):
    __label__ = "Argot"
    name = StringProperty(unique_index=True)
    description = StringProperty()

    refers_to = RelationshipTo("DrugNode", "REFERS_TO", model=RefersTo)

    channels = RelationshipFrom("ChannelNode", "SELLS")

    def merge(self) -> 'ArgotNode':
        properties = {k: v for k, v in self.__properties__.items() if v is not None}
        upserted = self.__class__.create_or_update(properties)[0]
        return upserted


class DrugNode(StructuredNode):
    __label__ = "Drug"
    drugbank_id = StringProperty(unique_index=True)
    name = StringProperty(index=True)
    english_name = StringProperty()
    drug_type = StringProperty()

    argots = RelationshipFrom("ArgotNode", "REFERS_TO")

    def merge(self) -> 'DrugNode':
        properties = {k: v for k, v in self.__properties__.items() if v is not None}
        upserted = self.__class__.create_or_update(properties)[0]
        return upserted

    @classmethod
    def from_mongo(cls, drug: dict) -> Self:
        return cls(
            drug_id=drug.get("drugbank_id"),
            english_name=drug.get("english_name"),
            drug_type=drug.get("drug_type")
        )
