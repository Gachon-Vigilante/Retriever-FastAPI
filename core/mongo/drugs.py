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

class Drugs(BaseModel):
    drugbank_id: str = Field(
        title="마약류 ID",
        description="마약류를 drugbank에서 분류한 ID."
    )
    drug_name: str = Field(
        title="마약류 이름",
        description="마약류의 호칭."
    )
    drug_type: str = Field(
        default="",
        title="마약류 종류",
        description="마약류의 법적인 분류."
    )
    drug_english_name: str = Field(
        default="",
        title="마약류 영문명",
        description="마약류의 영문 이름."
    )
    argots: list[Argot] = Field(
        default_factory=list,
        title="마약 은어 목록",
        description="마약류에 해당하는 마약 은어 목록."
    )

    def store(self) -> ObjectId:
        new_drugs = self.model_dump()
        MongoCollections().drugs.insert_one(new_drugs)
        return new_drugs.get("_id")

    @classmethod
    def store_new_argot(cls, _id: ObjectId | str, argot: Argot):
        MongoCollections().drugs.update_one(
            {"_id": _id},
            {"$push": {"argots": argot.model_dump()}}
        )

MongoCollections().drugs.create_index(
    [
        ("drugbank_id", 1),
    ],
    unique=True,
)
