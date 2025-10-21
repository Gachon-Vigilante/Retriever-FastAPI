# 필요한 라이브러리 추가
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from bs4 import BeautifulSoup
import numpy as np
from collections import Counter
from pymongo import UpdateOne
from datetime import datetime

from core.mongo.connections import MongoCollections
from utils import Logger
from core.neo4j.ogm import PostNode, SimilarTo
from core.mongo.post import PostFields # 새로운 필드명 Enum import

# 임베딩 모델
try:
    model = SentenceTransformer('upskyy/bge-m3-korean')
except Exception as e:
    print(f"Error loading SentenceTransformer model: {e}")
    raise

mongo = MongoCollections()
collection = mongo.posts
channel_collection = mongo.channel_info
logger = Logger(__name__)

def preprocess_text(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, 'html.parser')
    # get_text()의 결과가 None일 수 있는 경우를 대비하여 or '' 추가
    cleaned_text = soup.get_text(separator=' ') or ''
    return cleaned_text.strip()

def get_bert_embedding(text: str) -> np.ndarray:
    if not text or not text.strip():
        return np.zeros(model.get_sentence_embedding_dimension(), dtype=np.float64)
    return model.encode(text, convert_to_numpy=True).astype(np.float64)

def fetch_channel_catalog(channel_id: int):
    if not channel_id: return None
    return channel_collection.find_one({"_id": channel_id})

def embeddings():
    """모든 게시물에 대해 하이브리드 임베딩을 생성하고 저장합니다."""
    documents = list(collection.find({}, {PostFields.title: 1, "channelId": 1}))
    if not documents:
        return {"message": "No documents to process."}

    logger.info(f"총 {len(documents)}개 게시물에 대한 하이브리드 임베딩 시작.")

    corpus = [preprocess_text(doc.get(PostFields.title) or '') for doc in documents]
    
    vectorizer = TfidfVectorizer(min_df=2, max_df=0.7, token_pattern=r'\b[a-zA-Z0-9가-힣]{2,}\b')
    doc_keywords = {}
    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
        feature_names = np.array(vectorizer.get_feature_names_out())
        for i, doc in enumerate(documents):
            tfidf_vector = tfidf_matrix[i]
            sorted_indices = tfidf_vector.toarray().argsort()[0][::-1]
            top_keywords_indices = [idx for idx in sorted_indices if tfidf_vector[0, idx] > 0][:5]
            top_n_keywords = feature_names[top_keywords_indices]
            doc_keywords[doc['_id']] = ' '.join(top_n_keywords)
    except ValueError:
        logger.warning("TF-IDF를 계산하기에 문서가 부족하여 키워드 임베딩을 건너뜁니다.")

    bulk_ops = []
    for doc in documents:
        def normalize(v): 
            norm = np.linalg.norm(v)
            return v / norm if norm != 0 else v

        doc_text = doc.get(PostFields.title, '')
        doc_emb = normalize(get_bert_embedding(doc_text))

        keywords_text = doc_keywords.get(doc['_id'], '')
        keyword_emb = normalize(get_bert_embedding(keywords_text)) if keywords_text else np.zeros_like(doc_emb)
        
        catalog = fetch_channel_catalog(doc.get("channelId"))
        price_emb = np.zeros_like(doc_emb)
        if catalog and "catalog" in catalog and isinstance(catalog.get("catalog"), dict) and "description" in catalog["catalog"]:
            price_text = catalog["catalog"]["description"].replace("\n", " ").replace("-", "")
            if price_text: price_emb = normalize(get_bert_embedding(price_text))

        active_vectors = []
        if np.any(doc_emb): active_vectors.append((doc_emb, 0.5))
        if np.any(keyword_emb): active_vectors.append((keyword_emb, 0.3))
        if np.any(price_emb): active_vectors.append((price_emb, 0.2))

        if not active_vectors:
            combined_emb = np.zeros(model.get_sentence_embedding_dimension())
        else:
            total_weight = sum(w for _, w in active_vectors)
            combined_emb = sum((v * (w / total_weight)) for v, w in active_vectors)
            combined_emb = normalize(combined_emb)

        bulk_ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"embedding": combined_emb.tolist()}}))

    if bulk_ops:
        collection.bulk_write(bulk_ops)
        logger.info(f"하이브리드 임베딩 완료 및 저장: {len(bulk_ops)}개 문서.")
    
    return {"message": f"Hybrid embeddings generated for {len(bulk_ops)} documents."}

def similarity(threshold=0.7):
    """게시물 간 유사도를 계산하여 posts 컬렉션의 similarities 필드에 저장합니다."""
    projection = {f: 1 for f in [PostFields.link, PostFields.title, PostFields.discovered_at]}
    projection["embedding"] = 1
    documents = list(collection.find({"embedding": {"$exists": True}}, projection))

    if len(documents) < 2:
        return {"message": "Not enough documents with embeddings to calculate similarity."}

    logger.info(f"게시글 {len(documents)}개에 대한 텍스트 유사도 계산 시작.")

    embeddings = np.array([doc["embedding"] for doc in documents])
    similarity_matrix = cosine_similarity(embeddings)

    bulk_ops = []
    for i, doc in enumerate(documents):
        similarities = []
        for j, score in enumerate(similarity_matrix[i]):
            if i == j: continue
            other_doc = documents[j]
            similarities.append({
                "post_id": str(other_doc["_id"]),
                "similarity": float(score)
            })

            if score >= threshold:
                post_obj_1 = PostNode.from_mongo(doc)
                post_obj_2 = PostNode.from_mongo(other_doc)
                SimilarTo.merge(post_obj_1, post_obj_2, score=float(score))

        bulk_ops.append(UpdateOne(
            {"_id": doc["_id"]},
            {"$set": {PostFields.similarities: similarities, PostFields.updated_at: datetime.now()}}
        ))

    if bulk_ops:
        collection.bulk_write(bulk_ops)

    return {"message": f"Similarity calculations completed and stored in posts collection for {len(documents)} documents."}

def generate_separate_embeddings():
    # 이 함수는 현재 하이브리드 임베딩 전략과 맞지 않으므로, 내용을 비워두거나 삭제 고려
    pass
