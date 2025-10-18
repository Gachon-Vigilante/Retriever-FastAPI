"""클러스터링(게시글) 라우트 모듈

이 모듈은 게시글 임베딩 생성, 유사도 계산, HDBSCAN 기반 클러스터링을 위한
FastAPI 엔드포인트를 제공합니다. 대량 연산 성격이 강하므로 운영 환경에서는
배치/관리자 전용으로 사용하는 것을 권장합니다.

주의: 본 파일은 문서화만 추가되었으며, 기능 변경은 없습니다.
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, Any

from clustering.post_similarity import embeddings, similarity, generate_separate_embeddings
from clustering.newpost_similarity import new_post_insert
from clustering.post import perform_clustering_with_HDBSCAN, cluster_with_custom_metric

router = APIRouter()

@router.post("/preprocess")
def preprocess_posts():
    """게시글 임베딩(전처리) 생성 엔드포인트

    모든 게시물에 대해 하이브리드 임베딩을 생성하고 저장합니다.

    Returns:
        dict: 처리 결과 메시지.
    """
    return embeddings()

@router.post("/similarity")
def calculate_similarity(threshold: float = 0.7):
    """게시글 간 유사도 계산 엔드포인트

    전체 게시물 간의 코사인 유사도를 계산하고 MongoDB에 유사 항목을 저장합니다.

    Args:
        threshold (float): 유사도 임계값. 이 값 이상의 유사도를 가진 경우 후속 그래프 연결 등에 활용할 수 있습니다.

    Returns:
        dict: 처리 결과 메시지.
    """
    return similarity(threshold=threshold)

@router.post("/generate-separate-embeddings")
def generate_separate_embeddings_endpoint():
    """개별 임베딩/벡터 생성 엔드포인트

    각 게시물에 대해 문서 임베딩, 가격 임베딩, TF-IDF 벡터를 개별적으로 생성하여 저장합니다.

    Returns:
        dict: 처리 결과 메시지.
    """
    return generate_separate_embeddings()

@router.post("/new-post-similarity")
def new_post_similarity_endpoint():
    """신규 게시글 유사도 계산 엔드포인트

    새로 추가된 게시물과 기존 게시물 간의 유사도를 계산하고 저장합니다.

    Returns:
        dict: 처리 결과 메시지.
    """
    return new_post_insert()

@router.post("/cluster-hdbscan")
def cluster_hdbscan_endpoint(
    min_cluster_size: int = 15, 
    min_samples: int = 8, 
    n_neighbors: int = 15, 
    n_components: int = 15
):
    """HDBSCAN 기반 게시글 클러스터링 엔드포인트

    UMAP으로 차원 축소한 뒤 HDBSCAN으로 클러스터링을 수행합니다.

    Args:
        min_cluster_size (int): 클러스터 최소 크기.
        min_samples (int): 클러스터 핵심 포인트 최소 샘플 수.
        n_neighbors (int): UMAP에서 사용할 이웃 수.
        n_components (int): UMAP으로 축소할 차원 수.

    Returns:
        dict: 처리 결과(클러스터 수 등)를 포함한 메시지 또는 구현체 반환값.
    """
    return perform_clustering_with_HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        n_neighbors=n_neighbors,
        n_components=n_components
    )

# --- Model for Custom Clustering ---
class CustomClusteringRequest(BaseModel):
    """커스텀 클러스터링 요청 바디 모델

    Attributes:
        umap_params (dict[str, dict[str, Any]]): 임베딩별 UMAP 파라미터.
        weights (dict[str, float]): 임베딩 가중치. 예: {"doc": 0.5, "price": 0.2, "keyword": 0.3}
        hdbscan_params (dict[str, Any]): HDBSCAN 파라미터.
    """
    umap_params: Dict[str, Dict[str, Any]] = Field(default_factory=lambda: {
        "doc": {"n_neighbors": 15, "n_components": 5, "min_dist": 0.0, "metric": "cosine", "random_state": 42},
        "price": {"n_neighbors": 15, "n_components": 5, "min_dist": 0.0, "metric": "cosine", "random_state": 42},
        "keyword": {"n_neighbors": 15, "n_components": 5, "min_dist": 0.0, "metric": "cosine", "random_state": 42}
    })
    weights: Dict[str, float] = Field(default_factory=lambda: {"doc": 0.5, "price": 0.2, "keyword": 0.3})
    hdbscan_params: Dict[str, Any] = Field(default_factory=lambda: {"min_cluster_size": 15, "min_samples": 5, "cluster_selection_method": "eom"})

@router.post("/cluster-custom")
def cluster_custom_endpoint(request: CustomClusteringRequest):
    """커스텀 파라미터 기반 클러스터링 엔드포인트

    UMAP/HDBSCAN 파라미터와 임베딩 가중치를 직접 지정하여 클러스터링을 수행합니다.

    Args:
        request (CustomClusteringRequest): 클러스터링 파라미터 및 가중치 설정.

    Returns:
        dict: 처리 결과(클러스터 통계 등)를 포함한 메시지 또는 구현체 반환값.
    """
    return cluster_with_custom_metric(
        umap_params=request.umap_params,
        weights=request.weights,
        hdbscan_params=request.hdbscan_params
    )
