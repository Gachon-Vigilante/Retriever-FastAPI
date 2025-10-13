import umap.umap_ as umap
import numpy as np
import hdbscan
import re
from scipy.sparse import lil_matrix
from sklearn.metrics.pairwise import cosine_similarity,euclidean_distances
from collections import Counter
from core.mongo.connections import MongoCollections
from utils import Logger
from pymongo import UpdateOne
from sklearn.preprocessing import MinMaxScaler  
from sklearn.metrics import silhouette_score, davies_bouldin_score , silhouette_samples
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import datetime

# post_similarity 모듈에서 텍스트 전처리 함수를 가져옵니다.
from clustering.post_similarity import preprocess_text

mongo = MongoCollections()
collection = mongo.posts
logger = Logger(__name__)

# --- 기존 함수들 (변경 없음) ---

def _run_single_hdbscan_clustering(embeddings, min_cluster_size=15, min_samples=8, n_neighbors=15, n_components=15):
    # ... (이하 기존 코드와 동일)
    pass

def perform_clustering_with_HDBSCAN(min_cluster_size=15, min_samples=8, n_neighbors=15, n_components=15):
    # ... (이하 기존 코드와 동일)
    pass

def perform_ensemble_clustering(param_sets=None, final_min_cluster_size=10, final_min_samples=None):
    # ... (이하 기존 코드와 동일)
    pass

# --- 신규 하이브리드 클러스터링 기능 추가 ---

def calculate_jaccard_distance_matrix(texts: list[str]) -> np.ndarray:
    """
    주어진 텍스트 목록에 대해 Jaccard 거리 행렬을 계산합니다.
    Jaccard Distance = 1 - Jaccard Similarity
    """
    logger.info(f"{len(texts)}개 문서에 대한 Jaccard 거리 행렬 계산 시작...")

    # 간단한 토크나이저: 2글자 이상의 한글, 영문, 숫자만 추출
    token_pattern = r'\b[a-zA-Z0-9가-힣]{2,}\b'
    
    # 각 문서를 단어 집합(set)으로 변환
    corpus_sets = [set(re.findall(token_pattern, text.lower())) for text in texts]
    
    num_docs = len(texts)
    distance_matrix = np.zeros((num_docs, num_docs))

    for i in range(num_docs):
        for j in range(i, num_docs):
            if i == j:
                continue
            
            set1 = corpus_sets[i]
            set2 = corpus_sets[j]
            
            intersection = len(set1.intersection(set2))
            union = len(set1.union(set2))
            
            similarity = intersection / union if union != 0 else 0
            
            distance = 1 - similarity
            distance_matrix[i, j] = distance
            distance_matrix[j, i] = distance
            
    logger.info("Jaccard 거리 행렬 계산 완료.")
    return distance_matrix

def cluster_with_hybrid_metric(
    weights={'semantic': 0.7, 'structural': 0.3},
    min_cluster_size=15, 
    min_samples=8, 
    n_neighbors=15, 
    n_components=15
):
    """
    의미적 거리(코사인)와 구조적 거리(Jaccard)를 결합한 하이브리드 거리 행렬을 사용해 클러스터링을 수행합니다.
    """
    documents = list(collection.find(
        {"embedding": {"$exists": True}},
        {"_id": 1, "embedding": 1, "link": 1, "content": 1} 
    ))
    
    if len(documents) < min_cluster_size:
        return {"error": "Not enough documents with embeddings to cluster."}

    logger.info(f"총 {len(documents)}개 게시물에 대한 하이브리드 클러스터링 시작.")
    
    ids = [doc["_id"] for doc in documents]
    embeddings = np.array([doc["embedding"] for doc in documents])
    corpus = [preprocess_text(doc.get('content', '')) for doc in documents]

    # 1. 의미적 거리 행렬 계산
    semantic_dist_matrix = 1 - cosine_similarity(embeddings)

    # 2. 구조적 거리 행렬 계산
    structural_dist_matrix = calculate_jaccard_distance_matrix(corpus)

    # 3. 두 거리 행렬의 스케일 정규화
    scaler = MinMaxScaler()
    norm_semantic_dist = scaler.fit_transform(semantic_dist_matrix)
    norm_structural_dist = scaler.fit_transform(structural_dist_matrix)

    # 4. 가중치를 적용하여 최종 거리 행렬 생성
    logger.info(f"거리 행렬 결합 (가중치: semantic={weights['semantic']}, structural={weights['structural']})")
    combined_dist_matrix = (
        weights['semantic'] * norm_semantic_dist +
        weights['structural'] * norm_structural_dist
    )

    # 5. UMAP과 HDBSCAN에 'precomputed' metric 사용
    logger.info("사전 계산된 거리 행렬로 UMAP 및 HDBSCAN 실행...")
    umap_model = umap.UMAP(
        n_neighbors=n_neighbors, 
        n_components=n_components,
        min_dist=0.0, 
        metric='precomputed',
        random_state=42
    )
    umap_embeddings = umap_model.fit_transform(combined_dist_matrix)

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size, 
        min_samples=min_samples,
        metric='euclidean',
        cluster_selection_method='eom'
    )
    labels = clusterer.fit_predict(umap_embeddings)

    # 6. 결과 저장 및 반환
    bulk_ops = []
    for idx, doc_id in enumerate(ids):
        cluster_label = int(labels[idx])
        bulk_ops.append(UpdateOne({"_id": doc_id}, {"$set": {"hybrid_cluster_label": cluster_label}}))
    
    if bulk_ops:
        collection.bulk_write(bulk_ops)

    mask = labels != -1
    silhouette_avg = -1
    if np.sum(mask) > 1 and len(set(labels[mask])) > 1:
        silhouette_avg = silhouette_score(umap_embeddings[mask], labels[mask])

    cluster_dist = {int(k): int(v) for k, v in Counter(labels).items()}
    logger.info("하이브리드 클러스터링 완료.")

    return {
        "message": "Clustering with Hybrid Metric (Semantic + Structural) completed.",
        "weights": weights,
        "total_documents": len(documents),
        "clustered_documents": int(np.sum(mask)),
        "noise_documents": int(list(labels).count(-1)),
        "number_of_clusters": len(set(labels)) - (1 if -1 in labels else 0),
        "cluster_distribution": cluster_dist,
        "silhouette_score": float(silhouette_avg)
    }

# --- 나머지 기존 함수들 ---

def save_silhouette_plot(distance_matrix, labels, filename_prefix="silhouette_plot"):
    pass

def calculate_custom_distance_matrix(documents, weights, umap_params):
    pass


def cluster_with_custom_metric(umap_params, weights, hdbscan_params):
    pass
