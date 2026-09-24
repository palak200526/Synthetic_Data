from backend.repositories.validation_rules_repository import (
    create_validation_rule,
    get_validation_rules,
    get_validation_rule,
    delete_validation_rule,
)


SUPPORTED_RULE_TYPES = {
    "non_negative",
    "date_order",
    "range",
    "allowed_values",
    "not_null",
}


def create_rule(
    dataset_id: int,
    rule_name: str,
    rule_type: str,
    rule_definition: dict,
    description: str | None = None,
    is_active: bool = True,
):
    if not dataset_id:
        raise ValueError("Dataset ID is required.")

    if not rule_name or not rule_name.strip():
        raise ValueError("Rule name is required.")

    rule_type = rule_type.strip().lower()

    if rule_type not in SUPPORTED_RULE_TYPES:
        raise ValueError(
            f"Unsupported rule type: {rule_type}. "
            f"Supported rule types: "
            f"{', '.join(sorted(SUPPORTED_RULE_TYPES))}."
        )

    if not isinstance(rule_definition, dict):
        raise ValueError("Rule definition must be a dictionary.")

    if not rule_definition:
        raise ValueError("Rule definition cannot be empty.")

    return create_validation_rule(
        dataset_id=dataset_id,
        rule_name=rule_name.strip(),
        rule_type=rule_type,
        rule_definition=rule_definition,
        description=description,
        is_active=is_active,
    )


def get_rules(dataset_id: int):
    if not dataset_id:
        raise ValueError("Dataset ID is required.")

    return get_validation_rules(dataset_id)


def get_rule(rule_id: int):
    if not rule_id:
        raise ValueError("Rule ID is required.")

    rule = get_validation_rule(rule_id)

    if rule is None:
        raise ValueError(
            f"Validation rule {rule_id} not found."
        )

    return rule


def delete_rule(rule_id: int):
    if not rule_id:
        raise ValueError("Rule ID is required.")

    result = delete_validation_rule(rule_id)

    if result is None:
        raise ValueError(
            f"Validation rule {rule_id} not found."
        )

    return result