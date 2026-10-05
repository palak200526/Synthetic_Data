from pydantic import BaseModel
from typing import Optional


class GenerationRequest(BaseModel):
    dataset_id: int
    model_name: str
    parameters: Optional[dict] = None
    background: bool = True


class AutoTuneGenerationRequest(BaseModel):
    dataset_id: int
    model_name: str
    parameters: Optional[dict] = None
    max_attempts: int = 3
    min_score: float = 80.0
    improvement_threshold: float = 1.0


class EvaluationRequest(BaseModel):
    result_id: int


class DashboardResponse(BaseModel):
    status: str
    message: str
    total_datasets: Optional[int] = 0
    total_generations: Optional[int] = 0
    total_evaluations: Optional[int] = 0
    average_score: Optional[float] = None
    recent_datasets: Optional[list[dict]] = None
    recent_generations: Optional[list[dict]] = None
    recent_evaluations: Optional[list[dict]] = None
    data: Optional[dict] = None
    statistical_similarity: Optional[dict] = None
    correlation_covariance: Optional[dict] = None
    data_quality: Optional[dict] = None
    ml_utility: Optional[dict] = None
    relationship_integrity: Optional[dict] = None
    privacy: Optional[dict] = None

    class Config:
        extra = "allow"


class ReportGenerateRequest(BaseModel):
    result_id: int
    format: Optional[str] = "json"


class ReportResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None

    class Config:
        extra = "allow"


class DownloadResponse(BaseModel):
    status: str
    message: str

class MultiTableGenerationRequest(BaseModel):
    group_id: int
    model_name: str
    parameters: Optional[dict] = None

class ValidationRuleCreateRequest(BaseModel):
    dataset_id: int
    rule_name: str
    rule_type: str
    rule_definition: dict
    description: Optional[str] = None
    is_active: bool = True


class ValidationRuleResponse(BaseModel):
    status: str
    message: str
    rule: dict


class ValidationRulesResponse(BaseModel):
    status: str
    message: str
    rules: list[dict]


class ValidationRuleDeleteResponse(BaseModel):
    status: str
    message: str
    rule_id: int