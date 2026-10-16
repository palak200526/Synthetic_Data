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
    dataset_id: int | None = None,
    *,
    for_generation: bool = False,
):

    if dataframe.empty:
        raise ValueError(
            "Dataset cannot be empty."
        )

    original_dataframe = dataframe.copy()

    # --------------------------------------------------
    # 1. Get saved column configurations
    # --------------------------------------------------

    if dataset_id is not None:
        configurations = get_configurations(dataset_id)
        domain_type = get_dataset_domain_type(dataset_id)
    else:
        configurations = []
        domain_type = "supply_chain"

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

            # Vectorized ID generation for speed and low memory usage
            dataframe[column_name] = "ID_" + pd.RangeIndex(
                1, len(dataframe) + 1
            ).astype(str)

        elif action in ("keep", "llm"):

            pass


    # --------------------------------------------------
    # 5. Apply domain-specific processing
    # --------------------------------------------------

    if domain_type == "supply_chain" and not for_generation:

        dataframe = generate_supply_chain_features(
            dataframe
        )

    # --------------------------------------------------
    # 6. Prepare data for generation
    # --------------------------------------------------

    skip_columns = [
        configuration["column_name"]
        for configuration in configurations
        if configuration.get("action") in ("llm", "new_id", "remove", "id")
        and configuration.get("column_name") in dataframe.columns
    ]

    # Also exclude any ID-like columns from dummy encoding
    for col in dataframe.columns:
        col_lower = str(col).lower()
        if col_lower == "id" or col_lower.endswith("_id") or col_lower.endswith("id"):
            if col not in skip_columns:
                skip_columns.append(col)

    if for_generation:
        # Generative models must receive the original column schema. One-hot
        # encoding here would turn categories into unrelated dummy columns and
        # prevent the generator from reconstructing the uploaded dataset shape.
        preparation_result = {
            "dataframe": dataframe.copy(),
            "numerical_columns": dataframe.select_dtypes(include="number").columns.tolist(),
            "categorical_columns": [
                column for column in dataframe.columns
                if column not in skip_columns and (
                    pd.api.types.is_object_dtype(dataframe[column].dtype)
                    or pd.api.types.is_string_dtype(dataframe[column].dtype)
                    or pd.api.types.is_bool_dtype(dataframe[column].dtype)
                    or isinstance(dataframe[column].dtype, pd.CategoricalDtype)
                )
            ],
        }
    else:
        preparation_result = prepare_data_for_model(
            dataframe,
            skip_columns=skip_columns,
        )

    processed_dataframe = preparation_result["dataframe"]

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