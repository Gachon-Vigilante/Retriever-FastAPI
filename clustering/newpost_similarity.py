import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from bs4 import BeautifulSoup

from core.mongo.connections import MongoCollections
from core.neo4j.ogm import PostNode, SimilarTo

mongo = MongoCollections()
collection = mongo.posts
similarity_collection = mongo.post_similarity

try:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('upskyy/bge-m3-korean')
except Exception as e:
    print(f"Error loading SentenceTransformer model: {e}")
    raise


def preprocess_text(text: str) -> str:
    soup = BeautifulSoup(text, 'html.parser')
    return soup.get_text(separator=' ').strip()


def get_bert_embedding(text: str) -> np.ndarray:
    return model.encode(text, convert_to_numpy=True).astype(np.float64)


def fetch_documents(filter=None, with_embedding=False):
    proj = {
        "_id": 1, "link": 1, "source": 1, "title": 1, "siteName": 1,
        "title": 1, "promoSiteLink": 1, "createdAt": 1, "updatedAt": 1,
        "deleted": 1, "discovered_at": 1
    }
    if with_embedding:
        proj["embedding"] = 1

    cursor = collection.find(filter or {}, proj)

    docs = []
    for doc in cursor:
        title = doc.get("title", "")
        if not title.strip():
            continue
        docs.append({
            "_id": doc["_id"],
            "postId": str(doc["_id"]),
            "link": doc.get("link", ""),
            "source": doc.get("source", ""),
            "title": doc.get("title", ""),
            "siteName": doc.get("siteName", ""),
            "promoSiteLink": doc.get("promoSiteLink", []),
            "text": preprocess_text(title),
            "createdAt": doc.get("createdAt"),
            "updatedAt": doc.get("updatedAt", doc.get("createdAt")),
            "deleted": doc.get("deleted", False),
            "embedding": np.array(doc["embedding"]) if with_embedding and "embedding" in doc else None,
            "discovered_at": doc.get("discovered_at")
        })
    return docs

def merge_post_similarity(doc1, doc2, score):
    if score < 0.7:
        return

    post_obj_1 = PostNode.from_mongo(doc1)
    post_obj_2 = PostNode.from_mongo(doc2)
    SimilarTo.merge(post_obj_1, post_obj_2, score=float(score))

def calculate_similarity_between_sets(new_docs, existing_docs):
    """
    new_docs, existing_docs : 각각 embedding 필드가 반드시 numpy 배열로 포함되어야 함.
    """
    if not new_docs: return

    new_embeddings = np.array([doc["embedding"] for doc in new_docs])
    
    # 신규 문서끼리 유사도
    sim_new_new = cosine_similarity(new_embeddings)
    for i, doc in enumerate(new_docs):
        similarities = []
        for j, score in enumerate(sim_new_new[i]):
            if i == j: continue
            other_doc = new_docs[j]
            similarities.append({"similarPost": other_doc["postId"], "similarity": float(score)})
            merge_post_similarity(doc, other_doc, score)

        # 기존 문서와 신규 문서 간 유사도 저장
        if existing_docs:
            existing_embeddings = np.array([doc["embedding"] for doc in existing_docs])
            sim_new_exist = cosine_similarity(new_embeddings[i:i+1], existing_embeddings)[0]
            for j, score in enumerate(sim_new_exist):
                other_doc = existing_docs[j]
                similarities.append({"similarPost": other_doc["postId"], "similarity": float(score)})
                merge_post_similarity(doc, other_doc, score)
        
        # MongoDB에 유사도 정보 업데이트 (이 부분은 bulk_write 밖에서 개별 처리)
        # 이 함수는 새로운 문서에 대한 것이므로, upsert=True를 사용하거나, new_post_insert에서 별도 처리 필요
        # 지금은 일단 MongoDB 업데이트 로직은 제외하고 Neo4j 연동에 집중

from collections import Counter

def new_post_insert():
    new_docs = fetch_documents({"cluster_label": {"$exists": False}}, with_embedding=False)
    if not new_docs:
        return {"message": "No new documents."}

    promo_links = [doc.get("promoSiteLink", [])[0] for doc in new_docs if isinstance(doc.get("promoSiteLink", []), list) and doc["promoSiteLink"]]
    link_counts = Counter(promo_links)
    max_count = max(link_counts.values()) if link_counts else 1
    link_weights = {link: count / max_count for link, count in link_counts.items()}

    promo_embeddings = {link: get_bert_embedding(link) for link in link_weights}

    for doc in new_docs:
        text_emb = get_bert_embedding(doc["text"])
        promo_link = doc.get("promoSiteLink", [])[0] if isinstance(doc.get("promoSiteLink", []), list) and doc["promoSiteLink"] else None
        promo_emb = promo_embeddings.get(promo_link)
        weight = 0.3
        doc["embedding"] = ((1 - weight) * text_emb + weight * promo_emb) if promo_emb is not None else text_emb

    existing_docs = fetch_documents({"cluster_label": {"$exists": True}}, with_embedding=True)
    calculate_similarity_between_sets(new_docs, existing_docs)

    return {"message": "New post similarity calculated and stored."}
