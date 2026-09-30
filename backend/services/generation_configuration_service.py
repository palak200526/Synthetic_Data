from backend.repositories.configuration_repository import (
    get_generation_configurations,
)


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
    }

    for config in configurations:

        action = config["action"]
        column_name = config["column_name"]

        if action not in grouped:
            raise ValueError(
                f"Unsupported action '{action}' "
                f"for column '{column_name}'."
            )

        grouped[action].append(column_name)

    return grouped