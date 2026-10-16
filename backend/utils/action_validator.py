ALLOWED_ACTIONS = {
    "keep",
    "remove",
    "new_id",
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
    # Removed actions: they never produced new data, so they behave like keep.
    "generalize": "keep",
    "derived": "keep",
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
    # Only 'llm' columns may carry a rule; clear it for the rest
    # (old saved configs may still hold a leftover derived rule)
    # ---------------------------------------------------------
    if configuration.action != "llm":
        configuration.rule = None

    return True
