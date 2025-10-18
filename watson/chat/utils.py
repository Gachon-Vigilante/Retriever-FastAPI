from string import Formatter
from typing import Any, List, Union, Sequence
from pydantic import BaseModel

import yaml

import numpy as np
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, ToolMessage, AnyMessage

from utils import Logger
from watson.constants import retriever_tool_name

logger = Logger(__name__)

def fill_prompt(
        system_section: dict,
        additional_kwargs: dict=None,
) -> str:
    """
    프롬프트 섹션과 추가 인자를 바탕으로 템플릿 문자열을 채웁니다.

    주어진 `system_section` 내 `base` 템플릿에 등장하는 포맷 키들을 분석한 후,
    각 키에 해당하는 내용을 자동으로 매핑하여 문자열을 생성합니다.
    리스트로 구성된 항목은 `- 항목` 형식으로 줄바꿈되어 병합됩니다.

    "others" 키는 템플릿에 명시되지 않은 여분의 섹션들을 모아 한꺼번에 넣는 데 사용됩니다.

    Args:
        system_section (dict): 'base' 템플릿과 그 외 포맷 키별 내용을 포함한 프롬프트 사전.
        additional_kwargs (dict, optional): 추가적인 포맷 키-값 쌍. (현재 버전에서는 사용되지 않음)

    Returns:
        str: 포맷팅된 프롬프트 문자열.

    Raises:
        KeyError: 'base' 키가 `system_section`에 존재하지 않는 경우.
        ValueError: 템플릿에서 사용된 키가 `system_section`에 없는 경우 포맷팅 실패 가능성.
    """
    if additional_kwargs is None:
        additional_kwargs = {}
    base_template = system_section['base']['content']
    available_keys = set(system_section.keys()) - {'base'}

    # 1. 템플릿에서 사용된 포맷 키 추출
    used_keys = {
        field_name for _, field_name, _, _ in Formatter().parse(base_template)
        if field_name
    }

    matched = {}  # 섹션에 키가 따로 분류되어 있어, 자동으로 채울 값
    others_parts = []  # 따로 한꺼번에 리스트로 묶어서 채울 값

    # 2. 템플릿에 있는 포맷 키들 중, rules를 제외한 나머지 키를 system 섹션에서 찾아서 채워넣기
    for key in used_keys:
        if key == "others":
            continue  # 직접 주입할 값은 나중에 따로 처리
        if key in system_section:
            content = system_section[key].get('content', '')
            if isinstance(content, list):
                matched[key] = '\n'.join(f"- {item}" for item in content)
            elif isinstance(content, str):
                matched[key] = content
            else:
                matched[key] = ''

        else:
            matched[key] = '' # base 템플릿에서 매칭되지 않은 포맷 문자열은 제거 대상

    # 3. 명시적으로 base에 포맷 문자열로 등록되지 않은, rules에 들어갈 나머지 키들을 계산해서 rules로 병합
    remaining_keys = (available_keys - used_keys) | {"others"} # 포맷에 직접 안 쓰인 키들
    for key in remaining_keys:
        if system_section.get(key):
            content = system_section[key].get('content')
            if isinstance(content, list):
                others_parts.extend(f"- {item}" for item in content)
            elif isinstance(content, str):
                others_parts.append(f"- {content}")

    if "others" in used_keys:
        matched["others"] = '\n'.join(others_parts)

    # 4. 실제 포맷 수행
    result = base_template.format(**matched)

    return result


def count_korean_tokens(text: Union[str, BaseMessage]) -> int:
    # 한글 기준 1자 = 1.2 토큰 정도로 잡음 (보수적으로)

    return int(len(text.content if isinstance(text, BaseMessage) else text) * 1.2)

class NoSystemMessageError(ValueError):
    """SystemMessage가 메시지 내에 존재하지 않을 때 발생하는 예외"""
    pass


def trim_messages_by_token_limit_with_system_start(
    messages: Sequence[BaseMessage],
    max_tokens: int
) -> List[BaseMessage]:
    """
    SystemMessage부터 시작해서 max_tokens 이내로 메시지를 잘라 반환.
    SystemMessage 하나만 있어도 초과하면 허용함.

    Args:
        messages (Sequence[BaseMessage]): LangChain 메시지 객체들의 리스트.
        max_tokens (int): 최대 허용 토큰 수.

    Returns:
        List[BaseMessage]: 조건을 만족하는 메시지 서브셋.
    """
    # 1. 뒤에서부터 앞으로 전체 순회하며 토큰 카운트
    total_tokens = 0
    selected = []

    for message in reversed(messages):
        tokens = count_korean_tokens(message)
        if total_tokens + tokens > max_tokens:
            break
        selected.append(message)
        total_tokens += tokens

    if not selected:
        return []

    # 2. selected는 역순이므로 다시 원래 순서로
    selected = list(reversed(selected))

    # 3. SystemMessage부터 시작하도록 자르기
    system_start_idx = None
    for idx, msg in enumerate(selected):
        if isinstance(msg, SystemMessage):
            # 연속된 SystemMessage가 있다면 가장 앞의 것을 선택
            while idx > 0 and isinstance(selected[idx - 1], SystemMessage):
                idx -= 1
            system_start_idx = idx
            break

    if system_start_idx is None:
        raise NoSystemMessageError("SystemMessage가 현재 State의 messages에 포함되어 있지 않습니다. 최소 1개 필요합니다.")

    trimmed = selected[system_start_idx:]

    # 4. 이 묶음의 토큰 수가 max를 초과하더라도 허용
    return trimmed

def is_cachable(
    messages: Sequence[BaseMessage]
) -> bool:
    """
    가장 마지막 메세지에서부터 거꾸로 순회하면서,
    가장 마지막 QA chain에 ToolMessage가 있고 모두 retriever의 결과로만 구성되어 있을 경우 캐시가 가능하다는 것을 반환하는 함수.
    """
    cachable = False
    for message in reversed(messages):
        if isinstance(message, ToolMessage):
            if message.name == retriever_tool_name:
                cachable = True
            else:
                return False
        elif isinstance(message, HumanMessage):
            return cachable
    return False # 일반적으로는 message sequence 중에 HumanMessage에 도달하는 것이 일반적이나, 오류에 대비해 안전하게 False 반환

def load_prompts(yaml_path: str) -> dict:
    """
    YAML 파일로부터 프롬프트 정의를 로드합니다.

    지정된 경로의 YAML 파일을 읽어 파이썬 딕셔너리 형태로 반환합니다.
    일반적으로 system/user 프롬프트 템플릿을 포함한 구조를 다룰 때 사용됩니다.

    Args:
        yaml_path (str): 프롬프트 정의가 담긴 YAML 파일의 경로.

    Returns:
        dict: YAML 파일에서 로드한 프롬프트 정의 딕셔너리.

    Raises:
        FileNotFoundError: 지정된 YAML 파일이 존재하지 않을 경우.
        yaml.YAMLError: YAML 파싱 중 문법 오류가 발생한 경우.
        UnicodeDecodeError: 파일 인코딩 오류가 발생한 경우.
    """
    with open(yaml_path, 'r', encoding='utf-8') as file:
        prompt = yaml.safe_load(file)
    return prompt["chatbot"]

def get_last_ai_message(
        state: Union[List[AnyMessage], dict[str, Any], BaseModel],
        messages_key: str = "messages",
) -> BaseMessage:
    """
    가장 마지막 메세지를 반환하는 함수.
    일반적으로는 반환값이 AI Message일 것을 기대하고 있음.
    """
    if isinstance(state, list):
        ai_message = state[-1]
    elif isinstance(state, dict) and (messages := state.get(messages_key, [])):
        ai_message = messages[-1]
    elif messages := getattr(state, messages_key, []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state to check_cached edge: {state}")
    return ai_message

def load_yaml_file(path: str, key_structure: list[str], fallback: Any = None, label: str = "") -> Any:
    """
    공통 YAML 로더
    :param path: YAML 파일 경로
    :param key_structure: 필수 키 경로 예: ['mbti_profiles'] or ['mbti_compatibility', 'scores']
    :param fallback: 실패 시 반환할 값
    :param label: 로그 식별자 (예: "MBTI", "이모지 퀴즈")
    :return: key_structure에 따라 추출된 값 or fallback
    """
    try:
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)

            # 중첩 키 구조 탐색
            for key in key_structure:
                data = data[key]

        logger.info(f"[YML] {label} YAML 로딩 및 파싱 성공: {path}")
        return data

    except Exception as err:
        logger.error(f"[YML] {label} YAML 처리 실패: {err}")

        if fallback is not None:
            logger.warning(f"[YML] {label} fallback 값 반환")
            return fallback

        raise


def cosine_distance(a: list[float], b: list[float]) -> float:
    a = np.array(a)
    b = np.array(b)
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0  # 최대 거리로 취급
    return 1.0 - dot_product / (norm_a * norm_b)
