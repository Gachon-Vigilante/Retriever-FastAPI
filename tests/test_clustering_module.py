import pytest
from pymongo import MongoClient
import os
import numpy as np
from dotenv import load_dotenv

# 테스트 대상 함수 import
from clustering.post_similarity import embeddings
from clustering.post import (
    perform_clustering_with_HDBSCAN, 
    perform_ensemble_clustering,
    cluster_with_hybrid_metric
)

# .env 파일에서 환경 변수 로드
load_dotenv()

@pytest.fixture(scope="module")
def db_connection():
    """테스트를 위한 MongoDB 연결 Fixture"""
    connection_string = os.getenv("MONGO_CONNECTION_STRING")
    db_name = os.getenv("MONGO_DB_NAME")
    client = MongoClient(connection_string)
    db = client[db_name]
    yield db
    client.close()

@pytest.fixture
def posts_collection(db_connection):
    """posts 컬렉션에 대한 Fixture"""
    return db_connection.posts

@pytest.fixture
def setup_embedding_test(posts_collection):
    """임베딩 테스트를 위한 데이터 준비 및 정리"""
    test_data = [
        {"_id": "emb_post_1", "content": "이것은 첫 번째 테스트 게시물입니다."},
        {"_id": "emb_post_2", "content": "두 번째 게시물은 조금 더 깁니다. 임베딩 테스트를 위함입니다."},
        {"_id": "emb_post_3", "content": "세 번째 문서는 테스트 라는 단어를 포함합니다."}
    ]
    posts_collection.insert_many(test_data)
    yield
    posts_collection.delete_many({"_id": {"$in": ["emb_post_1", "emb_post_2", "emb_post_3"]}})

@pytest.fixture
def setup_clustering_test(posts_collection):
    """클러스터링 테스트를 위한 데이터 준비 및 정리"""
    # Jaccard 유사도를 위해 content 필드 추가
    test_data = [
        # 그룹 1
        {"_id": "cluster_post_1", "content": "A B C", "embedding": np.random.normal(0.1, 0.01, 10).tolist()},
        {"_id": "cluster_post_2", "content": "A B D", "embedding": np.random.normal(0.1, 0.01, 10).tolist()},
        # 그룹 2
        {"_id": "cluster_post_3", "content": "X Y Z", "embedding": np.random.normal(0.5, 0.01, 10).tolist()},
        {"_id": "cluster_post_4", "content": "X Y W", "embedding": np.random.normal(0.5, 0.01, 10).tolist()},
        # 그룹 3
        {"_id": "cluster_post_5", "content": "K L M", "embedding": np.random.normal(0.9, 0.01, 10).tolist()},
        {"_id": "cluster_post_6", "content": "K L N", "embedding": np.random.normal(0.9, 0.01, 10).tolist()},
        # 노이즈
        {"_id": "cluster_post_7", "content": "P Q R", "embedding": np.random.rand(10).tolist()},
    ]
    posts_collection.insert_many(test_data)
    yield
    posts_collection.delete_many({"_id": {"$regex": "^cluster_post_"}})

def test_embeddings_generation(posts_collection, setup_embedding_test):
    # ... (이하 기존 코드와 동일)
    pass

def test_hdbscan_clustering(posts_collection, setup_clustering_test):
    # ... (이하 기존 코드와 동일)
    pass

def test_ensemble_clustering(posts_collection, setup_clustering_test):
    # ... (이하 기존 코드와 동일)
    pass

def test_hybrid_clustering(posts_collection, setup_clustering_test):
    """cluster_with_hybrid_metric() 함수가 하이브리드 클러스터 레이블을 생성하는지 테스트"""
    # 1. 테스트 함수 실행
    result = cluster_with_hybrid_metric(
        weights={'semantic': 0.5, 'structural': 0.5},
        min_cluster_size=2,
        min_samples=1,
        n_neighbors=2,
        n_components=2
    )

    # 2. 결과 메시지 검증
    assert "message" in result
    assert result["total_documents"] == 7
    assert result["number_of_clusters"] > 0

    # 3. 데이터베이스 확인
    updated_posts = list(posts_collection.find({"_id": {"$regex": "^cluster_post_"}}))
    assert len(updated_posts) == 7

    labeled_count = 0
    for post in updated_posts:
        # 'hybrid_cluster_label' 필드가 존재하는지 확인
        assert "hybrid_cluster_label" in post
        assert isinstance(post["hybrid_cluster_label"], int)
        if post["hybrid_cluster_label"] != -1:
            labeled_count += 1
            
    # 최소한 일부 게시물은 클러스터에 할당되어야 함
    assert labeled_count > 0
