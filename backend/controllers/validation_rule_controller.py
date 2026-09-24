from fastapi import APIRouter

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


router = APIRouter()


@router.post(
    "/validation-rules",
    response_model=ValidationRuleResponse,
)
def create_validation_rule_api(
    request: ValidationRuleCreateRequest,
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
    response_model=ValidationRulesResponse,
)
def get_validation_rules_api(
    dataset_id: int,
):
    rules = get_rules(dataset_id)

    return {
        "status": "success",
        "message": "Validation rules retrieved successfully.",
        "rules": rules,
    }


@router.get(
    "/validation-rules/rule/{rule_id}",
    response_model=ValidationRuleResponse,
)
def get_validation_rule_api(
    rule_id: int,
):
    rule = get_rule(rule_id)

    return {
        "status": "success",
        "message": "Validation rule retrieved successfully.",
        "rule": rule,
    }


@router.delete(
    "/validation-rules/{rule_id}",
    response_model=ValidationRuleDeleteResponse,
)
def delete_validation_rule_api(
    rule_id: int,
):
    result = delete_rule(rule_id)

    return {
        "status": "success",
        "message": "Validation rule deleted successfully.",
        "rule_id": result["rule_id"],
    }