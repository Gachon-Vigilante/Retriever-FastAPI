import os
from typing import Self
from dotenv import load_dotenv
from datetime import datetime

from neomodel import (
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
        if merged_post.createdAt and merged_post_to_compare.createdAt:
            if merged_post.createdAt > merged_post_to_compare.createdAt:
                # post가 post_to_compare보다 나중에 생성되었을 경우 post -> post_to_compare
                merged_post.similar_to.connect(merged_post_to_compare)
            else:
                # post가 post_to_compare보다 먼저 생성되었을 경우 post_to_compare -> post
                merged_post_to_compare.similar_to.connect(merged_post)


class Sells(StructuredRel):
    messageIds = ArrayProperty(IntegerProperty())

    @classmethod
    def merge(
            cls,
            channel: 'ChannelNode',
            argot: 'ArgotNode',
    ):
        merged_channel = channel.merge()
        merged_argot = argot.merge()
        merged_channel.sells.connect(merged_argot)

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
    postId = StringProperty(index=True)
    title = StringProperty()
    link = StringProperty(unique_index=True, required=True)
    domain = StringProperty()
    siteName = StringProperty()
    content = StringProperty()
    cluster = IntegerProperty()
    createdAt = DateTimeProperty()
    updatedAt = DateTimeProperty(default_now=True)
    is_deleted = BooleanProperty(default=False, db_property="deleted")

    promotes = RelationshipTo("ChannelNode", "PROMOTES", model=Promotes)
    similar_to = RelationshipTo("PostNode", "SIMILAR_TO", model=SimilarTo)
    similar_posts = RelationshipFrom("PostNode", "SIMILAR_TO")

    def merge(self) -> Self:
        self.updatedAt = datetime.now()
        properties = {k: v for k, v in self.__properties__.items() if v is not None}
        upserted = self.__class__.create_or_update(properties)[0]
        return upserted

class ChannelNode(StructuredNode):
    __label__ = "Channel"
    channelId = StringProperty(unique_index=True, required=True)
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

class ArgotNode(StructuredNode):
    __label__ = "Argot"
    name = StringProperty(unique_index=True)

    refers_to = RelationshipTo("DrugNode", "REFERS_TO", model=RefersTo)

    channels = RelationshipFrom("ChannelNode", "SELLS")

    def merge(self) -> 'ArgotNode':
        properties = {k: v for k, v in self.__properties__.items() if v is not None}
        upserted = self.__class__.create_or_update(properties)[0]
        return upserted

class DrugNode(StructuredNode):
    __label__ = "Drug"
    name = StringProperty(index=True)
    drugId = StringProperty(unique_index=True)
    englishName = StringProperty()
    drugType = StringProperty()

    argots = RelationshipFrom("ArgotNode", "REFERS_TO")

    def merge(self) -> 'DrugNode':
        properties = {k: v for k, v in self.__properties__.items() if v is not None}
        upserted = self.__class__.create_or_update(properties)[0]
        return upserted

