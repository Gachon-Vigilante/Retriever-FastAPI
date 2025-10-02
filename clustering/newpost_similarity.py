import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from bs4 import BeautifulSoup

from server.db import Database
from server.cypher import run_cypher, Neo4j

collection = Database.Collection.POST
similarity_collection = Database.Collection.POST_SIMILARITY

try:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')
except Exception as e:
    print(f"Error loading SentenceTransformer model: {e}")
    raise


def preprocess_text(text: str) -> str:
    soup = BeautifulSoup(text, 'html.parser')
    return soup.get_text(separator=' ').strip()


def get_bert_embedding(text: str) -> np.ndarray:
    return model.encode(text).astype(np.float64)


def fetch_documents(filter=None, with_embedding=False):
    proj = {
        "_id": 1,
        "link": 1,
        "source": 1,
        "title": 1,
        "siteName": 1,
        "content": 1,
        "promoSiteLink": 1,  # ← 추가
        "createdAt": 1,
        "updatedAt": 1,
        "deleted": 1
    }
    if with_embedding:
        proj["embedding"] = 1

    cursor = collection.find(filter or {}, proj)

    docs = []
    for doc in cursor:
        content = doc.get("content", "")
        if not content.strip():
            continue
        docs.append({
            "postId": str(doc["_id"]),
            "link": doc.get("link", ""),
            "source": doc.get("source", ""),
            "title": doc.get("title", ""),
            "siteName": doc.get("siteName", ""),
            "content": content,
            "promoSiteLink": doc.get("promoSiteLink", []),  # ← 추가
            "text": preprocess_text(content),
            "createdAt": doc.get("createdAt"),
            "updatedAt": doc.get("updatedAt", doc.get("createdAt")),
            "deleted": doc.get("deleted", False),
            "embedding": np.array(doc["embedding"]) if with_embedding and "embedding" in doc else None
        })
    return docs



def insert_post_similarity(link1: str, link2: str, score: float):
    query = """
    MATCH (a:Post {link: $link1}), (b:Post {link: $link2})
    MERGE (a)-[r:SIMILAR]->(b)
    SET r.score = $score
    """
    run_cypher(query, {"link1": link1, "link2": link2, "score": score})


def merge_post_similarity(doc1, doc2, score):
    link1, link2 = doc1["link"], doc2["link"]
    if score < 0.7 or link1 >= link2:
        return

    for doc in (doc1, doc2):
        run_cypher(Neo4j.QueryTemplate.Node.Post.MERGE, {
            "link": doc["link"],
            "siteName": doc["siteName"],
            "content": doc["content"],
            "createdAt": doc["createdAt"],
            "updatedAt": doc["updatedAt"],
            "deleted": doc["deleted"]
        })
    insert_post_similarity(link1, link2, score)


def calculate_similarity_between_sets(new_docs, existing_docs):
    """
    new_docs, existing_docs : 각각 embedding 필드가 반드시 numpy 배열로 포함되어야 함.
    """

    new_embeddings = np.array([doc["embedding"] for doc in new_docs])
    existing_embeddings = np.array([doc["embedding"] for doc in existing_docs])

    # 신규 문서끼리 유사도
    sim_new_new = cosine_similarity(new_embeddings)

    # 신규 문서와 기존 문서 간 유사도
    sim_new_exist = cosine_similarity(new_embeddings, existing_embeddings)

    bulk_data = []

    # 신규 문서끼리 유사도 저장
    for i, doc in enumerate(new_docs):
        similarities = []
        for j, score in enumerate(sim_new_new[i]):
            if i == j:
                continue
            other_doc = new_docs[j]
            similarities.append({
                "similarPost": other_doc["postId"],
                "similarity": float(score)
            })
            merge_post_similarity(doc, other_doc, score)

        # 기존 문서와 신규 문서 간 유사도 저장
        for j, score in enumerate(sim_new_exist[i]):
            other_doc = existing_docs[j]
            similarities.append({
                "similarPost": other_doc["postId"],
                "similarity": float(score)
            })
            merge_post_similarity(doc, other_doc, score)

        bulk_data.append({
            "postId": doc["postId"],
            "similarPosts": similarities,
            "updatedAt": doc["updatedAt"]
        })

    if bulk_data:
        similarity_collection.insert_many(bulk_data)


from collections import Counter

def new_post_insert():
    new_docs = fetch_documents({"cluster_label": {"$exists": False}}, with_embedding=False)
    if not new_docs:
        return {"message": "No new documents."}

    # 1. promoSiteLink 기반 가중치 사전 생성
    promo_links = [
        doc.get("promoSiteLink", [])[0]
        for doc in new_docs
        if isinstance(doc.get("promoSiteLink", []), list) and doc["promoSiteLink"]
    ]
    link_counts = Counter(promo_links)
    max_count = max(link_counts.values()) if link_counts else 1
    link_weights = {link: count / max_count for link, count in link_counts.items()}

    # 2. promoSiteLink 임베딩 캐시
    promo_embeddings = {link: get_bert_embedding(link) for link in link_weights}

    # 3. 임베딩 계산: 본문 + (weighted) promo 링크
    for doc in new_docs:
        text_emb = get_bert_embedding(doc["text"])
        promo_link = doc.get("promoSiteLink", [])[0] if isinstance(doc.get("promoSiteLink", []), list) and doc["promoSiteLink"] else None

        promo_emb = promo_embeddings.get(promo_link)
        weight = 0.3

        if promo_emb is not None:
            doc["embedding"] = (1 - weight) * text_emb + weight * promo_emb
        else:
            doc["embedding"] = text_emb

    # 기존 문서 로딩
    existing_docs = fetch_documents({"cluster_label": {"$exists": True}}, with_embedding=True)
    if not existing_docs:
        calculate_similarity_between_sets(new_docs, [])
    else:
        calculate_similarity_between_sets(new_docs, existing_docs)

    return {"message": "New post similarity calculated and stored."}

