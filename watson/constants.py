import os
from enum import StrEnum

from dotenv import load_dotenv
from datetime import timedelta

from core.mongo.message import MessageFields

load_dotenv()

retriever_tool_name = "retriever_from_weaviate"
prompts_path = "watson/prompts.yml"
graph_mermaid_path = "graph.png"

EMBEDDING_DIMENSION = 1024

max_token_limit = 32000 # Claude-4-sonnet은 최대 200000 토큰까지 가능은 하지만, 32000 이하가 성능을 위해 권장된다고 함.
max_cache_size = 10000
max_cache_age: timedelta = timedelta(days=60)


weaviate_index_name = "TelegramMessages"

weaviate_headers={
    "X-HuggingFace-Api-Key": os.getenv("HUGGINGFACE_API_KEY"),
    "X-Cohere-Api-Key": os.getenv("COHERE_APIKEY"),
}

weaviate_http_host=os.getenv("WEAVIATE_HTTP_HOST", "localhost")
weaviate_http_port=int(os.getenv("WEAVIATE_HTTP_PORT", 8888))
weaviate_grpc_host=os.getenv("WEAVIATE_GRPC_HOST", "localhost")
weaviate_grpc_port=int(os.getenv("WEAVIATE_GRPC_PORT", 50051))

class WeaviateProperties(StrEnum):
    object_id = "object_id"
    message = MessageFields.message
    channel_id = MessageFields.channel_id
    message_id = MessageFields.message_id
    date = MessageFields.date
    views = MessageFields.views
