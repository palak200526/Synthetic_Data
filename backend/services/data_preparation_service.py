import pandas as pd


def prepare_data_for_model(dataframe: pd.DataFrame):
    dataframe = dataframe.copy()

    numerical_columns = dataframe.select_dtypes(
        include="number"
    ).columns.tolist()

    categorical_columns = []

    for column in dataframe.columns:
        dtype = dataframe[column].dtype

        if (
            pd.api.types.is_string_dtype(dtype)
            or pd.api.types.is_object_dtype(dtype)
            or pd.api.types.is_bool_dtype(dtype)
            or isinstance(dtype, pd.CategoricalDtype)
        ):
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