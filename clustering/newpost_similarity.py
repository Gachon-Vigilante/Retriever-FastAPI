import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from bs4 import BeautifulSoup
from pymongo import UpdateOne
from datetime import datetime

from core.mongo.connections import MongoCollections
from core.neo4j.ogm import PostNode, SimilarTo
from core.mongo.post import PostFields # 새로운 필드명 Enum import

mongo = MongoCollections()
collection = mongo.posts

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
    projection = {f: 1 for f in [PostFields.link, PostFields.title, PostFields.discovered_at, "promoSiteLink"]}
    if with_embedding:
        projection["embedding"] = 1

    cursor = collection.find(filter or {}, projection)

    docs = []
    for doc in cursor:
        # OGM과 MongoDB 업데이트를 위해 원본 문서 구조를 최대한 유지하며 필요한 키 추가
        doc['text_preprocessed'] = preprocess_text(doc.get(PostFields.title, ''))
        doc['post_id'] = str(doc['_id'])
        if with_embedding and "embedding" in doc:
            doc['embedding'] = np.array(doc["embedding"])
        docs.append(doc)
    return docs

def merge_post_similarity(doc1, doc2, score):
    if score < 0.7:
        return

    post_obj_1 = PostNode.from_mongo(doc1)
    post_obj_2 = PostNode.from_mongo(doc2)
    SimilarTo.merge(post_obj_1, post_obj_2, score=float(score))

def calculate_similarity_for_new_docs(new_docs, existing_docs):
    """
    새로운 문서들과 기존 문서들 간의 유사도를 계산하고, 
    각 새로운 문서에 대한 유사도 목록을 딕셔너리 형태로 반환합니다.
    """
    if not new_docs:
        return {}

    new_embeddings = np.array([doc["embedding"] for doc in new_docs])
    all_similarities = {doc['_id']: [] for doc in new_docs}

    # 1. 신규 문서들끼리의 유사도 계산
    sim_new_new = cosine_similarity(new_embeddings)
    for i, doc in enumerate(new_docs):
        for j, score in enumerate(sim_new_new[i]):
            if i == j: continue
            other_doc = new_docs[j]
            all_similarities[doc['_id']].append({"post_id": other_doc['post_id'], "similarity": float(score)})
            merge_post_similarity(doc, other_doc, score)

    # 2. 신규 문서와 기존 문서 간의 유사도 계산
    if existing_docs:
        existing_embeddings = np.array([doc["embedding"] for doc in existing_docs])
        sim_new_exist = cosine_similarity(new_embeddings, existing_embeddings)
        for i, doc in enumerate(new_docs):
            for j, score in enumerate(sim_new_exist[i]):
                other_doc = existing_docs[j]
                all_similarities[doc['_id']].append({"post_id": other_doc['post_id'], "similarity": float(score)})
                merge_post_similarity(doc, other_doc, score)

    return all_similarities

from collections import Counter

def new_post_insert():
    new_docs = fetch_documents({"cluster": {"$exists": False}}, with_embedding=False)
    if not new_docs:
        return {"message": "No new documents."}

    # --- 임베딩 생성 로직 ---
    promo_links = [doc.get("promoSiteLink", [])[0] for doc in new_docs if isinstance(doc.get("promoSiteLink", []), list) and doc["promoSiteLink"]]
    link_counts = Counter(promo_links)
    max_count = max(link_counts.values()) if link_counts else 1
    link_weights = {link: count / max_count for link, count in link_counts.items()}
    promo_embeddings = {link: get_bert_embedding(link) for link in link_weights}
    for doc in new_docs:
        text_emb = get_bert_embedding(doc["text_preprocessed"])
        promo_link = doc.get("promoSiteLink", [])[0] if isinstance(doc.get("promoSiteLink", []), list) and doc["promoSiteLink"] else None
        promo_emb = promo_embeddings.get(promo_link)
        weight = 0.3
        doc["embedding"] = ((1 - weight) * text_emb + weight * promo_emb) if promo_emb is not None else text_emb

    # --- 유사도 계산 및 DB 업데이트 ---
    existing_docs = fetch_documents({"cluster": {"$exists": True}}, with_embedding=True)
    
    similarities_map = calculate_similarity_for_new_docs(new_docs, existing_docs)

    bulk_ops = []
    for doc in new_docs:
        doc_id = doc['_id']
        if doc_id in similarities_map:
            bulk_ops.append(
                UpdateOne(
                    {"_id": doc_id},
                    {"$set": {PostFields.similarities: similarities_map[doc_id], PostFields.updated_at: datetime.now()}}
                )
            )

    if bulk_ops:
        collection.bulk_write(bulk_ops)

    return {"message": f"New post similarity for {len(new_docs)} documents calculated and stored."}
