from pathlib import Path

import pandas as pd


GENERATED_DIRECTORY = Path("data/generated")


def save_generated_dataset(
    dataframe: pd.DataFrame,
    dataset_id: int,
):
    GENERATED_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_filename = (
        f"synthetic_dataset_{dataset_id}.csv"
    )

    output_path = GENERATED_DIRECTORY / output_filename

    dataframe.to_csv(
        output_path,
        index=False,
    )

    return {
        "file_name": output_filename,
        "file_path": str(output_path),
        "row_count": len(dataframe),
        "column_count": len(dataframe.columns),
    }