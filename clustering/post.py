import umap.umap_ as umap
import numpy as np
import hdbscan
import re
from collections import Counter

from core.mongo.connections import MongoCollections
from utils import Logger
from pymongo import UpdateOne
from sklearn.metrics import silhouette_score

from core.neo4j.ogm import PostNode
from core.mongo.post import PostFields

mongo = MongoCollections()
collection = mongo.posts
logger = Logger(__name__)


# --- Helper Functions ---

def _get_char_ngrams(text: str, n: int = 3) -> set:
    """
    주어진 텍스트를 정규화하고, 문자 n-gram의 집합으로 변환합니다.
    - 소문자 변환
    - 한글, 영어 알파벳, 숫자를 제외한 모든 문자 제거
    """
    # 1. 소문자로 변환
    text = text.lower()
    # 2. 한글, 영어, 숫자를 제외한 모든 문자를 공백으로 변환
    text = re.sub(r'[^a-z0-9가-힣]', ' ', text)
    # 3. 여러 개의 공백을 하나로 합치고, 양쪽 끝 공백 제거
    text = ' '.join(text.split())
    # 4. 최종적으로 모든 공백 제거 후 n-gram 생성
    text = ''.join(text.split())
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def calculate_jaccard_distance_matrix(texts: list[str]) -> np.ndarray:
    """
    주어진 텍스트 목록에 대해 문자 3-gram 기반 Jaccard 거리 행렬을 계산합니다.
    """
    logger.info(f"Calculating Jaccard distance matrix for {len(texts)} documents...")
    corpus_sets = [_get_char_ngrams(text, n=3) for text in texts]
    num_docs = len(texts)
    distance_matrix = np.zeros((num_docs, num_docs))
    for i in range(num_docs):
        for j in range(i, num_docs):
            if i == j: continue
            set1, set2 = corpus_sets[i], corpus_sets[j]
            intersection = len(set1.intersection(set2))
            union = len(set1.union(set2))
            similarity = intersection / union if union != 0 else 0
            distance = 1 - similarity
            distance_matrix[i, j] = distance_matrix[j, i] = distance
    logger.info("Jaccard distance matrix calculation complete.")
    return distance_matrix


def perform_multi_view_clustering(
        weights={'id': 0.5, 'template': 0.5},
        min_cluster_size=3,
        min_samples=1,
        n_neighbors=15,
        n_components=10,
        similarity_threshold=0.7
):
    """
    'ID'와 '전체 템플릿'의 거리 행렬을 직접 가중 합산하여,
    더 정교한 최종 클러스터링을 수행하고 유사도 정보를 저장합니다.
    """
    documents = list(collection.find({}, {"_id": 1, PostFields.title: 1, PostFields.link: 1}))
    if len(documents) < min_cluster_size:
        return {"error": "Not enough documents to cluster."}

    logger.info(f"Starting multi-view clustering for {len(documents)} documents.")

    ids = [doc["_id"] for doc in documents]
    links = [doc.get(PostFields.link) for doc in documents]
    titles = [doc.get(PostFields.title, '') for doc in documents]
    num_docs = len(documents)

    # 1. 두 가지 다른 관점의 데이터(corpus) 준비
    corpus_id_only = [re.sub(r'[^a-z0-9]', '', title.lower()) for title in titles]
    corpus_full_template = [re.sub(r'[^a-z0-9가-힣]', '', title.lower()) for title in titles]

    # 2. 각 관점의 '거리 행렬'을 직접 계산
    logger.info("Calculating distance matrix for View 1 (ID)...")
    dist_matrix_id = calculate_jaccard_distance_matrix(corpus_id_only)

    logger.info("Calculating distance matrix for View 2 (Full Template)...")
    dist_matrix_template = calculate_jaccard_distance_matrix(corpus_full_template)

    # 3. 두 거리 행렬을 가중 합산하여 최종 거리 행렬 생성
    logger.info(f"Combining distance matrices with weights: id={weights['id']}, template={weights['template']}")
    combined_dist_matrix = (
            weights['id'] * dist_matrix_id +
            weights['template'] * dist_matrix_template
    )

    # 4. 최종 거리 행렬로 UMAP -> HDBSCAN 파이프라인 실행
    logger.info("Running UMAP on the combined distance matrix...")
    umap_model = umap.UMAP(
        n_neighbors=n_neighbors,
        n_components=n_components,
        metric='precomputed',
        random_state=42
    )
    umap_embeddings = umap_model.fit_transform(combined_dist_matrix)

    logger.info("Running HDBSCAN on the UMAP embeddings...")
    final_clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric='euclidean'
    )
    final_labels = final_clusterer.fit_predict(umap_embeddings)

    bulk_ops = []
    for i, doc_id in enumerate(ids):
        cluster_label = int(final_labels[i])

        similarities = []
        for j in range(num_docs):
            if i == j: continue
            similarity_score = 1.0 - combined_dist_matrix[i][j]
            if similarity_score >= similarity_threshold:
                similarities.append({
                    "post_id": str(ids[j]),
                    "similarity": float(similarity_score)
                })

        bulk_ops.append(
            UpdateOne(
                {"_id": doc_id},
                {
                    "$set": {
                        PostFields.cluster: cluster_label,
                        PostFields.similarities: sorted(similarities, key=lambda x: -x["similarity"])
                    }
                }
            )
        )

        if links[i]:
            post_node = PostNode(link=links[i], cluster=cluster_label)
            post_node.merge()

    if bulk_ops:
        collection.bulk_write(bulk_ops)

    mask = final_labels != -1
    silhouette_avg = -1
    if np.sum(mask) > 1 and len(set(final_labels[mask])) > 1:
        silhouette_avg = silhouette_score(umap_embeddings[mask], final_labels[mask])

    cluster_dist = {int(k): int(v) for k, v in Counter(final_labels).items()}
    logger.info("Multi-view clustering completed.")

    return {
        "message": "Multi-view clustering (Distance Combination) completed.",
        "weights": weights,
        "total_documents": len(documents),
        "clustered_documents": int(np.sum(mask)),
        "noise_documents": int(list(final_labels).count(-1)),
        "number_of_clusters": len(set(final_labels)) - (1 if -1 in final_labels else 0),
        "cluster_distribution": cluster_dist,
        "silhouette_score": float(silhouette_avg)
    }