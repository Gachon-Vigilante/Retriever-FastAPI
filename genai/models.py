"""GenAI 모델 및 프롬프트 로더 모듈

이 모듈은 분석에 사용할 프롬프트(prompts.yml)를 로드하고, LangChain의
ChatGoogleGenerativeAI 클라이언트를 구성합니다. 서버 런타임 경로에서 직접
LLM을 호출하기보다는, 분석 파이프라인(analyzers/post.py)에서 배치 처리 용도로
활용하는 것을 권장합니다.

Google 스타일의 한국어 docstring을 사용하며, 기능 변경 없이 문서화만 제공합니다.

Examples:
    from genai.models import prompts, llm

    # 프롬프트 사용 예시
    print(prompts["analysis"]["post"]["main"])  # 메인 지시문 출력

    # LLM 단발 호출(테스트 용도)
    resp = llm.invoke("Hello")
    print(resp.content)
"""
from pathlib import Path

import yaml
from langchain_google_genai import ChatGoogleGenerativeAI


# prompts.yml 파일 로드
def load_prompts() -> dict:
    """prompts.yml 파일을 로드하여 딕셔너리로 반환합니다.

    Returns:
        dict: prompts.yml의 내용을 파싱한 딕셔너리.

    Raises:
        FileNotFoundError: prompts.yml 파일이 존재하지 않는 경우.
        yaml.YAMLError: YAML 파싱 중 오류가 발생한 경우.

    Examples:
        data = load_prompts()
        system_prompt = data["analysis"]["post"]["main"]
    """
    prompts_path = Path(__file__).parent / "prompts.yml"
    with open(prompts_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

prompts = load_prompts()

# LangChain Google Generative AI 클라이언트 (테스트/도구적 사용)
# 운영 경로에서는 배치 API(google.genai)를 권장합니다.
llm_model_name = "gemini-2.5-pro"
llm = ChatGoogleGenerativeAI(
    model=llm_model_name,
    temperature=0,
    max_tokens=None,
    timeout=60,
    max_retries=2,
)
