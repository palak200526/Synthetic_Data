ALLOWED_ACTIONS = {
    "keep",
    "remove",
    "mask",
    "generalize",
    "new_id",
    "derived",
}


ALLOWED_DERIVED_OPERATIONS = {
    "add",
    "subtract",
    "multiply",
    "divide",
}


def validate_action(action: str) -> str:
    if not action:
        raise ValueError("Column action is required.")

    action = action.strip().lower()

    if action not in ALLOWED_ACTIONS:
        raise ValueError(
            f"Invalid column action: {action}. "
            f"Allowed actions are: "
            f"{', '.join(sorted(ALLOWED_ACTIONS))}."
        )

    return action


def validate_column_configuration(configuration):

    if not configuration.column_name.strip():
        raise ValueError("Column name is required.")

    if configuration.dataset_id <= 0:
        raise ValueError(
            "Dataset ID must be greater than zero."
        )

    if (
        configuration.is_sensitive
        and configuration.is_identifier
    ):
        raise ValueError(
            f"Column '{configuration.column_name}' "
            "cannot be both sensitive and identifier."
        )

    configuration.action = validate_action(
        configuration.action
    )

    # Validate derived-column rule
    if configuration.action == "derived":

        if configuration.rule is None:
            raise ValueError(
                f"Derived column '{configuration.column_name}' "
                "requires a rule."
            )

        if configuration.rule.operation not in ALLOWED_DERIVED_OPERATIONS:
            raise ValueError(
                f"Unsupported derived operation: "
                f"{configuration.rule.operation}. "
                f"Allowed operations are: "
                f"{', '.join(sorted(ALLOWED_DERIVED_OPERATIONS))}."
            )

        if len(configuration.rule.operands) < 2:
            raise ValueError(
                f"Derived column '{configuration.column_name}' "
                "requires at least two operands."
            )

        for operand in configuration.rule.operands:
            if not operand.strip():
                raise ValueError(
                    f"Invalid operand in derived rule "
                    f"for column '{configuration.column_name}'."
                )