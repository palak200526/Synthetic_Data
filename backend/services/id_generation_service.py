import uuid
import pandas as pd


def generate_new_ids(dataframe: pd.DataFrame, column_name: str):
    if column_name not in dataframe.columns:
        raise ValueError(
            f"Column '{column_name}' does not exist in the dataset."
        )

    generated_ids = [
        str(uuid.uuid4())
        for _ in range(len(dataframe))
    ]

    # Validate uniqueness
    if len(generated_ids) != len(set(generated_ids)):
        raise ValueError(
            f"Generated IDs for column '{column_name}' are not unique."
        )

    dataframe = dataframe.copy()

    # Replace original identifier values
    dataframe[column_name] = generated_ids

    return dataframe