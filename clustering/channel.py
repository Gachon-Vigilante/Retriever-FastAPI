from pymongo import MongoClient
import torch
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer, AutoModel

from server.db import Database

# MongoDB 연결
collection = Database.Collection.Channel.DATA
similarity_collection = Database.Collection.Channel.SIMILARITY
drug_collection = Database.Collection.DRUGS

# KoBERT 모델 로딩
model_name = "monologg/kobert"
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
model = AutoModel.from_pretrained(model_name, trust_remote_code=True)

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

# KoBERT 임베딩
def get_bert_embedding(text):
    tokens = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding="max_length")
    with torch.no_grad():
        output = model(**tokens)
    return output.last_hidden_state[:, 0, :].squeeze().tolist()

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
    embeddings = [get_bert_embedding(text) for text in texts]

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

    similarity_collection.insert_many(results)
    return {"message": "Channel similarity with drug weights saved to MongoDB."}
