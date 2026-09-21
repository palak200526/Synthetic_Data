import pandas as pd


def validate_preprocessing_output(
    original_dataframe: pd.DataFrame,
    processed_dataframe: pd.DataFrame,
):
    errors = []

    # 1. Processed dataframe should not be empty
    if processed_dataframe.empty:
        errors.append("Preprocessed dataset is empty.")

    # 2. Row count should remain unchanged
    if len(original_dataframe) != len(processed_dataframe):
        errors.append(
            "Row count changed during preprocessing."
        )

    # 3. Check for remaining missing values
    missing_values = processed_dataframe.isna().sum()

    columns_with_missing_values = (
        missing_values[missing_values > 0].index.tolist()
    )

    if columns_with_missing_values:
        errors.append(
            "Missing values remain in columns: "
            + ", ".join(
                str(column)
                for column in columns_with_missing_values
            )
        )

    # 4. Check for infinite values
    numerical_data = processed_dataframe.select_dtypes(
        include="number"
    )

    if not numerical_data.empty:
        has_infinite_values = (
            numerical_data
            .isin([float("inf"), float("-inf")])
            .any()
            .any()
        )

        if has_infinite_values:
            errors.append(
                "Preprocessed dataset contains infinite values."
            )

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
    }