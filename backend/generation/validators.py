import pandas as pd


def validate_synthetic_dataset(
    original_df: pd.DataFrame,
    synthetic_df: pd.DataFrame,
    required_rows: int
):
    """
    Validate the generated synthetic dataset.

    Checks:
    - Required record count
    - Same column names
    - Same column order
    - Compatible data types
    - Identifier uniqueness
    """

    errors = []

    # 1. Validate record count
    if len(synthetic_df) != required_rows:
        errors.append(
            f"Expected {required_rows} rows, "
            f"but generated {len(synthetic_df)} rows."
        )

    # 2. Validate columns
    if list(original_df.columns) != list(synthetic_df.columns):
        errors.append(
            "Synthetic dataset columns do not match "
            "the original dataset."
        )

    # 3. Validate data types
    for column in original_df.columns:

        if column not in synthetic_df.columns:
            continue

        original_dtype = original_df[column].dtype
        synthetic_dtype = synthetic_df[column].dtype

        if pd.api.types.is_numeric_dtype(original_dtype):

            if not pd.api.types.is_numeric_dtype(
                synthetic_dtype
            ):
                errors.append(
                    f"Column '{column}' should be numeric "
                    f"but generated dtype is {synthetic_dtype}."
                )

    # 4. Validate identifier uniqueness
    identifier_columns = [
        column
        for column in original_df.columns
        if column.lower().endswith("_id")
        or column.lower() == "id"
    ]

    for column in identifier_columns:

        if column not in synthetic_df.columns:
            continue

        if synthetic_df[column].duplicated().any():
            errors.append(
                f"Identifier column '{column}' "
                "contains duplicate values."
            )

    # Final result
    if errors:
        return {
            "valid": False,
            "errors": errors
        }

    return {
        "valid": True,
        "errors": []
    }