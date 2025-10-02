# 필요한 라이브러리 추가
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer # TF-IDF Vectorizer 추가
from bs4 import BeautifulSoup
import numpy as np
from collections import Counter
from pymongo import UpdateOne
from server.db import Database
from server.cypher import run_cypher, Neo4j
from server.logger import logger
from .newpost_similarity import insert_post_similarity

# MongoDB 컬렉션
collection = Database.Collection.POST
channel_collection = Database.Collection.Channel.INFO

# Ko-SBERT 모델 로드
try:
    model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')
except Exception as e:
    print(f"Error loading SentenceTransformer model: {e}")
    raise

def preprocess_text(text):
    if not text: return ""
    soup = BeautifulSoup(text, 'html.parser')
    return soup.get_text(separator=' ').strip()

def get_bert_embedding(text: str) -> np.ndarray:
    if not text or not text.strip():
        return np.zeros(model.get_sentence_embedding_dimension(), dtype=np.float64)
    return model.encode(text, convert_to_numpy=True).astype(np.float64)

def fetch_channel_catalog(channel_id: int):
    if not channel_id: return None
    return channel_collection.find_one({"_id": channel_id})

# 이 함수가 /post_preprocess 에서 호출됩니다.
def embeddings():
    # 모든 문서를 대상으로 임베딩을 새로 생성합니다.
    documents = list(collection.find({}))
    if not documents:
        return {"message": "No documents to process."}

    logger.info(f"총 {len(documents)}개 게시물에 대한 하이브리드 임베딩 시작.")

    corpus = [preprocess_text(doc.get('content', '')) for doc in documents]
    vectorizer = TfidfVectorizer(min_df=2, max_df=0.7, token_pattern=r'\b[a-zA-Z0-9가-힣]{2,}\b')
    tfidf_matrix = vectorizer.fit_transform(corpus)
    feature_names = np.array(vectorizer.get_feature_names_out())
    
    doc_keywords = {}
    for i, doc in enumerate(documents):
        tfidf_vector = tfidf_matrix[i]
        sorted_indices = tfidf_vector.toarray().argsort()[0][::-1]
        top_keywords_indices = [idx for idx in sorted_indices if tfidf_vector[0, idx] > 0][:5]
        top_n_keywords = feature_names[top_keywords_indices]
        doc_keywords[doc['_id']] = ' '.join(top_n_keywords)

    bulk_ops = []
    for doc in documents:
        # 1. 문맥 임베딩
        doc_text = preprocess_text(doc.get('content', ''))
        doc_emb = get_bert_embedding(doc_text)

        # 2. 키워드 의미 임베딩
        keywords_text = doc_keywords.get(doc['_id'], '')
        keyword_emb = get_bert_embedding(keywords_text)
        
        # 3. 가격 정보 임베딩
        catalog = fetch_channel_catalog(doc.get("channelId"))
        price_emb = np.zeros_like(doc_emb) # 기본값은 0 벡터
        if catalog and "catalog" in catalog and isinstance(catalog.get("catalog"), dict) and "description" in catalog["catalog"]:
            price_text = catalog["catalog"]["description"].replace("\n", " ").replace("-", "")
            price_emb = get_bert_embedding(price_text)

        # 4. 가중치를 적용하여 하나의 최종 임베딩으로 결합
        w_doc = 0.5
        w_keyword = 0.3
        w_price = 0.2
        
        combined_emb = (w_doc * doc_emb) + (w_keyword * keyword_emb) + (w_price * price_emb)

        # 생성된 최종 임베딩을 'embedding' 필드에 저장하고, 다른 벡터 필드는 삭제
        bulk_ops.append(UpdateOne(
            {"_id": doc["_id"]},
            {
                "$set": {"embedding": combined_emb.tolist()},
                "$unset": {
                    "doc_embedding": "", 
                    "keyword_embedding": "", 
                    "price_embedding": "",
                    "keyword_vector": ""
                }
            }
        ))

    if bulk_ops:
        collection.bulk_write(bulk_ops)
        logger.info(f"하이브리드 임베딩 완료 및 저장: {len(bulk_ops)}개 문서.")
    
    return {"message": f"Hybrid embeddings (TF-IDF + SBERT) generated for {len(bulk_ops)} documents."}


# __init__.py 에서 호출할 함수
def similarity(threshold=0.7):
    documents = list(collection.find({"embedding": {"$exists": True}}, {
        "_id": 1, "link": 1, "siteName": 1, "content": 1,
        "createdAt": 1, "updatedAt": 1, "deleted": 1, "embedding": 1
    }))

    if len(documents) < 2:
        return {"message": "Not enough documents with embeddings to calculate similarity."}

    logger.info(f"게시글 {len(documents)}개에 대한 텍스트 유사도 계산 시작.")

    embeddings = np.array([doc["embedding"] for doc in documents])
    similarity_matrix = cosine_similarity(embeddings)

    bulk_ops = []
    for i, doc in enumerate(documents):
        similarities = []
        for j, score in enumerate(similarity_matrix[i]):
            if i == j:
                continue

            other_doc = documents[j]
            similarities.append({
                "similarPost": str(other_doc["_id"]),
                "similarity": float(score)
            })

            if score >= threshold and doc["link"] < other_doc["link"]:
                run_cypher(Neo4j.QueryTemplate.Node.Post.MERGE, {
                    "link": doc["link"],
                    "siteName": doc.get("source") or doc.get("siteName"),
                    "content": doc.get("content"),
                    "createdAt": doc.get("createdAt"),
                    "updatedAt": doc.get("updatedAt"),
                    "deleted": doc.get("deleted")
                })
                run_cypher(Neo4j.QueryTemplate.Node.Post.MERGE, {
                    "link": other_doc["link"],
                    "siteName": other_doc.get("source") or other_doc.get("siteName"),
                    "content": other_doc.get("content"),
                    "createdAt": other_doc.get("createdAt"),
                    "updatedAt": other_doc.get("updatedAt"),
                    "deleted": other_doc.get("deleted")
                })
                insert_post_similarity(doc["link"], other_doc["link"], score)

        bulk_ops.append(UpdateOne(
            {"_id": doc["_id"]},
            {"$set": {"similarPosts": similarities, "updatedAt": doc["updatedAt"]}}
        ))

    if bulk_ops:
        collection.bulk_write(bulk_ops)

    return {"message": "Similarity calculations completed and stored in MongoDB & Neo4j."}


# -------------------- 3개의 임베딩 벡터 -----------
def generate_separate_embeddings():
    """
    [최종 수정] promoChannelId를 사용하여 가격 정보를 올바르게 임베딩합니다.
    """
    documents = list(collection.find({}))
    if not documents:
        return {"message": "No documents to process."}

    logger.info(f"총 {len(documents)}개 게시물에 대한 개별 벡터/임베딩 생성 시작.")

    corpus = [preprocess_text(doc.get('content', '')) for doc in documents]
    vectorizer = TfidfVectorizer(min_df=2, max_df=0.7, token_pattern=r'\b[a-zA-Z0-9가-힣]{2,}\b')
    tfidf_matrix = vectorizer.fit_transform(corpus)

    vocabulary = vectorizer.get_feature_names_out()
    logger.info(f"TF-IDF Vectorizer가 학습한 전체 단어 수: {len(vocabulary)}")
    logger.info(f"학습된 단어 샘플 (앞 100개): {vocabulary[:100]}")
    
    bulk_ops = []
    for i, doc in enumerate(documents):

        price_emb = np.zeros(model.get_sentence_embedding_dimension(), dtype=np.float64)
        

        channel_id = doc.get("promoChannelId")

        if channel_id:
            catalog = fetch_channel_catalog(channel_id)
            

            if catalog and "description" in catalog:
                price_text = catalog["description"]
                
                # "가격 정보 없음" 케이스는 0 벡터로 처리합니다.
                if "가격 정보를 찾을 수 없습니다" not in price_text:
                    cleaned_price_text = price_text.replace("\n", " ").replace("-", "")
                    price_emb = get_bert_embedding(cleaned_price_text)
        
        # --- doc_embedding 및 tfidf_vector 생성 로직  ---
        doc_text = corpus[i]
        doc_emb = get_bert_embedding(doc_text)
        
        tfidf_vector = tfidf_matrix[i].toarray().flatten().tolist()

        bulk_ops.append(UpdateOne(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "doc_embedding": doc_emb.tolist(),
                    "price_embedding": price_emb.tolist(),
                    "tfidf_vector": tfidf_vector
                }
            }
        ))

    if bulk_ops:
        collection.bulk_write(bulk_ops)
        logger.info(f"개별 벡터/임베딩 생성 및 저장 완료: {len(bulk_ops)}개 문서.")
    
    return {"message": f"Separate embeddings and vectors generated for {len(bulk_ops)} documents. {(vocabulary[:100])}"}