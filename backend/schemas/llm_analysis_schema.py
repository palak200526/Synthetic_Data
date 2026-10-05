from pydantic import BaseModel, Field
from typing import List


class ColumnLLMAnalysis(BaseModel):
    column_name: str

    is_identifier: bool

    action: str = Field(
        ...,
        description=(
            "Action to apply during synthetic data generation. "
            "Allowed values: keep, remove, new_id, generalize, derived, llm."
        )
    )

    reason: str


class LLMAnalysisResponse(BaseModel):
    columns: List[ColumnLLMAnalysis]