from pydantic import BaseModel
from typing import Optional


class GenerationRequest(BaseModel):
    dataset_id: int
    model_name: str
    parameters: Optional[dict] = None


class EvaluationRequest(BaseModel):
    result_id: int


class DashboardResponse(BaseModel):
    status: str
    message: str


class ReportResponse(BaseModel):
    status: str
    message: str


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