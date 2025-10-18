from pymongo import MongoClient
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

from core.mongo.connections import MongoCollections

# MongoDB 연결
mongo = MongoCollections()
collection = mongo.channel_data
similarity_collection = mongo.channel_similarity
drug_collection = mongo.drugs

# 임베딩 모델을 'upskyy/bge-m3-korean'으로 업그레이드
try:
    model = SentenceTransformer('upskyy/bge-m3-korean')
except Exception as e:
    print(f"Error loading SentenceTransformer model: {e}")
    raise

# 마약 가중치 로딩
def load_drug_weights():
    drugs = drug_collection.find({})
    weights = {}
    for drug in drugs:
        name = drug.get('drugName')
        count = drug.get('count', 1)
        if name:
            weights[name] = count
    return weights

# 텍스트 가중치 적용
def apply_weighted_keywords(text, weights):
    words = text.split()
    weighted_words = []
    for word in words:
        weight = int(weights.get(word, 1))
        weighted_words.extend([word] * weight)
    return ' '.join(weighted_words)

# 임베딩 함수를 SentenceTransformer에 맞게 간소화
def get_embedding(text):
    return model.encode(text, convert_to_numpy=True).astype(np.float64)

# 채널별 메시지 통합
def group_texts_by_channel():
    cursor = collection.find({}, {"channelId": 1, "text": 1, "timestamp": 1})
    grouped = {}
    timestamps = {}

    for doc in cursor:
        channel = doc["channelId"]
        text = doc.get("text", "")
        if not text.strip():
            continue
        grouped[channel] = grouped.get(channel, "") + " " + text
        timestamps[channel] = doc["timestamp"]  # 가장 마지막 메시지 기준으로 덮어씀

    return grouped, timestamps

# 채널 유사도 분석 및 저장
def calculate_and_store_channel_similarity():
    drug_weights = load_drug_weights()
    grouped_texts, timestamps = group_texts_by_channel()

    channel_ids = list(grouped_texts.keys())
    texts = [apply_weighted_keywords(grouped_texts[cid], drug_weights) for cid in channel_ids]
    embeddings = [get_embedding(text) for text in texts]

    similarity_matrix = cosine_similarity(np.array(embeddings))
    similarity_collection.delete_many({})  # 기존 데이터 삭제

    results = []
    for i, cid in enumerate(channel_ids):
        similar_channels = []
        for j, score in enumerate(similarity_matrix[i]):
            if i != j:
                similar_channels.append({
                    "channelId": channel_ids[j],
                    "similarity": float(score)
                })

        results.append({
            "channelId": cid,
            "timestamp": timestamps[cid],
            "similarChannels": sorted(similar_channels, key=lambda x: -x["similarity"])[:10]
        })

    if results:
        similarity_collection.insert_many(results)
    return {"message": "Channel similarity with drug weights saved to MongoDB."}
