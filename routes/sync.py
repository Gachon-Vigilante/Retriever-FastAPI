from fastapi import APIRouter
from bson import ObjectId

from core.mongo.channel import ChannelFields
from core.mongo.connections import MongoCollections
from core.mongo.message import MessageFields
from core.mongo.post import PostFields
from core.neo4j.ogm import PostNode, ChannelNode, ArgotNode, Promotes, SimilarTo, Sells
from utils import Logger
from .responses import SuccessfulResponse

logger = Logger(__name__)

sync_router = APIRouter(prefix="/api/v1/sync")

@sync_router.patch("", response_model=SuccessfulResponse)
async def synchronize_mongo_and_neo4j():
    """
    """
    posts_collection = MongoCollections().posts
    channel_collection = MongoCollections().channels
    for post_doc in posts_collection.find({"analysis.drugs_related": {"$ne": False}}):
        PostNode.from_mongo(post_doc).merge()

    for channel_doc in channel_collection.find():
        ChannelNode.from_mongo(channel_doc).merge()

    pipeline = [
        # 1. 'analysis.promotions' 배열을 풉니다.
        {
            "$unwind": "$analysis.promotions"
        },

        # 2. 'analysis.promotions.identifiers' 배열을 풉니다.
        {
            "$unwind": "$analysis.promotions.identifiers"
        },

        # 3. 'channel_id'가 존재하고 null이 아닌 문서만 남깁니다.
        {
            "$match": {
                "analysis.promotions.identifiers.channel_id": {"$ne": None}
            }
        },

        # 4. (수정됨) 4번($replaceRoot)과 5번(기존 $project)을 이 단계로 교체합니다.
        #    결과 문서의 형식을 "link"와 "channel_id"만 포함하도록 지정합니다.
        {
            "$project": {
                # _id는 기본적으로 포함되므로 명시적으로 제외
                "_id": 0,

                # 원본 문서의 'link' 필드를 그대로 가져옵니다.
                PostFields.link: "$link",

                # 현재 unwind된 경로에서 'channel_id' 값을 가져옵니다.
                ChannelFields.channel_id: "$analysis.promotions.identifiers.channel_id"
            }
        }
    ]

    # 집계 파이프라인 실행
    # .aggregate()는 커서(cursor)를 반환하므로 for-loop로 순회할 수 있습니다.
    for result in posts_collection.aggregate(pipeline):
        Promotes.merge(
            PostNode(link=result.get(PostFields.link)),
            ChannelNode(channel_id=result.get(ChannelFields.channel_id))
        )
    logger.info("All promotions are synchronized.")

    for post in posts_collection.find({"analysis.drugs_related": {"$ne": False}}, projection={
        PostFields.link: 1,
        PostFields.similarities: 1
    }):
        for similar_post_info in post.get(PostFields.similarities, []):
            similar_post = posts_collection.find_one({
                "_id": ObjectId(similar_post_info["post_id"]),
                "analysis.drugs_related": {"$ne": False}
            }, projection={
                PostFields.link: 1,
            })
            if not similar_post: continue
            SimilarTo.merge(
                PostNode(link=post.get(PostFields.link)),
                PostNode(link=similar_post.get(PostFields.link)),
                score=similar_post_info["similarity"]
            )
    logger.info("All similarities are synchronized.")

    for message in MongoCollections().messages.find(projection={
        MessageFields.message: 1,
        MessageFields.channel_id: 1,
        MessageFields.message_id: 1,
    }):
        for argot in MongoCollections().drugs.distinct("argots.name"):
            if argot in message.get(MessageFields.message):
                Sells.merge(
                    ChannelNode(channel_id=message.get(MessageFields.channel_id)),
                    ArgotNode(name=argot),
                    message_id=message.get(MessageFields.message_id)
                )
    logger.info("All sells are synchronized.")

    return SuccessfulResponse(message="All data from mongo to neo4j is synchronized.")
