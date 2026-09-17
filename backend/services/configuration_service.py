from pathlib import Path

from backend.repositories.configuration_repository import (
    save_configuration,
)
from backend.repositories.dataset_repository import (
    get_dataset_filename,
)
from backend.services.dataset_loader import load_dataset
from backend.utils.action_validator import (
    validate_column_configuration,
)


UPLOAD_DIRECTORY = Path("data/uploads")


def save_column_configurations(request):
    saved_configurations = []
    seen_columns = set()

    for configuration in request.configurations:

        # 1. Validate action and classification
        validate_column_configuration(
            configuration
        )

        # 2. Normalize column name
        configuration.column_name = (
            configuration.column_name.strip()
        )

        # 3. Check for duplicate configuration
        key = (
            configuration.dataset_id,
            configuration.column_name,
        )

        if key in seen_columns:
            raise ValueError(
                f"Duplicate configuration for column "
                f"'{configuration.column_name}' "
                f"in dataset {configuration.dataset_id}."
            )

        seen_columns.add(key)

        # 4. Get the correct dataset file
        filename = get_dataset_filename(
            configuration.dataset_id
        )

        file_path = UPLOAD_DIRECTORY / filename

        # 5. Load the exact dataset
        dataframe = load_dataset(
            str(file_path)
        )

        # 6. Verify that the column exists
        if configuration.column_name not in dataframe.columns:
            raise ValueError(
                f"Column '{configuration.column_name}' "
                f"does not exist in dataset "
                f"{configuration.dataset_id}."
            )

        # 7. Save configuration
        result = save_configuration(
            configuration
        )

        saved_configurations.append(result)

    return {
        "status": "success",
        "message": "Column configurations saved successfully.",
        "data": saved_configurations,
    }