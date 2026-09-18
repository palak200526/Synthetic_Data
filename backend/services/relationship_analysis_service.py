import pandas as pd
from backend.repositories.relationship_repository import (
    save_relationship_analysis,
    get_relationship_analysis,
)


def analyze_relationships(dataframe: pd.DataFrame):
    if dataframe.empty:
        raise ValueError("Dataset cannot be empty.")

    numerical_dataframe = dataframe.select_dtypes(
        include="number"
    )

    if numerical_dataframe.empty:
        raise ValueError(
            "Dataset does not contain numerical columns."
        )

    correlation_matrix = numerical_dataframe.corr()
    covariance_matrix = numerical_dataframe.cov()

    return {
        "numerical_columns": numerical_dataframe.columns.tolist(),
        "correlation_matrix": correlation_matrix,
        "covariance_matrix": covariance_matrix,
    }

