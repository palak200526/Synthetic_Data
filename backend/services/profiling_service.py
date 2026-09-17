from pathlib import Path

from backend.services.dataset_loader import load_dataset
from backend.services.dataset_profiler import generate_profile
from backend.services.sensitive_detector import (
    detect_sensitive_and_identifier_columns,
)


UPLOAD_DIRECTORY = Path("data/uploads")


def get_profile(filename: str):
    file_path = UPLOAD_DIRECTORY / filename

    dataframe = load_dataset(str(file_path))

    # Generate normal dataset profile
    profile = generate_profile(dataframe)

    # Detect sensitive and identifier columns
    sensitive_detection = detect_sensitive_and_identifier_columns(dataframe)

    # Add detection results to profile
    profile["sensitive_detection"] = sensitive_detection

    return {
        "status": "success",
        "message": "Dataset profile generated successfully.",
        "data": profile,
    }