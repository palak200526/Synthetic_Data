from fastapi import APIRouter, Depends

from backend.schemas.api_schema import (
    ValidationRuleCreateRequest,
    ValidationRuleResponse,
    ValidationRulesResponse,
    ValidationRuleDeleteResponse,
)

from backend.services.validation_rule_service import (
    create_rule,
    get_rules,
    get_rule,
    delete_rule,
)

from backend.utils.auth_dependency import get_current_user


router = APIRouter(
    prefix="",
    tags=["Validation Rules"],
)


@router.post(
    "/validation-rules",
    summary="Create validation rule",
    description=(
        "Creates and stores a configurable business validation rule for a "
        "dataset. Rules can define constraints such as non-negative values "
        "or valid relationships between columns and are enforced during "
        "synthetic data generation."
    ),
    response_model=ValidationRuleResponse,
)
def create_validation_rule_api(
    request: ValidationRuleCreateRequest,
    current_user=Depends(get_current_user),
):
    rule = create_rule(
        dataset_id=request.dataset_id,
        rule_name=request.rule_name,
        rule_type=request.rule_type,
        rule_definition=request.rule_definition,
        description=request.description,
        is_active=request.is_active,
    )

    return {
        "status": "success",
        "message": "Validation rule created successfully.",
        "rule": rule,
    }


@router.get(
    "/validation-rules/{dataset_id}",
    summary="Get dataset validation rules",
    description=(
        "Retrieves all validation rules configured for the specified dataset. "
        "The returned rules can be reviewed before or during synthetic data "
        "generation."
    ),
    response_model=ValidationRulesResponse,
)
def get_validation_rules_api(
    dataset_id: int,
    current_user=Depends(get_current_user),
):
    rules = get_rules(dataset_id)

    return {
        "status": "success",
        "message": "Validation rules retrieved successfully.",
        "rules": rules,
    }


@router.get(
    "/validation-rules/rule/{rule_id}",
    summary="Get validation rule",
    description=(
        "Retrieves the details of a specific validation rule using its rule ID, "
        "including its rule type, definition, active status, and associated "
        "dataset."
    ),
    response_model=ValidationRuleResponse,
)
def get_validation_rule_api(
    rule_id: int,
    current_user=Depends(get_current_user),
):
    rule = get_rule(rule_id)

    return {
        "status": "success",
        "message": "Validation rule retrieved successfully.",
        "rule": rule,
    }


@router.delete(
    "/validation-rules/{rule_id}",
    summary="Delete validation rule",
    description=(
        "Deletes a configured validation rule using its rule ID. "
        "The rule will no longer be available for enforcement during "
        "synthetic data generation."
    ),
    response_model=ValidationRuleDeleteResponse,
)
def delete_validation_rule_api(
    rule_id: int,
    current_user=Depends(get_current_user),
):
    result = delete_rule(rule_id)

    return {
        "status": "success",
        "message": "Validation rule deleted successfully.",
        "rule_id": result["rule_id"],
    }