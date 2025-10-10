import yaml
from pathlib import Path
from pydantic import BaseModel, Field

from langchain_google_genai import ChatGoogleGenerativeAI


# prompts.yml 파일 로드
def load_prompts():
    prompts_path = Path(__file__).parent / "prompts.yml"
    with open(prompts_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

prompts = load_prompts()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    max_tokens=None,
    timeout=60,
    max_retries=2,
    # other params...
)