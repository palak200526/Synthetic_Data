import pandas as pd


def prepare_data_for_model(
    dataframe: pd.DataFrame,
    skip_columns=None,
    max_categories: int = 30,
):
    dataframe = dataframe.copy()
    skip = set(skip_columns or [])

    numerical_columns = dataframe.select_dtypes(
        include="number"
    ).columns.tolist()

    categorical_columns = []

    for column in dataframe.columns:
        if column in skip:
            continue

        dtype = dataframe[column].dtype

        if (
            pd.api.types.is_string_dtype(dtype)
            or pd.api.types.is_object_dtype(dtype)
            or pd.api.types.is_bool_dtype(dtype)
            or isinstance(dtype, pd.CategoricalDtype)
        ):
            # Only dummy-encode low-cardinality discrete categorical columns
            # High-cardinality columns (e.g. IDs, UUIDs, text) must NEVER be one-hot encoded
            # as that creates an O(N^2) explosion (e.g., 40,025 x 40,025 -> 12 GB RAM)
            n_unique = dataframe[column].nunique(dropna=True)
            if 1 <= n_unique <= max_categories:
                categorical_columns.append(column)

    if categorical_columns:
        dataframe = pd.get_dummies(
            dataframe,
            columns=categorical_columns,
            dtype=int,
        )

    return {
        "dataframe": dataframe,
        "numerical_columns": numerical_columns,
        "categorical_columns": categorical_columns,
    }