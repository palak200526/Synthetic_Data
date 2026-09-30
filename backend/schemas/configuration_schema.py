from pydantic import BaseModel
from typing import List


class DerivedRule(BaseModel):
    operation: str
    operands: List[str]


class ColumnConfiguration(BaseModel):
    dataset_id: int
    column_name: str
    column_type: str
    is_sensitive: bool
    is_identifier: bool
    action: str
    rule: DerivedRule | None = None


class ColumnConfigurationRequest(BaseModel):
    configurations: List[ColumnConfiguration]