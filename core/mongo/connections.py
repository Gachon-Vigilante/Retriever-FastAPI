import os
from typing import Optional
from functools import lru_cache

import pymongo
from dotenv import load_dotenv

from utils import Logger


logger = Logger(__name__)

load_dotenv()

class MongoCollections:
    """
    컬렉션들을 중앙 관리하는 오브젝트.
    getter로 컬렉션을 호출하지만, 캐시 때문에 한 번만 호출 후 재사용됩니다.
    """
    def __init__(self, db: pymongo.database.Database = None):
        if db and not isinstance(db, pymongo.database.Database):
            raise TypeError("Database object must be provided with pymongo.database.Database type.")
        self.db = db or mongo_client()[os.getenv('MONGO_DB_NAME')]

    @property
    @lru_cache(maxsize=1)
    def channels(self) -> pymongo.collection.Collection:
        return self.db.channels

    @property
    @lru_cache(maxsize=1)
    def chats(self) -> pymongo.collection.Collection:
        return self.db.chats


_mongo_client: Optional[pymongo.MongoClient] = None

@lru_cache(maxsize=1)
def mongo_client():
    """MongoDB 클라이언트를 지연 생성하고 캐시합니다."""

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