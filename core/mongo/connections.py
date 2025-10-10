"""MongoDB 연결 및 컬렉션 관리 모듈 - PyMongo 기반 데이터베이스 연결 관리

이 모듈은 MongoDB 데이터베이스 연결을 관리하고, 컬렉션에 대한 중앙 집중식 접근을 제공합니다.
연결 풀링, 캐싱, 에러 핸들링을 통해 안정적인 데이터베이스 연결을 보장하며,
환경 변수를 통한 설정 관리를 지원합니다.

MongoDB Connection and Collection Management Module - Database connection management based on PyMongo

This module manages MongoDB database connections and provides centralized access to collections.
It ensures stable database connections through connection pooling, caching, and error handling,
and supports configuration management through environment variables.
"""

import os
from typing import Optional
from functools import lru_cache

import pymongo
from dotenv import load_dotenv
from pymongo.errors import CollectionInvalid

from utils import Logger


logger = Logger(__name__)

load_dotenv()

db_name = os.getenv('MONGO_DB_NAME')

class MongoCollections:
    """MongoDB 컬렉션들을 중앙 관리하는 클래스

    애플리케이션에서 사용하는 모든 MongoDB 컬렉션에 대한 중앙 집중식 접근점을 제공합니다.
    각 컬렉션은 프로퍼티로 접근할 수 있으며, LRU 캐시를 통해 성능을 최적화합니다.
    데이터베이스 객체를 직접 전달하거나 환경 변수를 통해 자동 연결할 수 있습니다.

    Centralized management class for MongoDB collections

    Provides centralized access point to all MongoDB collections used in the application.
    Each collection can be accessed through properties, with performance optimized through LRU cache.
    Can accept database objects directly or connect automatically through environment variables.

    Attributes:
        db (pymongo.database.Database): MongoDB 데이터베이스 객체
                                      MongoDB database object

    Examples:
        # 기본 연결 사용
        collections = MongoCollections()
        channels = collections.channels

        # 특정 데이터베이스 객체 사용
        custom_db = pymongo.MongoClient()["custom_db"]
        collections = MongoCollections(db=custom_db)
    """

    def __init__(self, db: pymongo.database.Database = None):
        """MongoCollections 인스턴스를 초기화합니다.

        데이터베이스 객체를 직접 받거나, 환경 변수를 통해 자동으로 연결합니다.
        유효하지 않은 데이터베이스 객체가 전달되면 TypeError를 발생시킵니다.

        Initialize MongoCollections instance.

        Accepts database object directly or connects automatically through environment variables.
        Raises TypeError if invalid database object is provided.

        Args:
            db (Optional[pymongo.database.Database]): MongoDB 데이터베이스 객체.
                                                     None인 경우 환경 변수를 통해 자동 연결
                                                     MongoDB database object.
                                                     If None, connects automatically through environment variables

        Raises:
            TypeError: 전달된 db 객체가 pymongo.database.Database 타입이 아닌 경우
                      When provided db object is not of pymongo.database.Database type
        """
        if db and not isinstance(db, pymongo.database.Database):
            raise TypeError("Database object must be provided with pymongo.database.Database type.")
        if not db and not db_name:
            raise EnvironmentError("To use default MongoDB instance, MONGO_DB_NAME environment variable must be set.")
        self.db = db or mongo_client()[db_name]

    @property
    @lru_cache(maxsize=1)
    def channels(self) -> pymongo.collection.Collection:
        """채널 정보를 저장하는 MongoDB 컬렉션에 접근합니다.

        텔레그램 채널의 메타데이터, 상태, 설정 등을 저장하는 컬렉션입니다.
        LRU 캐시를 통해 반복 접근 시 성능을 최적화합니다.
        Access MongoDB collection for storing channel information.
        Collection that stores Telegram channel metadata, status, settings, etc.
        Performance is optimized for repeated access through LRU cache.
        Returns:
            pymongo.collection.Collection: channels 컬렉션 객체
                                            channels collection object
        """
        return self.db.channels

    @property
    @lru_cache(maxsize=1)
    def chats(self) -> pymongo.collection.Collection:
        """채팅 메시지를 저장하는 MongoDB 컬렉션에 접근합니다.

        텔레그램 채팅방과 채널에서 수집된 메시지들을 저장하는 컬렉션입니다.
        LRU 캐시를 통해 반복 접근 시 성능을 최적화합니다.

        Access MongoDB collection for storing chat messages.

        Collection that stores messages collected from Telegram chatrooms and channels.
        Performance is optimized for repeated access through LRU cache.

        Returns:
            pymongo.collection.Collection: chats 컬렉션 객체
                                            chats collection object
        """
        return self.db.chats

    @property
    @lru_cache(maxsize=1)
    def posts(self) -> pymongo.collection.Collection:
        return self.db.posts

    @property
    @lru_cache(maxsize=1)
    def post_similarity(self) -> pymongo.collection.Collection:
        return self.db.post_similarity

    @property
    @lru_cache(maxsize=1)
    def drugs(self) -> pymongo.collection.Collection:
        return self.db.drugs

    @property
    @lru_cache(maxsize=1)
    def channel_data(self) -> pymongo.collection.Collection:
        return self.db.channel_data

    @property
    @lru_cache(maxsize=1)
    def channel_similarity(self) -> pymongo.collection.Collection:
        return self.db.channel_similarity

    @property
    @lru_cache(maxsize=1)
    def channel_info(self) -> pymongo.collection.Collection:
        return self.db.channel_info

    @property
    @lru_cache(maxsize=1)
    def posts(self) -> pymongo.collection.Collection:
        """웹 게시물을 저장하는 MongoDB 컬렉션에 접근합니다.

        온라인에서 크롤링된 웹 게시물들을 저장하는 컬렉션입니다.
        LRU 캐시를 통해 반복 접근 시 성능을 최적화합니다.

        Access MongoDB collection for storing online web posts.

        Collection that stores posts collected from web(e.g. Google, X) by crawling.
        Performance is optimized for repeated access through LRU cache.

        Returns:
            pymongo.collection.Collection: posts 컬렉션 객체
                                          posts collection object
        """
        return self.db.posts

    @property
    @lru_cache(maxsize=1)
    def analysis_jobs(self) -> pymongo.collection.Collection:
        """Gemini 배치 작업 컬렉션"""
        return self.db.analysis_jobs

_mongo_client: Optional[pymongo.MongoClient] = None

@lru_cache(maxsize=1)
def mongo_client() -> Optional[pymongo.MongoClient]:
    """MongoDB 클라이언트를 지연 생성하고 캐시하는 함수

    환경 변수에서 연결 문자열을 읽어 MongoDB 클라이언트를 생성합니다.
    전역 변수를 통해 싱글톤 패턴을 구현하며, LRU 캐시로 성능을 최적화합니다.
    연결 실패 시 로그를 남기고 None을 반환합니다.

    Function to lazily create and cache MongoDB client

    Creates MongoDB client by reading connection string from environment variables.
    Implements singleton pattern through global variables and optimizes performance with LRU cache.
    Logs errors and returns None on connection failure.

    Returns:
        Optional[pymongo.MongoClient]: MongoDB 클라이언트 객체 또는 None (연결 실패 시)
                                     MongoDB client object or None (on connection failure)

    Environment Variables:
        MONGO_CONNECTION_STRING (str): MongoDB 연결 문자열
                                     MongoDB connection string

    Examples:
        client = mongo_client()
        if client:
            db = client["mydb"]
            collection = db["mycollection"]

    Note:
        연결 설정:
        Connection settings:
        - serverSelectionTimeoutMS=5000: 서버 선택 타임아웃 5초
                                        Server selection timeout 5 seconds
        - retryWrites=True: 쓰기 작업 재시도 활성화
                           Enable write operation retry
        - retryReads=True: 읽기 작업 재시도 활성화
                          Enable read operation retry
    """

    global _mongo_client

    if _mongo_client is None:
        connection_string = os.getenv("MONGO_CONNECTION_STRING")
        if not connection_string:
            return None

        try:
            _mongo_client = pymongo.MongoClient(
                connection_string,
                serverSelectionTimeoutMS=5000,
                retryWrites=True,
                retryReads=True
            )
            # 연결 테스트
            _mongo_client.admin.command('ping')
        except Exception as e:
            logger.critical(f"MongoDB 연결 실패: {e}")
            return None

    return _mongo_client

collections = MongoCollections()
default_db = mongo_client()[db_name]
collection_names = [
    collections.channels.name,
    collections.chats.name,
    collections.posts.name,
    collections.analysis_jobs.name,
]
for collection_name in collection_names:
    try:
        default_db.create_collection(collection_name)
    except CollectionInvalid:
        pass

collections.channels.create_index([
    ("id", 1),
    ("username", 1),
    ("title", 1)
], unique=True)

collections.chats.create_index([
    ("message_id", 1),
    ("chat_id", 1),
    ("edit_date", 1),
], unique=True)

collections.analysis_jobs.create_index(
    [("status", 1)],
    unique=True,
    partialFilterExpression={"status": "accepting_request"}
)

collections.analysis_jobs.create_index(
    [("post_ids", 1)],
    unique=True, # 유일성을 보장한다.
    partialFilterExpression={ # 하지만 아래 조건을 만족하는 문서에만 적용한다.
        "status": {
            "$in": [
                "accepting_request",
                "pending",
                "submitted",
                "processed"
                # FAILED와 COMPLETED 상태는 여기서 제외
            ]
        }
    }
)

