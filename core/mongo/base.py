"""MongoDB 기본 객체 모듈 - Pydantic 기반 MongoDB 문서 모델의 기본 클래스

이 모듈은 MongoDB 컬렉션에 저장될 모든 문서 모델의 기본 클래스를 정의합니다.
Pydantic BaseModel을 상속받아 데이터 검증과 직렬화 기능을 제공하며,
MongoDB의 ObjectId 필드를 자동으로 처리합니다.

MongoDB Base Object Module - Base class for MongoDB document models based on Pydantic

This module defines the base class for all document models that will be stored
in MongoDB collections. It inherits from Pydantic BaseModel to provide
data validation and serialization features, and automatically handles
MongoDB's ObjectId field.
"""

from typing import Optional, Union

from bson import ObjectId
from pydantic import BaseModel, Field, field_validator, ConfigDict


class BaseMongoObject(BaseModel):
    """MongoDB 문서를 위한 기본 Pydantic 모델 클래스

    MongoDB에 저장될 모든 문서의 기본 구조를 정의합니다.
    ObjectId 필드를 자동으로 처리하고, 공통 설정을 제공합니다.
    데이터 검증, 직렬화/역직렬화, 타입 변환 등의 기능을 포함합니다.

    Base Pydantic model class for MongoDB documents

    Defines the basic structure for all documents to be stored in MongoDB.
    Automatically handles ObjectId fields and provides common configurations.
    Includes features for data validation, serialization/deserialization, and type conversion.

    Attributes:
        model_config (ConfigDict): Pydantic 모델 설정
                                  Pydantic model configuration
            - populate_by_name: 필드명과 별칭 모두 허용
                               Allow both field names and aliases
            - arbitrary_types_allowed: 임의 타입 허용
                                      Allow arbitrary types
            - str_strip_whitespace: 문자열 공백 제거
                                   Strip whitespace from strings
            - validate_assignment: 할당 시 검증 수행
                                  Validate on assignment

        oid (Optional[str]): MongoDB ObjectId의 문자열 표현
                           String representation of MongoDB ObjectId

    Examples:
        class MyModel(BaseMongoObject):
            name: str
            value: int

        # 모델 인스턴스 생성
        model = MyModel(name="test", value=42)

        # MongoDB에서 조회된 데이터로 모델 생성  
        model = MyModel(_id="507f1f77bcf86cd799439011", name="test", value=42)
    """
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    oid: Optional[str] = Field(
        default=None,
        title="Object ID",
        description="MongoDB object ID (string representation)",
        alias="_id",
        serialization_alias="_id",
        exclude=True
    )
