from backend.services.dataset_loader import load_dataset
from backend.services.dataset_profiler import generate_profile
from backend.services.sensitive_detector import (
    detect_sensitive_and_identifier_columns,
)

from backend.services.domain_preset_service import (
    get_domain_preset,
)

from backend.repositories.dataset_repository import (
    get_dataset_profile,
    save_dataset_profile,
    get_dataset_domain_type,
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
        # 6. Get dataset domain
        # -----------------------------------------------------
        domain_type = get_dataset_domain_type(
            dataset_id
        )

        # -----------------------------------------------------
        # 7. Detect sensitive and identifier columns
        # -----------------------------------------------------
        sensitive_detection = (
            detect_sensitive_and_identifier_columns(
                dataframe
            )
        )

        # -----------------------------------------------------
        # 8. Apply domain-specific presets
        # -----------------------------------------------------
        for column_result in sensitive_detection:

            column_name = (
                column_result["column_name"]
            )

            preset = get_domain_preset(
                column_name,
                domain_type,
            )

            if preset:

                column_result["preset_applied"] = True

                column_result["suggested_type"] = (
                    preset["suggested_type"]
                )

                column_result["is_sensitive"] = (
                    preset["is_sensitive"]
                )

                column_result["is_identifier"] = (
                    preset["is_identifier"]
                )

            else:

                # Fall back to existing detection
                column_result["preset_applied"] = False

        # -----------------------------------------------------
        # 9. Add sensitive detection to profile
        # -----------------------------------------------------
        profile["sensitive_detection"] = (
            sensitive_detection
        )

        # -----------------------------------------------------
        # 10. Save generated profile
        # -----------------------------------------------------
        saved_profile = save_dataset_profile(
            dataset_id,
            profile,
        )

        # -----------------------------------------------------
        # 11. Return generated profile
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