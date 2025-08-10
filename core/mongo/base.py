from typing import Optional, Union

from bson import ObjectId
from pydantic import BaseModel, Field, field_validator, ConfigDict


class BaseMongoObject(BaseModel):
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
