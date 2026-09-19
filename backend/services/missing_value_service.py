import pandas as pd

from backend.services.outlier_service import (
    detect_outliers_iqr,
)


def handle_missing_values(dataframe: pd.DataFrame):
    dataframe = dataframe.copy()

    outlier_results = detect_outliers_iqr(dataframe)

    for column in dataframe.columns:

        if not dataframe[column].isna().any():
            continue

        # Numerical columns
        if pd.api.types.is_numeric_dtype(dataframe[column]):

            # Use median when the column contains outliers
            if outlier_results.get(column):
                fill_value = dataframe[column].median()
                strategy = "median"

            # Otherwise use mean
            else:
                fill_value = dataframe[column].mean()
                strategy = "mean"

        # Categorical / text columns
        else:
            fill_value = dataframe[column].mode().iloc[0]
            strategy = "mode"

        dataframe[column] = dataframe[column].fillna(fill_value)

    return dataframe