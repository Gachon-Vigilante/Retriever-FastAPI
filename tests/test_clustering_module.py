import pytest
from pymongo import MongoClient
import os
import numpy as np
from dotenv import load_dotenv

# 테스트 대상 함수 import
from clustering.post_similarity import embeddings
from clustering.post import perform_clustering_with_HDBSCAN

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
    # HDBSCAN의 min_cluster_size 기본값이 15이므로, 테스트에서는 더 작은 값으로 실행할 예정
    # 의미적으로 구분되는 3개의 그룹과 노이즈 1개를 생성
    test_data = [
        # 그룹 1 (값 0.1 근처)
        {"_id": "cluster_post_1", "embedding": np.random.normal(0.1, 0.01, 10).tolist()},
        {"_id": "cluster_post_2", "embedding": np.random.normal(0.1, 0.01, 10).tolist()},
        # 그룹 2 (값 0.5 근처)
        {"_id": "cluster_post_3", "embedding": np.random.normal(0.5, 0.01, 10).tolist()},
        {"_id": "cluster_post_4", "embedding": np.random.normal(0.5, 0.01, 10).tolist()},
        # 그룹 3 (값 0.9 근처)
        {"_id": "cluster_post_5", "embedding": np.random.normal(0.9, 0.01, 10).tolist()},
        {"_id": "cluster_post_6", "embedding": np.random.normal(0.9, 0.01, 10).tolist()},
        # 노이즈
        {"_id": "cluster_post_7", "embedding": np.random.rand(10).tolist()},
    ]
    posts_collection.insert_many(test_data)
    yield
    posts_collection.delete_many({"_id": {"$regex": "^cluster_post_"}})

def test_embeddings_generation(posts_collection, setup_embedding_test):
    """embeddings() 함수가 게시물에 임베딩 필드를 생성하는지 테스트"""
    result = embeddings()
    assert "message" in result
    assert "generated for 3 documents" in result["message"]

    updated_posts = list(posts_collection.find({"_id": {"$in": ["emb_post_1", "emb_post_2", "emb_post_3"]}}))
    assert len(updated_posts) == 3
    for post in updated_posts:
        assert "embedding" in post
        assert isinstance(post["embedding"], list) and len(post["embedding"]) > 0
        assert all(isinstance(x, float) for x in post["embedding"])

def test_hdbscan_clustering(posts_collection, setup_clustering_test):
    """perform_clustering_with_HDBSCAN() 함수가 클러스터 레이블을 생성하는지 테스트"""
    # 1. 테스트 함수 실행
    # 테스트 데이터가 적으므로, 클러스터링이 가능하도록 파라미터 조정
    result = perform_clustering_with_HDBSCAN(min_cluster_size=2, min_samples=1, n_neighbors=2, n_components=2)
    
    # 2. 결과 메시지 검증
    assert "message" in result
    assert result["total_documents"] == 7
    assert result["number_of_clusters"] > 0 # 최소 하나 이상의 클러스터가 생성되어야 함

    # 3. 데이터베이스 확인
    updated_posts = list(posts_collection.find({"_id": {"$regex": "^cluster_post_"}}))
    assert len(updated_posts) == 7
    
    labeled_count = 0
    for post in updated_posts:
        # 'cluster_label' 필드가 존재하는지 확인
        assert "cluster_label" in post
        # 'cluster_label'이 정수인지 확인
        assert isinstance(post["cluster_label"], int)
        if post["cluster_label"] != -1:
            labeled_count += 1
            
    # 최소한 일부 게시물은 클러스터에 할당되어야 함 (모두 노이즈(-1)는 아니어야 함)
    assert labeled_count > 0
