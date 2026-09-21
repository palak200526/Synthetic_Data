ALLOWED_ACTIONS = {
    "keep",
    "remove",
    "mask",
    "generalize",
}


def validate_action(action: str) -> str:
    if not action:
        raise ValueError("Column action is required.")

    action = action.strip().lower()

    if action not in ALLOWED_ACTIONS:
        raise ValueError(
            f"Invalid column action: {action}. "
            f"Allowed actions are: {', '.join(sorted(ALLOWED_ACTIONS))}."
        )

    return action


def validate_column_configuration(configuration):
    if not configuration.column_name.strip():
        raise ValueError("Column name is required.")

    if configuration.dataset_id <= 0:
        raise ValueError("Dataset ID must be greater than zero.")

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