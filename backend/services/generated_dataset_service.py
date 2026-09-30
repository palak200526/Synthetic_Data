from pathlib import Path
from datetime import datetime

import pandas as pd

from backend.repositories.dataset_repository import (
    get_dataset_filename,
)

from backend.repositories.configuration_repository import (
    get_configurations,
)

from backend.services.dataset_loader import load_dataset

from backend.repositories.dataset_repository import (
    get_dataset_file_path,
)

GENERATED_DIRECTORY = Path("data/generated")
UPLOAD_DIRECTORY = Path("data/uploads")


def save_generated_dataset(
    dataframe: pd.DataFrame,
    dataset_id: int,
    model_name: str,
):
    # Create date-wise folder
    today = datetime.now().strftime("%Y-%m-%d")

    date_directory = (
        GENERATED_DIRECTORY / today
    )

    date_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Save using dataset ID and model name
    output_filename = (
        f"synthetic_dataset_{dataset_id}_{model_name}.csv"
    )

    output_path = (
        date_directory / output_filename
    )

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


def prepare_dataset_for_generation(
    dataset_id: int,
):

    # 1. Get original dataset filename
    filename = get_dataset_filename(
        dataset_id
    )

    # 2. Load original dataset
    file_path = get_dataset_file_path(dataset_id)

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