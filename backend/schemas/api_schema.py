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