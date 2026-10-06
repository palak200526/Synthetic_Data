from backend.repositories.configuration_repository import (
    get_generation_configurations,
)
from backend.utils.action_validator import validate_action


def get_generation_configuration(dataset_id: int):
    configurations = get_generation_configurations(
        dataset_id
    )

    if not configurations:
        raise ValueError(
            f"No column configurations found for dataset {dataset_id}."
        )

    return configurations


def group_columns_by_action(configurations):
    grouped = {
        "keep": [],
        "remove": [],
        "new_id": [],
        "generalize": [],
        "derived": [],
        "llm": [],
    }

    for config in configurations:
        raw_action = config.get("action", "keep")
        column_name = config.get("column_name", "")

        try:
            action = validate_action(raw_action)
        except Exception:
            action = "keep"

        grouped[action].append(column_name)

    return grouped