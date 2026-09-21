from pydantic import BaseModel
from typing import List


class ColumnConfiguration(BaseModel):
    dataset_id: int
    column_name: str
    column_type: str
    is_sensitive: bool
    is_identifier: bool
    action: str


class ColumnConfigurationRequest(BaseModel):
    configurations: List[ColumnConfiguration]