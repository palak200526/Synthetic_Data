from backend.services.dataset_loader import load_dataset
from backend.services.dataset_profiler import generate_profile

from backend.repositories.dataset_repository import (
    get_dataset_profile,
    save_dataset_profile,
    get_dataset_file_path,
    get_dataset_user_id,
)


def get_profile(dataset_id: int, user_id: int):

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
    # 2. Check if profile already exists
    # ---------------------------------------------------------
    try:

        saved_profile = get_dataset_profile(
            dataset_id
        )

        return {
            "status": "success",
            "message": (
                "Dataset profile retrieved successfully."
            ),
            "dataset_id": dataset_id,
            "profile_id": saved_profile["profile_id"],
            "data": saved_profile["profile_data"],
        }

    except ValueError:

        # -----------------------------------------------------
        # 3. Get actual stored dataset file path
        # -----------------------------------------------------
        file_path = get_dataset_file_path(
            dataset_id
        )

        # -----------------------------------------------------
        # 4. Load dataset
        # -----------------------------------------------------
        dataframe = load_dataset(
            file_path
        )

        # -----------------------------------------------------
        # 5. Generate basic dataset profile
        # -----------------------------------------------------
        profile = generate_profile(
            dataframe
        )

        # -----------------------------------------------------
        # 6. Save generated profile
        # -----------------------------------------------------
        saved_profile = save_dataset_profile(
            dataset_id,
            profile,
        )

        # -----------------------------------------------------
        # 7. Return profile
        # -----------------------------------------------------
        return {
            "status": "success",
            "message": (
                "Dataset profile generated successfully."
            ),
            "dataset_id": dataset_id,
            "profile_id": saved_profile["profile_id"],
            "data": profile,
        }