import pandas as pd

from backend.services.id_pattern_service import generate_ids_like


def generate_new_ids(dataframe: pd.DataFrame, column_name: str):
    if column_name not in dataframe.columns:
        raise ValueError(
            f"Column '{column_name}' does not exist in the dataset."
        )

    # New IDs follow the format of the original ones and never reuse them.
    generated_ids = generate_ids_like(
        source=dataframe[column_name],
        count=len(dataframe),
    )

    # Validate uniqueness
    if len(generated_ids) != len(set(generated_ids)):
        raise ValueError(
            f"Generated IDs for column '{column_name}' are not unique."
        )

    dataframe = dataframe.copy()

    # Replace original identifier values
    dataframe[column_name] = generated_ids

    return dataframe