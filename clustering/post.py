import umap.umap_ as umap
import numpy as np
import hdbscan
from sklearn.metrics.pairwise import cosine_similarity,euclidean_distances
from collections import Counter
from server.db import Database
from server.cypher import run_cypher
from server.logger import logger
from pymongo import UpdateOne
from sklearn.preprocessing import MinMaxScaler  
from sklearn.metrics import silhouette_score, davies_bouldin_score , silhouette_samples
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import datetime # 파일명 구분을 위해 추가

collection = Database.Collection.POST




def perform_clustering_with_HDBSCAN(min_cluster_size=15, min_samples=8, n_neighbors=15, n_components=15):
    """
    단일 'embedding' 필드를 사용하여 UMAP + HDBSCAN 클러스터링을 수행합니다.
    """
    # 'embedding' 필드가 존재하는 모든 문서를 가져옵니다.
    documents = list(collection.find({"embedding": {"$exists": True}}, {"_id": 1, "embedding": 1, "link": 1}))
    if len(documents) < min_cluster_size:
        return {"error": "Not enough documents with embeddings to cluster."}

    logger.info(f"총 {len(documents)}개 게시물에 대한 UMAP+HDBSCAN 클러스터링 시작.")

    embeddings = np.array([doc["embedding"] for doc in documents])
    ids = [doc["_id"] for doc in documents]
    links = [doc.get("link") for doc in documents]

    # UMAP으로 차원 축소
    logger.info(f"UMAP으로 {n_components}차원으로 축소 중...")
    umap_model = umap.UMAP(
        n_neighbors=n_neighbors, 
        n_components=n_components,
        min_dist=0.0, 
        metric='cosine', 
        random_state=42
    )
    umap_embeddings = umap_model.fit_transform(embeddings)

    # HDBSCAN 클러스터링
    logger.info("HDBSCAN 클러스터링 수행 중...")
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size, 
        min_samples=min_samples,
        metric='euclidean', 
        cluster_selection_method='eom'
    )
    labels = clusterer.fit_predict(umap_embeddings)

    # 클러스터링 성능 평가 (실루엣 계수)
    mask = labels != -1
    silhouette_avg = -1
    if np.sum(mask) > 1 and len(set(labels[mask])) > 1:
        silhouette_avg = silhouette_score(umap_embeddings[mask], labels[mask])

    # 결과 업데이트
    bulk_ops = []
    for idx, doc_id in enumerate(ids):
        cluster_label = int(labels[idx])
        bulk_ops.append(UpdateOne({"_id": doc_id}, {"$set": {"cluster_label": cluster_label}}))
        run_cypher(
            "MERGE (p:Post {link: $link}) ON MATCH SET p.cluster = $cluster",
            parameters={"link": links[idx], "cluster": cluster_label}
        )
    
    if bulk_ops:
        collection.bulk_write(bulk_ops)

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



def save_silhouette_plot(distance_matrix, labels, filename_prefix="silhouette_plot"):
    """
    실루엣 플롯을 생성하고 지정된 경로에 이미지 파일로 저장합니다.
    """
    # 노이즈(-1)를 제외한 클러스터 레이블과 데이터만 사용
    mask = labels != -1
    if np.sum(mask) < 2 or len(set(labels[mask])) < 2:
        logger.info("유효한 클러스터가 부족하여 실루엣 플롯을 생성할 수 없습니다.")
        return

    # 실루엣 점수 계산
    silhouette_vals = silhouette_samples(distance_matrix, labels)
    silhouette_avg = np.mean(silhouette_vals[mask])
    
    plt.figure(figsize=(10, 8))
    
    y_lower = 10
    cluster_labels = np.unique(labels[mask])

    # 각 클러스터의 실루엣 플롯을 그립니다.
    for i, cluster in enumerate(cluster_labels):
        cluster_silhouette_vals = silhouette_vals[labels == cluster]
        cluster_silhouette_vals.sort()
        
        size_cluster_i = cluster_silhouette_vals.shape[0]
        y_upper = y_lower + size_cluster_i
        
        plt.fill_betweenx(np.arange(y_lower, y_upper), 0, cluster_silhouette_vals,
                          label=f'Cluster {cluster}')
        y_lower = y_upper + 10

    plt.axvline(x=silhouette_avg, color="red", linestyle="--", label="Average")
    plt.title("Silhouette Plot for the Various Clusters")
    plt.xlabel("Silhouette coefficient values")
    plt.ylabel("Cluster label")
    plt.legend()

    # 현재 시간을 이용해 고유한 파일명 생성
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.png"
    
    plt.savefig(filename)
    plt.close() # 메모리 누수 방지를 위해 plot을 닫아줍니다.
    logger.info(f"실루엣 플롯이 '{filename}' 파일로 저장되었습니다.")

def calculate_custom_distance_matrix(documents, weights, umap_params):
    """
    각 벡터를 UMAP으로 차원 축소한 후, 거리 행렬을 계산하고 가중합합니다.
    """

    doc_embeddings = np.array([doc['doc_embedding'] for doc in documents], dtype=np.float64)
    price_embeddings = np.array([doc['price_embedding'] for doc in documents], dtype=np.float64)
    tfidf_vectors = np.array([doc['tfidf_vector'] for doc in documents], dtype=np.float64)

    # [수정] 함수 상단의 고정된 umap_model 정의 삭제

    if umap_params:
        logger.info(f"UMAP으로 차원 축소 수행 (params: {umap_params})")
        
        if 'doc' in umap_params:
            umap_model = umap.UMAP(**umap_params['doc'])
            doc_embeddings = umap_model.fit_transform(doc_embeddings)
            logger.info(f"문서 임베딩 -> {doc_embeddings.shape[1]} 차원으로 축소 완료.")

        if 'price' in umap_params:
            umap_model = umap.UMAP(**umap_params['price'])
            # 가격 임베딩에 0이 아닌 값이 하나라도 있을 때만 UMAP 실행
            if np.any(price_embeddings):
                price_embeddings = umap_model.fit_transform(price_embeddings)
                logger.info(f"가격 임베딩 -> {price_embeddings.shape[1]} 차원으로 축소 완료.")
            else:
                # 모든 값이 0이면 UMAP은 오류를 일으키므로 건너뛰고 0 벡터 유지
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
    
    final_dist_matrix = (weights['doc'] * doc_dist_scaled + 
                         weights['price'] * price_dist_scaled + 
                         weights['keyword'] * tfidf_dist_scaled)
    
    np.fill_diagonal(final_dist_matrix, 0)
    
    logger.info("커스텀 거리 행렬 계산 완료.")
    return final_dist_matrix


def cluster_with_custom_metric(
    umap_params,
    weights,
    hdbscan_params
):
    
    query = {
        "doc_embedding": {"$exists": True},
        "price_embedding": {"$exists": True},
        "tfidf_vector": {"$exists": True}
    }
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

    # 결과 업데이트 및 저장
    bulk_ops = []
    for idx, doc_id in enumerate(ids):
        cluster_label = int(labels[idx])
        bulk_ops.append(UpdateOne({"_id": doc_id}, {"$set": {"cluster_label": cluster_label}}))
        run_cypher(
            "MERGE (p:Post {link: $link}) ON MATCH SET p.cluster = $cluster",
            parameters={"link": links[idx], "cluster": cluster_label}
        )
    
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
        "DBI": float(davies_bouldin_val) #
    }