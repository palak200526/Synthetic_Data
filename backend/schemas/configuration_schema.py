from pydantic import BaseModel
from typing import Any, List, Optional, Union


class DerivedRule(BaseModel):
    operation: str
    operands: List[str]


class ColumnConfiguration(BaseModel):
    dataset_id: int
    column_name: str
    column_type: str
    is_identifier: bool
    action: str
    rule: Optional[Union[DerivedRule, dict[str, Any]]] = None


class ColumnConfigurationRequest(BaseModel):
    configurations: List[ColumnConfiguration]