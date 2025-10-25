"""약물/은어(Argot) 데이터 모델 및 검색 유틸리티

이 모듈은 마약류(Drug)와 그에 대응하는 은어(Argot) 목록을 MongoDB에서 관리하고,
문서 텍스트에서 은어를 빠르게 탐지하기 위한 간단한 유틸리티를 제공합니다.

구성 요소:
- Argot: 은어 항목 Pydantic 모델
- Drugs: 약물 문서 Pydantic 모델(약물 기본 정보 + 은어 배열)
- get_all_argots(): MongoDB에서 모든 은어를 평탄화하여 조회
- find_all_argots_in_text(): 텍스트에 포함된 은어를 전수 검사하여 매칭 결과 반환

주의:
- find_all_argots_in_text는 매우 단순한 포함 검사(in substring)로 동작합니다.
  고급 토큰화/정규화가 필요하면 후속 개선이 필요합니다.
"""
from enum import StrEnum

from bson import ObjectId
from pydantic import BaseModel, Field

from .connections import MongoCollections


class Argot(BaseModel):
    """마약 은어(속어) 항목 모델

    Attributes:
        name (str): 은어 텍스트.
        description (str): 은어 설명.
    """
    name: str = Field(
        title="마약 은어",
        description="마약 은어의 호칭."
    )
    description: str = Field(
        title="마약 은어 설명",
        description="마약 은어의 설명."
    )

class DrugsFields(StrEnum):
    """Drugs 문서 필드 상수"""
    drugbank_id = "drugbank_id",
    name = "name",
    drug_type = "drug_type",
    english_name = "english_name",
    argots = "argots",

class Drugs(BaseModel):
    """약물(Drug) 문서 모델

    약물 기본 정보(drugbank_id, 이름, 분류)와 연관 은어 목록을 저장합니다.
    """
    drugbank_id: str = Field(
        title="마약류 ID",
        description="마약류를 drugbank에서 분류한 ID.",
        alias=DrugsFields.drugbank_id,
    )
    name: str = Field(
        title="마약류 이름",
        description="마약류의 호칭.",
        alias=DrugsFields.name,
    )
    drug_type: str = Field(
        default="",
        title="마약류 종류",
        description="마약류의 법적인 분류.",
        alias=DrugsFields.drug_type,
    )
    english_name: str = Field(
        default="",
        title="마약류 영문명",
        description="마약류의 영문 이름.",
        alias=DrugsFields.english_name,
    )
    argots: list[Argot] = Field(
        default_factory=list,
        title="마약 은어 목록",
        description="마약류에 해당하는 마약 은어 목록.",
        alias=DrugsFields.argots,
    )

    def store(self) -> ObjectId:
        """약물 문서를 MongoDB에 저장하고 ObjectId를 반환합니다."""
        new_drugs = self.model_dump()
        MongoCollections().drugs.insert_one(new_drugs)
        return new_drugs.get("_id")

    @classmethod
    def store_new_argot(cls, _id: ObjectId | str, argot: Argot):
        """기존 약물 문서(_id)에 은어 항목을 추가합니다."""
        MongoCollections().drugs.update_one(
            {"_id": _id},
            {"$push": {DrugsFields.argots: argot.model_dump()}}
        )


class ArgotSearchResult(BaseModel):
    """은어 검색 결과 모델

    Attributes:
        drugbank_id (str): 해당 은어가 속한 약물 ID.
        matched_argot (str): 매칭된 은어 텍스트.
    """
    drugbank_id: str
    matched_argot: str

def get_all_argots() -> list[ArgotSearchResult]:
    """모든 약물 문서에서 은어를 평탄화하여 조회합니다.

    Returns:
        list[ArgotSearchResult]: drugbank_id와 은어 이름으로 구성된 결과 목록.
    """
    drugs_collection = MongoCollections().drugs

    pipeline = [
        # 1. argots 배열을 풀어헤칩니다.
        {"$unwind": "$argots"},
        # 2. 필요한 필드만 추출합니다.
        {
            "$project": {
                "_id": 0,
                DrugsFields.drugbank_id: f"${DrugsFields.drugbank_id}",
                "matched_argot": f"${DrugsFields.argots}.name",
            }
        }
    ]

    # Aggregation 실행
    results = [ArgotSearchResult(**doc) for doc in drugs_collection.aggregate(pipeline)]
    return results

# 프로세스 시작 시 전체 은어 목록을 캐싱하여 단순 포함 검색 속도 향상
all_argots = get_all_argots()

def find_all_argots_in_text(text: str) -> list[ArgotSearchResult]:
    """본문 텍스트에서 발견된 모든 은어를 반환합니다.

    단순 포함 검사(substring) 방식으로 동작하며, 케이스/어절 경계 처리 등은 수행하지 않습니다.

    Args:
        text (str): 검사할 본문 텍스트

    Returns:
        list[ArgotSearchResult]: 매칭된 은어 검색 결과 목록(깊은 복사)
    """
    return [argot.model_copy(deep=True) for argot in all_argots if argot.matched_argot in text]
