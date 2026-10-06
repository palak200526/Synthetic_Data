import pandas as pd
import re


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
        include=["object", "string", "category", "bool"]
    ).columns.tolist()

    return {
        "numerical_columns": numerical_columns,
        "categorical_columns": categorical_columns,
    }


def detect_patterns(series: pd.Series) -> list[str]:
    """
    Detect common patterns in string columns.
    """

    patterns = []

    values = (
        series
        .dropna()
        .astype(str)
        .head(100)
    )

    pattern_checks = {
        "email": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",

        "phone": r"^\+?[\d\s().-]{7,}$",

        "uuid": (
            r"^[0-9a-fA-F]{8}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{12}$"
        ),
    }

    for pattern_name, regex in pattern_checks.items():

        if not values.empty:

            matches = values.str.match(
                regex,
                na=False
            )

            if matches.mean() >= 0.8:
                patterns.append(pattern_name)

    return patterns


def get_column_information(dataframe: pd.DataFrame) -> list:
    """
    Generate detailed information for every column.

    This information is used by the LLM to determine:
    - whether a column is an identifier
    - which action should be applied during generation
    """

    column_information = []

    for column in dataframe.columns:

        series = dataframe[column]

        dtype = str(series.dtype)

        # ---------------------------------------------------------
        # Column classification
        # ---------------------------------------------------------

        if pd.api.types.is_numeric_dtype(series):

            column_type = "numerical"

        elif (
            pd.api.types.is_object_dtype(series)
            or pd.api.types.is_string_dtype(series)
            or isinstance(
                series.dtype,
                pd.CategoricalDtype
            )
            or pd.api.types.is_bool_dtype(series)
        ):

            column_type = "categorical"

        else:

            column_type = "other"

        # ---------------------------------------------------------
        # Basic column information
        # ---------------------------------------------------------

        row_count = len(series)

        unique_count = int(
            series.nunique(dropna=True)
        )

        unique_ratio = (
            float(unique_count / row_count)
            if row_count > 0
            else 0.0
        )

        null_count = int(
            series.isna().sum()
        )

        null_ratio = float(
            series.isna().mean()
        )

        # ---------------------------------------------------------
        # Create base profile
        # ---------------------------------------------------------

        column_profile = {

            "column_name": column,

            "dtype": dtype,

            "classification": column_type,

            "row_count": row_count,

            "unique_count": unique_count,

            "unique_ratio": unique_ratio,

            "null_count": null_count,

            "null_ratio": null_ratio,

            # Actual examples from the dataset
            "sample_values": (
                series
                .dropna()
                .astype(str)
                .head(10)
                .tolist()
            ),
        }

        # ---------------------------------------------------------
        # String information
        # ---------------------------------------------------------

        if (
            pd.api.types.is_object_dtype(series)
            or pd.api.types.is_string_dtype(series)
            or isinstance(
                series.dtype,
                pd.CategoricalDtype
            )
        ):

            values = (
                series
                .dropna()
                .astype(str)
            )

            if not values.empty:

                lengths = values.str.len()

                column_profile["string_length"] = {

                    "min": int(
                        lengths.min()
                    ),

                    "max": int(
                        lengths.max()
                    ),

                    "average": float(
                        lengths.mean()
                    ),
                }

                column_profile["patterns"] = (
                    detect_patterns(series)
                )

        # ---------------------------------------------------------
        # Numerical information
        # ---------------------------------------------------------

        if pd.api.types.is_numeric_dtype(series):

            column_profile["statistics"] = {

                "min": float(
                    series.min()
                ),

                "max": float(
                    series.max()
                ),

                "mean": float(
                    series.mean()
                ),

                "median": float(
                    series.median()
                ),

                "std": float(
                    series.std()
                ),
            }

        # ---------------------------------------------------------
        # Categorical information
        # ---------------------------------------------------------

        if (
            not pd.api.types.is_numeric_dtype(series)
            and unique_count <= 50
        ):

            value_counts = (
                series
                .value_counts(
                    dropna=True
                )
                .head(10)
            )

            column_profile["top_values"] = {

                str(value): int(count)

                for value, count
                in value_counts.items()
            }

        # ---------------------------------------------------------
        # Add completed profile
        # ---------------------------------------------------------

        column_information.append(
            column_profile
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
    Calculate descriptive statistics
    for numerical columns.
    """

    numerical_data = dataframe.select_dtypes(
        include=["number"]
    )

    if numerical_data.empty:
        return {}

    statistics = (
        numerical_data
        .describe()
        .round(2)
    )

    return statistics.to_dict()


def get_categorical_frequencies(
    dataframe: pd.DataFrame
) -> dict:
    """
    Calculate value frequencies
    for categorical columns.
    """

    categorical_columns = dataframe.select_dtypes(
        include=[
            "object",
            "string",
            "category",
            "bool"
        ]
    ).columns

    frequencies = {}

    for column in categorical_columns:

        value_counts = (
            dataframe[column]
            .value_counts(
                dropna=False
            )
            .head(20)
        )

        frequencies[column] = {

            str(value): int(count)

            for value, count
            in value_counts.items()
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
        get_missing_value_summary(
            dataframe
        )
    )

    profile["numerical_statistics"] = (
        get_numerical_statistics(
            dataframe
        )
    )

    profile["categorical_frequencies"] = (
        get_categorical_frequencies(
            dataframe
        )
    )

    return profile