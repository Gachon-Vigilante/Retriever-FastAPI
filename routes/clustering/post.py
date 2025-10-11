from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, Any

from clustering.post_similarity import embeddings, similarity, generate_separate_embeddings
from clustering.newpost_similarity import new_post_insert
from clustering.post import perform_clustering_with_HDBSCAN, cluster_with_custom_metric

router = APIRouter()

@router.post("/preprocess")
def preprocess_posts():
    """
    모든 게시물에 대한 하이브리드 임베딩을 생성하고 저장합니다.
    """
    return embeddings()

@router.post("/similarity")
def calculate_similarity(threshold: float = 0.7):
    """
    전체 게시물 간의 유사도를 계산하고 관계를 저장합니다.
    `threshold` 값 이상의 유사도를 가진 게시물들이 연결됩니다.
    """
    return similarity(threshold=threshold)

@router.post("/generate-separate-embeddings")
def generate_separate_embeddings_endpoint():
    """
    각 게시물에 대해 문서 임베딩, 가격 임베딩, TF-IDF 벡터를
    개별적으로 생성하여 저장합니다.
    """
    return generate_separate_embeddings()

@router.post("/new-post-similarity")
def new_post_similarity_endpoint():
    """
    새로 추가된 게시물과 기존 게시물 간의 유사도를 계산합니다.
    """
    return new_post_insert()

@router.post("/cluster-hdbscan")
def cluster_hdbscan_endpoint(
    min_cluster_size: int = 15, 
    min_samples: int = 8, 
    n_neighbors: int = 15, 
    n_components: int = 15
):
    """
    UMAP과 HDBSCAN을 사용하여 게시물을 클러스터링합니다.
    - `min_cluster_size`: 클러스터의 최소 크기
    - `min_samples`: 클러스터 핵심 포인트가 되기 위한 최소 샘플 수
    - `n_neighbors`: UMAP에서 사용하는 이웃 수
    - `n_components`: UMAP으로 축소할 차원 수
    """
    return perform_clustering_with_HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        n_neighbors=n_neighbors,
        n_components=n_components
    )

# --- Model for Custom Clustering ---
class CustomClusteringRequest(BaseModel):
    umap_params: Dict[str, Dict[str, Any]] = Field(default_factory=lambda: {
        "doc": {"n_neighbors": 15, "n_components": 5, "min_dist": 0.0, "metric": "cosine", "random_state": 42},
        "price": {"n_neighbors": 15, "n_components": 5, "min_dist": 0.0, "metric": "cosine", "random_state": 42},
        "keyword": {"n_neighbors": 15, "n_components": 5, "min_dist": 0.0, "metric": "cosine", "random_state": 42}
    })
    weights: Dict[str, float] = Field(default_factory=lambda: {"doc": 0.5, "price": 0.2, "keyword": 0.3})
    hdbscan_params: Dict[str, Any] = Field(default_factory=lambda: {"min_cluster_size": 15, "min_samples": 5, "cluster_selection_method": "eom"})

@router.post("/cluster-custom")
def cluster_custom_endpoint(request: CustomClusteringRequest):
    """
    커스텀 가중치와 파라미터를 사용하여 게시물을 클러스터링합니다.
    - UMAP, HDBSCAN 파라미터와 각 임베딩의 가중치를 직접 설정할 수 있습니다.
    """
    return cluster_with_custom_metric(
        umap_params=request.umap_params,
        weights=request.weights,
        hdbscan_params=request.hdbscan_params
    )
