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
        timestamps[channel] = doc["timestamp"]  # 가장 마지막 메시지로 갱신

    return grouped, timestamps

# similarity에 등록 안 된 채널만 자동 추출
def get_new_channels(grouped_texts):
    existing_similarities = similarity_collection.distinct("channelId")
    all_channel_ids = list(grouped_texts.keys())
    new_channels = [cid for cid in all_channel_ids if cid not in existing_similarities]
    return new_channels

# 신규 채널 유사도 계산 및 저장
def calculate_similarity_for_new_channels():
    drug_weights = load_drug_weights()
    grouped_texts, timestamps = group_texts_by_channel()

    new_channel_ids = get_new_channels(grouped_texts)

    if not new_channel_ids:
        return {"message": "No new channels to process."}

    # 기존 채널 ID와 임베딩 준비
    existing_channel_ids = [cid for cid in grouped_texts.keys() if cid not in new_channel_ids]
    existing_texts = [apply_weighted_keywords(grouped_texts[cid], drug_weights) for cid in existing_channel_ids]
    existing_embeddings = [get_embedding(text) for text in existing_texts] if existing_channel_ids else []

    results = []
    for new_channel_id in new_channel_ids:
        new_text = apply_weighted_keywords(grouped_texts[new_channel_id], drug_weights)
        new_embedding = get_embedding(new_text)

        # 기존 채널이 없으면 skip
        if not existing_channel_ids:
            similar_channels = []
        else:
            # 코사인 유사도 계산
            similarity_scores = cosine_similarity(
                [new_embedding],
                existing_embeddings
            )[0]

            similar_channels = []
            for cid, score in zip(existing_channel_ids, similarity_scores):
                similar_channels.append({
                    "channelId": cid,
                    "similarity": float(score)
                })

        results.append({
            "channelId": new_channel_id,
            "timestamp": timestamps[new_channel_id],
            "similarChannels": sorted(similar_channels, key=lambda x: -x["similarity"])[:10]
        })

    if results:
        similarity_collection.insert_many(results)

    return {"message": f"Similarity calculation complete for {len(new_channel_ids)} new channels."}
