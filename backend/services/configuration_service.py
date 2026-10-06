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
    save_configurations_bulk,   # 👈 naya function
    get_configurations,
)


UPLOAD_DIRECTORY = Path("data/uploads")


def find_dataset_file(dataset_id: int, filename: str):
    """
    Finds the actual uploaded dataset file.

    Files are stored inside date-wise folders and renamed
    using the dataset ID.
    """

    expected_filename = f"dataset_{dataset_id}_{filename}"

    matches = list(UPLOAD_DIRECTORY.rglob(expected_filename))
    if matches:
        return matches[0]

    matches = list(UPLOAD_DIRECTORY.rglob(filename))
    if matches:
        return matches[0]

    raise FileNotFoundError(
        f"Dataset file for dataset ID {dataset_id} "
        f"could not be found."
    )


def save_column_configurations(request, user_id: int):
    """
    Save multiple column configurations in a single batch.

    Optimizations:
      1. Ownership verified ONCE (not per column)
      2. Dataset loaded ONCE (not 618 times)
      3. All validations done in memory
      4. Bulk insert into DB (single transaction)
    """

    if not request.configurations:
        raise ValueError("No configurations provided.")

    # ---------------------------------------------------------
    # 1. All configs must target the SAME dataset
    # ---------------------------------------------------------
    dataset_id = request.configurations[0].dataset_id

    for config in request.configurations:
        if config.dataset_id != dataset_id:
            raise ValueError(
                "All configurations must target the same dataset."
            )

    # ---------------------------------------------------------
    # 2. Ownership check — ONCE
    # ---------------------------------------------------------
    dataset_user_id = get_dataset_user_id(dataset_id)
    if dataset_user_id != user_id:
        raise PermissionError(
            "You do not have access to this dataset."
        )

    # ---------------------------------------------------------
    # 3. Load dataset ONCE
    # ---------------------------------------------------------
    filename = get_dataset_filename(dataset_id)
    file_path = find_dataset_file(dataset_id, filename)
    dataframe = load_dataset(str(file_path))

    valid_columns = set(dataframe.columns)

    # ---------------------------------------------------------
    # 4. Validate everything in memory (fast)
    # ---------------------------------------------------------
    seen_columns = set()
    prepared = []

    for configuration in request.configurations:

        # Action + rule validation
        validate_column_configuration(configuration)

        # Normalize column name
        configuration.column_name = configuration.column_name.strip()

        # Duplicate check
        if configuration.column_name in seen_columns:
            raise ValueError(
                f"Duplicate configuration for column "
                f"'{configuration.column_name}'."
            )
        seen_columns.add(configuration.column_name)

        # Column must exist in dataset
        if configuration.column_name not in valid_columns:
            raise ValueError(
                f"Column '{configuration.column_name}' does not exist "
                f"in dataset {dataset_id}."
            )

        prepared.append(configuration)

    # ---------------------------------------------------------
    # 5. Bulk save to DB (single transaction)
    # ---------------------------------------------------------
    saved_configurations = save_configurations_bulk(
        dataset_id=dataset_id,
        configurations=prepared,
    )

    return {
        "status": "success",
        "message": "Column configurations saved successfully.",
        "data": saved_configurations,
    }


def review_column_configurations(dataset_id: int, user_id: int):

    dataset_user_id = get_dataset_user_id(dataset_id)
    if dataset_user_id != user_id:
        raise PermissionError(
            "You do not have access to this dataset."
        )

    configurations = get_configurations(dataset_id)

    if not configurations:
        return {
            "status": "error",
            "message": (
                f"No column configurations found for dataset {dataset_id}."
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