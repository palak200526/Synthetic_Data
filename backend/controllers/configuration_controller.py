from fastapi import APIRouter

from backend.schemas.configuration_schema import (
    ColumnConfigurationRequest,
)
from backend.services.configuration_service import (
    save_column_configurations,
)

router = APIRouter()


@router.post("/column-configurations")
def save_column_configurations_controller(
    request: ColumnConfigurationRequest
):
    return save_column_configurations(request)