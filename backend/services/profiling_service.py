from pathlib import Path

from backend.services.dataset_loader import load_dataset
from backend.services.dataset_profiler import generate_profile
from backend.services.sensitive_detector import (
    detect_sensitive_and_identifier_columns,
)
from backend.repositories.dataset_repository import (
    get_dataset_id_by_filename,
    save_dataset_profile,
)

UPLOAD_DIRECTORY = Path("data/uploads")


def get_profile(filename: str):
    # 1. Get dataset ID
    dataset_id = get_dataset_id_by_filename(filename)

    # 2. Get dataset file
    file_path = UPLOAD_DIRECTORY / filename

    # 3. Load dataset
    dataframe = load_dataset(str(file_path))

    # 4. Generate profile
    profile = generate_profile(dataframe)

    # 5. Detect sensitive and identifier columns
    sensitive_detection = detect_sensitive_and_identifier_columns(
        dataframe
    )

    profile["sensitive_detection"] = sensitive_detection

    # 6. Save profile in database
    saved_profile = save_dataset_profile(
        dataset_id,
        profile,
    )

    return {
        "status": "success",
        "message": "Dataset profile generated successfully.",
        "dataset_id": dataset_id,
        "profile_id": saved_profile["profile_id"],
        "data": profile,
    }