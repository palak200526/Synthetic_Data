from pathlib import Path

import pandas as pd


GENERATED_DIRECTORY = Path("data/generated")

from backend.repositories.dataset_repository import (
    get_dataset_filename,
)
from backend.repositories.configuration_repository import (
    get_configurations,
)
from backend.services.dataset_loader import load_dataset


UPLOAD_DIRECTORY = Path("data/uploads")

def save_generated_dataset(
    dataframe: pd.DataFrame,
    dataset_id: int,
    model_name: str,
):
    GENERATED_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_filename = (
        f"synthetic_dataset_{dataset_id}_{model_name}.csv"
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

def prepare_dataset_for_generation(dataset_id: int):

    # 1. Get original dataset filename
    filename = get_dataset_filename(dataset_id)

    # 2. Load original dataset
    file_path = UPLOAD_DIRECTORY / filename

    dataframe = load_dataset(
        str(file_path)
    )

    # 3. Get saved column configurations
    configurations = get_configurations(
        dataset_id
    )

    if not configurations:
        raise ValueError(
            f"No column configurations found "
            f"for dataset {dataset_id}."
        )

    return {
        "filename": filename,
        "dataframe": dataframe,
        "configurations": configurations,
    }