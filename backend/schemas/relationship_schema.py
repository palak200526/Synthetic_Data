from pydantic import BaseModel, Field


class RelationshipAnalysisRequest(BaseModel):
    test_size: float = Field(
        default=0.2,
        gt=0,
        lt=1,
    )
    random_state: int = 42

class DatasetRelationshipRequest(BaseModel):

    group_id: int

    parent_dataset_id: int

    parent_column: str

    child_dataset_id: int

    child_column: str

    relationship_type: str = "one-to-many"