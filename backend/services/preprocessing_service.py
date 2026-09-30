import pandas as pd

from backend.repositories.configuration_repository import (
    get_configurations,
)

from backend.repositories.dataset_repository import (
    get_dataset_domain_type,
)

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


def preprocess_dataset(
    dataframe: pd.DataFrame,
    dataset_id: int
):

    if dataframe.empty:
        raise ValueError(
            "Dataset cannot be empty."
        )

    original_dataframe = dataframe.copy()

    # --------------------------------------------------
    # 1. Get saved column configurations
    # --------------------------------------------------

    configurations = get_configurations(
        dataset_id
    )

    # --------------------------------------------------
    # 2. Detect outliers
    # --------------------------------------------------

    iqr_outliers = detect_outliers_iqr(
        dataframe
    )

    zscore_outliers = detect_outliers_zscore(
        dataframe
    )

    # --------------------------------------------------
    # 3. Handle missing values
    # --------------------------------------------------

    dataframe = handle_missing_values(
        dataframe
    )

    # --------------------------------------------------
    # 4. Apply column configurations
    # --------------------------------------------------

    for configuration in configurations:

        column_name = configuration[
            "column_name"
        ]

        action = configuration[
            "action"
        ]

        if column_name not in dataframe.columns:
            continue

        if action == "remove":

            dataframe = dataframe.drop(
                columns=[column_name]
            )

        elif action == "new_id":

            dataframe[column_name] = [
                f"ID_{i + 1}"
                for i in range(
                    len(dataframe)
                )
            ]

        elif action == "keep":

            pass

        elif action == "generalize":

            # Generalization will be
            # implemented using rule configuration.
            pass

        elif action == "derived":

            # Derived column logic will be
            # implemented using rule configuration.
            pass

    # --------------------------------------------------
    # 5. Apply domain-specific processing
    # --------------------------------------------------

    domain_type = get_dataset_domain_type(
        dataset_id
    )

    if domain_type == "supply_chain":

        dataframe = generate_supply_chain_features(
            dataframe
        )

    # --------------------------------------------------
    # 6. Prepare data for generation
    # --------------------------------------------------

    preparation_result = prepare_data_for_model(
        dataframe
    )

    processed_dataframe = (
        preparation_result["dataframe"]
    )

    # --------------------------------------------------
    # 7. Validate preprocessing output
    # --------------------------------------------------

    validation_result = (
        validate_preprocessing_output(
            original_dataframe,
            processed_dataframe,
        )
    )

    if not validation_result["is_valid"]:

        raise ValueError(
            "Preprocessing validation failed: "
            + "; ".join(
                validation_result["errors"]
            )
        )

    return {
        "dataframe": processed_dataframe,

        "numerical_columns":
            preparation_result[
                "numerical_columns"
            ],

        "categorical_columns":
            preparation_result[
                "categorical_columns"
            ],

        "outliers": {
            "iqr": iqr_outliers,
            "zscore": zscore_outliers,
        },

        "validation":
            validation_result,
    }