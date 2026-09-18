from pydantic import BaseModel, Field


class RelationshipAnalysisRequest(BaseModel):
    test_size: float = Field(
        default=0.2,
        gt=0,
        lt=1,
    )
    random_state: int = 42