from pathlib import Path

from backend.repositories.dataset_repository import (
    get_dataset_filename,
    get_dataset_user_id,
)

from backend.services.dataset_loader import load_dataset

from backend.services.column_profile_service import (
    build_dataset_column_profiles,
)

from backend.services.llm_column_analysis_service import (
    analyze_columns,
)


UPLOAD_DIRECTORY = Path("data/uploads")


def find_dataset_file(dataset_id: int, filename: str):
    """
    Find the uploaded dataset file for a dataset ID.
    """

    expected_filename = f"dataset_{dataset_id}_{filename}"

    matches = list(
        UPLOAD_DIRECTORY.rglob(expected_filename)
    )

    if matches:
        return matches[0]

    matches = list(
        UPLOAD_DIRECTORY.rglob(filename)
    )

    if matches:
        return matches[0]

    raise FileNotFoundError(
        f"Dataset file for dataset ID {dataset_id} "
        f"could not be found."
    )


def analyze_dataset_columns(
    dataset_id: int,
    user_id: int,
):
    """
    Load a user's dataset, build detailed column profiles,
    and ask the LLM to determine identifier status and
    generation action for every column.
    """

    # ---------------------------------------------------------
    # 1. Verify dataset ownership
    # ---------------------------------------------------------

    dataset_user_id = get_dataset_user_id(dataset_id)

    if dataset_user_id != user_id:
        raise PermissionError(
            "You do not have access to this dataset."
        )

    # ---------------------------------------------------------
    # 2. Get original filename
    # ---------------------------------------------------------

    filename = get_dataset_filename(dataset_id)

    # ---------------------------------------------------------
    # 3. Find uploaded file
    # ---------------------------------------------------------

    file_path = find_dataset_file(
        dataset_id,
        filename,
    )

    # ---------------------------------------------------------
    # 4. Load dataset
    # ---------------------------------------------------------

    dataframe = load_dataset(
        str(file_path)
    )

    # ---------------------------------------------------------
    # 5. Build detailed column profiles
    # ---------------------------------------------------------

    profiles = build_dataset_column_profiles(
        dataframe
    )

    # ---------------------------------------------------------
    # 6. Send profiles to LLM
    # ---------------------------------------------------------

    analysis = analyze_columns(
        profiles
    )

    # ---------------------------------------------------------
    # 7. Return result
    # ---------------------------------------------------------

    return {
        "status": "success",
        "dataset_id": dataset_id,
        "data": analysis.model_dump(),
    }