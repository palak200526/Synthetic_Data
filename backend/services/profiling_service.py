from pathlib import Path

from backend.services.dataset_loader import load_dataset
from backend.services.dataset_profiler import generate_profile
from backend.services.sensitive_detector import (
    detect_sensitive_and_identifier_columns,
)

from backend.repositories.dataset_repository import (
    get_dataset_id_by_filename,
    get_dataset_profile,
    save_dataset_profile,
)


UPLOAD_DIRECTORY = Path("data/uploads")


def get_profile(filename: str):

    # 1. Get dataset ID
    dataset_id = get_dataset_id_by_filename(filename)

    # 2. Check if profile already exists
    try:
        saved_profile = get_dataset_profile(dataset_id)

        return {
            "status": "success",
            "message": "Dataset profile retrieved successfully.",
            "dataset_id": dataset_id,
            "profile_id": saved_profile["profile_id"],
            "data": saved_profile["profile_data"],
        }

    except ValueError:

        # 3. Profile does not exist, so generate it
        file_path = UPLOAD_DIRECTORY / filename

        dataframe = load_dataset(
            str(file_path)
        )

        profile = generate_profile(
            dataframe
        )

        # 4. Detect sensitive and identifier columns
        sensitive_detection = (
            detect_sensitive_and_identifier_columns(
                dataframe
            )
        )

        profile["sensitive_detection"] = (
            sensitive_detection
        )

        # 5. Save newly generated profile
        saved_profile = save_dataset_profile(
            dataset_id,
            profile,
        )

        # 6. Return newly generated profile
        return {
            "status": "success",
            "message": "Dataset profile generated successfully.",
            "dataset_id": dataset_id,
            "profile_id": saved_profile["profile_id"],
            "data": profile,
        }