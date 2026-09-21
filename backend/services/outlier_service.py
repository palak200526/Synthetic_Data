import pandas as pd


def detect_outliers_iqr(dataframe: pd.DataFrame):

    results = {}

    numerical_columns = dataframe.select_dtypes(
        include="number"
    ).columns

    for column in numerical_columns:

        series = dataframe[column].dropna()

        if series.empty:
            results[column] = []
            continue

        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)

        iqr = q3 - q1

        lower_bound = q1 - (1.5 * iqr)
        upper_bound = q3 + (1.5 * iqr)

        outlier_indices = dataframe.index[
            (dataframe[column] < lower_bound)
            | (dataframe[column] > upper_bound)
        ].tolist()

        results[column] = outlier_indices

    return results


def detect_outliers_zscore(dataframe: pd.DataFrame):

    results = {}

    numerical_columns = dataframe.select_dtypes(
        include="number"
    ).columns

    for column in numerical_columns:

        series = dataframe[column].dropna()

        if series.empty:
            results[column] = []
            continue

        mean = series.mean()
        std = series.std()

        if std == 0:
            results[column] = []
            continue

        z_scores = (
            (dataframe[column] - mean) / std
        )

        outlier_indices = dataframe.index[
            z_scores.abs() > 3
        ].tolist()

        results[column] = outlier_indices

    return results