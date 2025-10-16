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
from core.neo4j.ogm import PostNode

# post_similarity 모듈에서 텍스트 전처리 함수를 가져옵니다.
from clustering.post_similarity import preprocess_text

mongo = MongoCollections()
collection = mongo.posts
logger = Logger(__name__)

def _run_single_hdbscan_clustering(embeddings, min_cluster_size=15, min_samples=8, n_neighbors=15, n_components=15):
    """UMAP과 HDBSCAN을 사용하여 클러스터링 계산만 수행하는 내부 함수"""
    logger.info(f"Running UMAP (n_components={n_components}) and HDBSCAN (min_cluster_size={min_cluster_size})...")
    umap_model = umap.UMAP(
        n_neighbors=n_neighbors,
        n_components=n_components,
        min_dist=0.0,
        metric='cosine',
        random_state=42
    )
    umap_embeddings = umap_model.fit_transform(embeddings)

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric='euclidean',
        cluster_selection_method='eom'
    )
    labels = clusterer.fit_predict(umap_embeddings)
    return labels, umap_embeddings

def perform_clustering_with_HDBSCAN(min_cluster_size=15, min_samples=8, n_neighbors=15, n_components=15):
    """
    단일 HDBSCAN 클러스터링을 수행하고 결과를 DB에 저장합니다.
    """
    documents = list(collection.find({"embedding": {"$exists": True}}, {"_id": 1, "embedding": 1, "link": 1}))
    if len(documents) < min_cluster_size:
        return {"error": "Not enough documents with embeddings to cluster."}

    logger.info(f"총 {len(documents)}개 게시물에 대한 단일 HDBSCAN 클러스터링 시작.")

    embeddings = np.array([doc["embedding"] for doc in documents])
    ids = [doc["_id"] for doc in documents]
    links = [doc.get("link") for doc in documents]

    labels, umap_embeddings = _run_single_hdbscan_clustering(
        embeddings, min_cluster_size, min_samples, n_neighbors, n_components
    )

    bulk_ops = []
    for idx, doc_id in enumerate(ids):
        cluster_label = int(labels[idx])
        bulk_ops.append(UpdateOne({"_id": doc_id}, {"$set": {"cluster_label": cluster_label}}))
        if links[idx]:
            post_node = PostNode(link=links[idx], cluster=cluster_label)
            post_node.merge()

    if bulk_ops:
        collection.bulk_write(bulk_ops)

    mask = labels != -1
    silhouette_avg = -1
    if np.sum(mask) > 1 and len(set(labels[mask])) > 1:
        silhouette_avg = silhouette_score(umap_embeddings[mask], labels[mask])

    cluster_dist = {int(k): int(v) for k, v in Counter(labels).items()}
    logger.info("클러스터링 완료.")

    return {
        "message": "Clustering with UMAP+HDBSCAN completed.",
        "total_documents": len(documents),
        "clustered_documents": int(np.sum(mask)),
        "noise_documents": int(list(labels).count(-1)),
        "number_of_clusters": len(set(labels)) - (1 if -1 in labels else 0),
        "cluster_distribution": cluster_dist,
        "silhouette_score": float(silhouette_avg)
    }

def perform_ensemble_clustering(param_sets=None, final_min_cluster_size=10, final_min_samples=None):
    """앙상블 클러스터링을 수행하고 결과를 DB에 저장합니다."""
    documents = list(collection.find({"embedding": {"$exists": True}}, {"_id": 1, "embedding": 1, "link": 1}))
    if not documents:
        return {"error": "No documents with embeddings to cluster."}

    logger.info(f"총 {len(documents)}개 게시물에 대한 앙상블 클러스터링 시작.")
    embeddings = np.array([doc["embedding"] for doc in documents])
    ids = [doc["_id"] for doc in documents]
    links = [doc.get("link") for doc in documents]
    num_docs = len(documents)

    if param_sets is None:
        param_sets = [
            {'min_cluster_size': 5, 'min_samples': 1, 'n_neighbors': 5, 'n_components': 5},
            {'min_cluster_size': 10, 'min_samples': 2, 'n_neighbors': 10, 'n_components': 10},
            {'min_cluster_size': 15, 'min_samples': 5, 'n_neighbors': 15, 'n_components': 15},
            {'min_cluster_size': 20, 'min_samples': 10, 'n_neighbors': 20, 'n_components': 20},
        ]

    all_labels = []
    for params in param_sets:
        labels, _ = _run_single_hdbscan_clustering(embeddings, **params)
        all_labels.append(labels)

    logger.info("동시-연관 행렬 생성 중...")
    co_association_matrix = lil_matrix((num_docs, num_docs), dtype=np.int8)
    for labels in all_labels:
        unique_labels = np.unique(labels[labels != -1])
        for label in unique_labels:
            indices = np.where(labels == label)[0]
            for i in range(len(indices)):
                for j in range(i + 1, len(indices)):
                    idx1, idx2 = indices[i], indices[j]
                    co_association_matrix[idx1, idx2] += 1
                    co_association_matrix[idx2, idx1] += 1

    logger.info("최종 클러스터링 수행 중...")
    max_similarity = len(all_labels)
    distance_matrix = max_similarity - co_association_matrix.toarray()
    distance_matrix = distance_matrix.astype(np.float64)

    final_clusterer = hdbscan.HDBSCAN(
        metric='precomputed',
        min_cluster_size=final_min_cluster_size,
        min_samples=final_min_samples,
        cluster_selection_method='eom'
    )
    final_labels = final_clusterer.fit_predict(distance_matrix)

    bulk_ops = []
    for idx, doc_id in enumerate(ids):
        cluster_label = int(final_labels[idx])
        bulk_ops.append(UpdateOne({"_id": doc_id}, {"$set": {"ensemble_cluster_label": cluster_label}}))
        if links[idx]:
            post_node = PostNode(link=links[idx], cluster=cluster_label)
            post_node.merge()

    if bulk_ops:
        collection.bulk_write(bulk_ops)

    mask = final_labels != -1
    cluster_dist = {int(k): int(v) for k, v in Counter(final_labels).items()}
    logger.info("앙상블 클러스터링 완료.")

    return {
        "message": "Ensemble clustering completed.",
        "total_documents": num_docs,
        "clustered_documents": int(np.sum(mask)),
        "noise_documents": int(list(final_labels).count(-1)),
        "number_of_clusters": len(set(final_labels)) - (1 if -1 in final_labels else 0),
        "cluster_distribution": cluster_dist,
    }

def calculate_jaccard_distance_matrix(texts: list[str]) -> np.ndarray:
    """
    주어진 텍스트 목록에 대해 Jaccard 거리 행렬을 계산합니다.
    """
    logger.info(f"{len(texts)}개 문서에 대한 Jaccard 거리 행렬 계산 시작...")
    token_pattern = r'\b[a-zA-Z0-9가-힣]{2,}\b'
    corpus_sets = [set(re.findall(token_pattern, text.lower())) for text in texts]
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
    logger.info("Jaccard 거리 행렬 계산 완료.")
    return distance_matrix

def cluster_with_hybrid_metric(weights={'semantic': 0.7, 'structural': 0.3}, min_cluster_size=15, min_samples=8, n_neighbors=15, n_components=15):
    """
    의미적 거리(코사인)와 구조적 거리(Jaccard)를 결합한 하이브리드 거리 행렬을 사용해 클러스터링을 수행합니다.
    """
    documents = list(collection.find({"embedding": {"$exists": True}}, {"_id": 1, "embedding": 1, "link": 1, "title": 1}))
    if len(documents) < min_cluster_size:
        return {"error": "Not enough documents with embeddings to cluster."}

    logger.info(f"총 {len(documents)}개 게시물에 대한 하이브리드 클러스터링 시작.")
    ids = [doc["_id"] for doc in documents]
    links = [doc.get("link") for doc in documents]
    embeddings = np.array([doc["embedding"] for doc in documents])
    corpus = [preprocess_text(doc.get('title', '')) for doc in documents]

    semantic_dist_matrix = 1 - cosine_similarity(embeddings)
    structural_dist_matrix = calculate_jaccard_distance_matrix(corpus)

    scaler = MinMaxScaler()
    norm_semantic_dist = scaler.fit_transform(semantic_dist_matrix)
    norm_structural_dist = scaler.fit_transform(structural_dist_matrix)

    logger.info(f"거리 행렬 결합 (가중치: semantic={weights['semantic']}, structural={weights['structural']})")
    combined_dist_matrix = (weights['semantic'] * norm_semantic_dist + weights['structural'] * norm_structural_dist)

    logger.info("사전 계산된 거리 행렬로 UMAP 및 HDBSCAN 실행...")
    umap_model = umap.UMAP(n_neighbors=n_neighbors, n_components=n_components, min_dist=0.0, metric='precomputed', random_state=42)
    umap_embeddings = umap_model.fit_transform(combined_dist_matrix)

    clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, min_samples=min_samples, metric='euclidean', cluster_selection_method='eom')
    labels = clusterer.fit_predict(umap_embeddings)

    bulk_ops = []
    for idx, doc_id in enumerate(ids):
        cluster_label = int(labels[idx])
        bulk_ops.append(UpdateOne({"_id": doc_id}, {"$set": {"hybrid_cluster_label": cluster_label}}))
        if links[idx]:
            post_node = PostNode(link=links[idx], cluster=cluster_label)
            post_node.merge()

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

def save_silhouette_plot(distance_matrix, labels, filename_prefix="silhouette_plot"):
    """
    실루엣 플롯을 생성하고 지정된 경로에 이미지 파일로 저장합니다.
    """
    mask = labels != -1
    if np.sum(mask) < 2 or len(set(labels[mask])) < 2:
        logger.info("유효한 클러스터가 부족하여 실루엣 플롯을 생성할 수 없습니다.")
        return

    silhouette_vals = silhouette_samples(distance_matrix, labels)
    silhouette_avg = np.mean(silhouette_vals[mask])
    plt.figure(figsize=(10, 8))
    y_lower = 10
    cluster_labels = np.unique(labels[mask])

    for i, cluster in enumerate(cluster_labels):
        cluster_silhouette_vals = silhouette_vals[labels == cluster]
        cluster_silhouette_vals.sort()
        size_cluster_i = cluster_silhouette_vals.shape[0]
        y_upper = y_lower + size_cluster_i
        plt.fill_betweenx(np.arange(y_lower, y_upper), 0, cluster_silhouette_vals, label=f'Cluster {cluster}')
        y_lower = y_upper + 10

    plt.axvline(x=silhouette_avg, color="red", linestyle="--", label="Average")
    plt.title("Silhouette Plot for the Various Clusters")
    plt.xlabel("Silhouette coefficient values")
    plt.ylabel("Cluster label")
    plt.legend()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.png"
    plt.savefig(filename)
    plt.close()
    logger.info(f"실루엣 플롯이 '{filename}' 파일로 저장되었습니다.")

def calculate_custom_distance_matrix(documents, weights, umap_params):
    """
    각 벡터를 UMAP으로 차원 축소한 후, 거리 행렬을 계산하고 가중합합니다.
    """
    doc_embeddings = np.array([doc['doc_embedding'] for doc in documents], dtype=np.float64)
    price_embeddings = np.array([doc['price_embedding'] for doc in documents], dtype=np.float64)
    tfidf_vectors = np.array([doc['tfidf_vector'] for doc in documents], dtype=np.float64)

    if umap_params:
        logger.info(f"UMAP으로 차원 축소 수행 (params: {umap_params})")
        if 'doc' in umap_params:
            umap_model = umap.UMAP(**umap_params['doc'])
            doc_embeddings = umap_model.fit_transform(doc_embeddings)
            logger.info(f"문서 임베딩 -> {doc_embeddings.shape[1]} 차원으로 축소 완료.")
        if 'price' in umap_params:
            umap_model = umap.UMAP(**umap_params['price'])
            if np.any(price_embeddings):
                price_embeddings = umap_model.fit_transform(price_embeddings)
                logger.info(f"가격 임베딩 -> {price_embeddings.shape[1]} 차원으로 축소 완료.")
            else:
                logger.info("가격 임베딩이 모두 0이므로 UMAP 적용을 건너뜁니다.")
        if 'keyword' in umap_params:
            umap_model = umap.UMAP(**umap_params['keyword'])
            tfidf_vectors = umap_model.fit_transform(tfidf_vectors)
            logger.info(f"키워드 벡터 -> {tfidf_vectors.shape[1]} 차원으로 축소 완료.")

    doc_dist = 1 - cosine_similarity(doc_embeddings)
    price_dist = 1 - cosine_similarity(price_embeddings)
    tfidf_dist = 1 - cosine_similarity(tfidf_vectors)

    scaler = MinMaxScaler()
    doc_dist_scaled = scaler.fit_transform(doc_dist.flatten().reshape(-1, 1)).reshape(doc_dist.shape)
    price_dist_scaled = scaler.fit_transform(price_dist.flatten().reshape(-1, 1)).reshape(price_dist.shape)
    tfidf_dist_scaled = scaler.fit_transform(tfidf_dist.flatten().reshape(-1, 1)).reshape(tfidf_dist.shape)

    final_dist_matrix = (weights['doc'] * doc_dist_scaled + weights['price'] * price_dist_scaled + weights['keyword'] * tfidf_dist_scaled)
    np.fill_diagonal(final_dist_matrix, 0)
    logger.info("커스텀 거리 행렬 계산 완료.")
    return final_dist_matrix

def cluster_with_custom_metric(umap_params, weights, hdbscan_params):
    """
    커스텀 가중치와 파라미터를 사용하여 게시물을 클러스터링합니다.
    """
    query = {"doc_embedding": {"$exists": True}, "price_embedding": {"$exists": True}, "tfidf_vector": {"$exists": True}}
    documents = list(collection.find(query, {"_id": 1, "link": 1, "doc_embedding": 1, "price_embedding": 1, "tfidf_vector": 1}))

    if len(documents) < hdbscan_params.get('min_cluster_size', 5):
        return {"error": "Not enough documents with all required vectors to cluster."}

    logger.info(f"총 {len(documents)}개 게시물에 대한 커스텀 거리 기반 클러스터링 시작 (알고리즘: hdbscan).")

    ids = [doc["_id"] for doc in documents]
    links = [doc.get("link") for doc in documents]

    distance_matrix = calculate_custom_distance_matrix(documents, weights, umap_params)

    logger.info(f"HDBSCAN 클러스터링 수행 (params: {hdbscan_params})...")
    clusterer = hdbscan.HDBSCAN(metric='precomputed', **hdbscan_params)
    labels = clusterer.fit_predict(distance_matrix)

    save_silhouette_plot(distance_matrix, labels, filename_prefix="custom_hdbscan_silhouette")

    mask = labels != -1
    silhouette_avg = -1
    if np.sum(mask) > 1 and len(set(labels[mask])) > 1:
        silhouette_avg = silhouette_score(distance_matrix[mask], labels[mask])
        davies_bouldin_val = davies_bouldin_score(distance_matrix, labels)

    unique_labels = set(labels)
    num_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)

    bulk_ops = []
    for idx, doc_id in enumerate(ids):
        cluster_label = int(labels[idx])
        bulk_ops.append(UpdateOne({"_id": doc_id}, {"$set": {"cluster_label": cluster_label}}))
        if links[idx]:
            post_node = PostNode(link=links[idx], cluster=cluster_label)
            post_node.merge()

    if bulk_ops:
        collection.bulk_write(bulk_ops)

    cluster_dist = {int(k): int(v) for k, v in Counter(labels).items()}
    logger.info("클러스터링 완료.")

    return {
        "message": f"Clustering with custom distance metric hdbscan completed.",
        "total_documents": len(documents),
        "clustered_documents": int(np.sum(labels != -1)),
        "noise_documents": int(list(labels).count(-1)),
        "number_of_clusters": num_clusters,
        "cluster_distribution": cluster_dist,
        "silhouette_score": float(silhouette_avg),
        "DBI": float(davies_bouldin_val)
    }
