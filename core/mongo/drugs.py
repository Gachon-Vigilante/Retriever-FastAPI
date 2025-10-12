from enum import StrEnum

from bson import ObjectId
from pydantic import BaseModel, Field

from .connections import MongoCollections


class Argot(BaseModel):
    name: str = Field(
        title="마약 은어",
        description="마약 은어의 호칭."
    )
    description: str = Field(
        title="마약 은어 설명",
        description="마약 은어의 설명."
    )

class DrugsFields(StrEnum):
    drugbank_id = "drugbank_id",
    name = "name",
    drug_type = "drug_type",
    english_name = "english_name",
    argots = "argots",

class Drugs(BaseModel):
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
        new_drugs = self.model_dump()
        MongoCollections().drugs.insert_one(new_drugs)
        return new_drugs.get("_id")

    @classmethod
    def store_new_argot(cls, _id: ObjectId | str, argot: Argot):
        MongoCollections().drugs.update_one(
            {"_id": _id},
            {"$push": {DrugsFields.argots: argot.model_dump()}}
        )


class ArgotSearchResult(BaseModel):
    drugbank_id: str
    matched_argot: str

def get_all_argots() -> list[ArgotSearchResult]:
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

all_argots = get_all_argots()

def find_all_argots_in_text(text: str) -> list[ArgotSearchResult]:
    return [argot.model_copy(deep=True) for argot in all_argots if argot.matched_argot in text]
