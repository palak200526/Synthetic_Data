from pathlib import Path

from backend.repositories.dataset_repository import (
    get_dataset_filename,
    get_dataset_user_id,
)

from backend.services.dataset_loader import load_dataset

from backend.utils.action_validator import (
    validate_column_configuration,
)

from backend.repositories.configuration_repository import (
    save_configuration,
    get_configurations,
)


UPLOAD_DIRECTORY = Path("data/uploads")


def find_dataset_file(dataset_id: int, filename: str):
    """
    Finds the actual uploaded dataset file.

    Files are stored inside date-wise folders and renamed
    using the dataset ID.
    """

    # Expected stored filename
    expected_filename = f"dataset_{dataset_id}_{filename}"

    # Search inside data/uploads recursively
    matches = list(
        UPLOAD_DIRECTORY.rglob(expected_filename)
    )

    if matches:
        return matches[0]

    # Fallback: search using original filename
    matches = list(
        UPLOAD_DIRECTORY.rglob(filename)
    )

    if matches:
        return matches[0]

    raise FileNotFoundError(
        f"Dataset file for dataset ID {dataset_id} "
        f"could not be found."
    )


def save_column_configurations(
    request,
    user_id: int
):
    saved_configurations = []
    seen_columns = set()

    for configuration in request.configurations:

        # ---------------------------------------------------------
        # 1. Verify dataset ownership
        # ---------------------------------------------------------
        dataset_user_id = get_dataset_user_id(
            configuration.dataset_id
        )

        if dataset_user_id != user_id:
            raise PermissionError(
                "You do not have access to this dataset."
            )

        # ---------------------------------------------------------
        # 2. Validate action and classification
        # ---------------------------------------------------------
        validate_column_configuration(
            configuration
        )

        # ---------------------------------------------------------
        # 3. Normalize column name
        # ---------------------------------------------------------
        configuration.column_name = (
            configuration.column_name.strip()
        )

        # ---------------------------------------------------------
        # 4. Check duplicate configuration
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # 5. Get original dataset filename
        # ---------------------------------------------------------
        filename = get_dataset_filename(
            configuration.dataset_id
        )

        # ---------------------------------------------------------
        # 6. Find actual uploaded file
        # ---------------------------------------------------------
        file_path = find_dataset_file(
            configuration.dataset_id,
            filename
        )

        # ---------------------------------------------------------
        # 7. Load exact dataset
        # ---------------------------------------------------------
        dataframe = load_dataset(
            str(file_path)
        )

        # ---------------------------------------------------------
        # 8. Verify column exists
        # ---------------------------------------------------------
        if configuration.column_name not in dataframe.columns:
            raise ValueError(
                f"Column '{configuration.column_name}' "
                f"does not exist in dataset "
                f"{configuration.dataset_id}."
            )

        # ---------------------------------------------------------
        # 9. Save configuration
        # ---------------------------------------------------------
        result = save_configuration(
            configuration
        )

        saved_configurations.append(result)

    return {
        "status": "success",
        "message": "Column configurations saved successfully.",
        "data": saved_configurations,
    }


def review_column_configurations(
    dataset_id: int,
    user_id: int
):

    # ---------------------------------------------------------
    # 1. Verify dataset ownership
    # ---------------------------------------------------------
    dataset_user_id = get_dataset_user_id(
        dataset_id
    )

    if dataset_user_id != user_id:
        raise PermissionError(
            "You do not have access to this dataset."
        )

    # ---------------------------------------------------------
    # 2. Get configurations
    # ---------------------------------------------------------
    configurations = get_configurations(
        dataset_id
    )

    if not configurations:
        return {
            "status": "error",
            "message": (
                "No column configurations found "
                f"for dataset {dataset_id}."
            ),
            "dataset_id": dataset_id,
            "data": [],
        }

    return {
        "status": "success",
        "message": "Column configurations retrieved successfully.",
        "dataset_id": dataset_id,
        "data": configurations,
    }