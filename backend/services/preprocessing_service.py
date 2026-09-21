import pandas as pd

from backend.services.missing_value_service import (
    handle_missing_values,
)
from backend.services.outlier_service import (
    detect_outliers_iqr,
    detect_outliers_zscore,
)
from backend.services.feature_engineering_service import (
    generate_supply_chain_features,
)
from backend.services.data_preparation_service import (
    prepare_data_for_model,
)
from backend.services.preprocessing_validator import (
    validate_preprocessing_output,
)


def preprocess_dataset(dataframe: pd.DataFrame):

    if dataframe.empty:
        raise ValueError("Dataset cannot be empty.")

    original_dataframe = dataframe.copy()

    # 1. Detect outliers
    iqr_outliers = detect_outliers_iqr(dataframe)
    zscore_outliers = detect_outliers_zscore(dataframe)

    # 2. Handle missing values
    dataframe = handle_missing_values(dataframe)

    # 3. Generate supply-chain features
    dataframe = generate_supply_chain_features(dataframe)

    # 4. Prepare numerical and categorical data
    preparation_result = prepare_data_for_model(dataframe)

    processed_dataframe = preparation_result["dataframe"]

    # 5. Validate output
    validation_result = validate_preprocessing_output(
        original_dataframe,
        processed_dataframe,
    )

    if not validation_result["is_valid"]:
        raise ValueError(
            "Preprocessing validation failed: "
            + "; ".join(validation_result["errors"])
        )

    return {
        "dataframe": processed_dataframe,
        "numerical_columns": preparation_result[
            "numerical_columns"
        ],
        "categorical_columns": preparation_result[
            "categorical_columns"
        ],
        "outliers": {
            "iqr": iqr_outliers,
            "zscore": zscore_outliers,
        },
        "validation": validation_result,
    }