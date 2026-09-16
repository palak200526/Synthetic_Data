import pandas as pd


def get_basic_profile(dataframe: pd.DataFrame) -> dict:
    """
    Generate basic dataset dimensions.
    """

    return {
        "row_count": int(dataframe.shape[0]),
        "column_count": int(dataframe.shape[1]),
    }

def get_column_types(dataframe: pd.DataFrame) -> dict:
    """
    Classify columns as numerical or categorical.
    """

    numerical_columns = dataframe.select_dtypes(
        include=["number"]
    ).columns.tolist()

    categorical_columns = dataframe.select_dtypes(
        include=["object", "category", "bool"]
    ).columns.tolist()

    return {
        "numerical_columns": numerical_columns,
        "categorical_columns": categorical_columns,
    }

def get_column_information(dataframe: pd.DataFrame) -> list:
    """
    Generate information for every column.
    """

    column_information = []

    for column in dataframe.columns:

        dtype = str(dataframe[column].dtype)

        if pd.api.types.is_numeric_dtype(dataframe[column]):
            column_type = "numerical"

        elif (
            pd.api.types.is_object_dtype(dataframe[column])
            or pd.api.types.is_categorical_dtype(dataframe[column])
            or pd.api.types.is_bool_dtype(dataframe[column])
        ):
            column_type = "categorical"

        else:
            column_type = "other"

        column_information.append(
            {
                "column": column,
                "data_type": dtype,
                "classification": column_type,
            }
        )

    return column_information


def get_missing_value_summary(
    dataframe: pd.DataFrame
) -> list:
    """
    Calculate missing-value count and percentage
    for every column.
    """

    total_rows = len(dataframe)

    missing_summary = []

    for column in dataframe.columns:

        missing_count = int(
            dataframe[column].isna().sum()
        )

        if total_rows > 0:
            missing_percentage = (
                missing_count / total_rows
            ) * 100
        else:
            missing_percentage = 0.0

        missing_summary.append(
            {
                "column": column,
                "missing_count": missing_count,
                "missing_percentage": round(
                    missing_percentage,
                    2
                ),
            }
        )

    return missing_summary

def get_numerical_statistics(
    dataframe: pd.DataFrame
) -> dict:
    """
    Calculate descriptive statistics for numerical columns.
    """

    numerical_data = dataframe.select_dtypes(
        include=["number"]
    )

    if numerical_data.empty:
        return {}

    statistics = numerical_data.describe().round(2)

    return statistics.to_dict()


def get_categorical_frequencies(
    dataframe: pd.DataFrame
) -> dict:
    """
    Calculate value frequencies for categorical columns.
    """

    categorical_columns = dataframe.select_dtypes(
        include=["object", "category", "bool"]
    ).columns

    frequencies = {}

    for column in categorical_columns:

        value_counts = (
            dataframe[column]
            .value_counts(dropna=False)
            .head(20)
        )

        frequencies[column] = {
            str(value): int(count)
            for value, count in value_counts.items()
        }

    return frequencies


def generate_profile(
    dataframe: pd.DataFrame
) -> dict:
    """
    Generate the complete dataset profile.
    """

    profile = {}

    profile["basic"] = get_basic_profile(
        dataframe
    )

    profile["column_types"] = get_column_types(
        dataframe
    )

    profile["columns"] = get_column_information(
        dataframe
    )

    profile["missing_values"] = (
        get_missing_value_summary(dataframe)
    )

    profile["numerical_statistics"] = (
        get_numerical_statistics(dataframe)
    )

    profile["categorical_frequencies"] = (
        get_categorical_frequencies(dataframe)
    )

    return profile