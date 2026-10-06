ALLOWED_ACTIONS = {
    "keep",
    "remove",
    "generalize",
    "new_id",
    "derived",
    "llm",
}

ACTION_ALIASES = {
    "llm_generate": "llm",
    "llm_text": "llm",
    "text": "llm",
    "generate_llm": "llm",
    "llm text": "llm",
    "drop": "remove",
    "delete": "remove",
    "exclude": "remove",
    "id": "new_id",
    "identifier": "new_id",
    "new id": "new_id",
    "synthesize": "keep",
    "generate": "keep",
    "standard": "keep",
}


ALLOWED_DERIVED_OPERATIONS = {
    "add",
    "subtract",
    "multiply",
    "divide",
}


def validate_action(action: str) -> str:
    if not action:
        raise ValueError(
            "Column action is required."
        )

    action = action.strip().lower()
    action = ACTION_ALIASES.get(action, action)

    if action not in ALLOWED_ACTIONS:
        raise ValueError(
            f"Invalid column action: {action}. "
            f"Allowed actions are: "
            f"{', '.join(sorted(ALLOWED_ACTIONS))}."
        )

    return action


def validate_column_configuration(
    configuration
):
    # ---------------------------------------------------------
    # Validate column name
    # ---------------------------------------------------------
    if not str(configuration.column_name or "").strip():
        raise ValueError(
            "Column name is required."
        )

    # ---------------------------------------------------------
    # Validate dataset ID
    # ---------------------------------------------------------
    if configuration.dataset_id <= 0:
        raise ValueError(
            "Dataset ID must be greater than zero."
        )

    # ---------------------------------------------------------
    # Validate action
    # ---------------------------------------------------------
    configuration.action = validate_action(
        configuration.action
    )

    # ---------------------------------------------------------
    # Validate new_id action
    # ---------------------------------------------------------
    if configuration.action == "new_id":
        configuration.is_identifier = True

    if configuration.action == "llm":
        configuration.is_identifier = False

    # ---------------------------------------------------------
    # Validate derived-column rule
    # ---------------------------------------------------------
    if configuration.action == "derived":
        if configuration.rule is None:
            raise ValueError(
                f"Derived column '{configuration.column_name}' requires a rule."
            )

        operation = getattr(configuration.rule, "operation", None)
        operands = getattr(configuration.rule, "operands", None)

        if isinstance(configuration.rule, dict):
            operation = configuration.rule.get("operation")
            operands = configuration.rule.get("operands")

        if operation not in ALLOWED_DERIVED_OPERATIONS:
            raise ValueError(
                f"Unsupported derived operation: {operation}. "
                f"Allowed operations are: "
                f"{', '.join(sorted(ALLOWED_DERIVED_OPERATIONS))}."
            )

        if not operands or len(operands) < 2:
            raise ValueError(
                f"Derived column '{configuration.column_name}' requires at least two operands."
            )

        for operand in operands:
            if not str(operand or "").strip():
                raise ValueError(
                    f"Invalid operand in derived rule for column '{configuration.column_name}'."
                )

    # ---------------------------------------------------------
    # Non-derived / non-llm columns should not have complex rules
    # ---------------------------------------------------------
    if configuration.action in ("llm", "derived"):
        return True

    if configuration.rule is not None and isinstance(configuration.rule, dict) and len(configuration.rule) > 0:
        raise ValueError(
            f"Column '{configuration.column_name}' cannot have a derived rule because its action is '{configuration.action}'."
        )

    return True