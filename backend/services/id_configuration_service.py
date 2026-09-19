from pathlib import Path

from backend.repositories.configuration_repository import (
    get_identifier_configurations,
)
from backend.repositories.dataset_repository import (
    get_dataset_filename,
)
from backend.services.dataset_loader import load_dataset
from backend.services.id_generation_service import (
    generate_new_ids,
)
from backend.services.generated_dataset_service import (
    save_generated_dataset,
)

UPLOAD_DIRECTORY = Path("data/uploads")


def generate_ids_for_dataset(dataset_id: int):
    # 1. Get selected identifier columns
    configurations = get_identifier_configurations(dataset_id)

    if not configurations:
        raise ValueError(
            f"No identifier columns configured for dataset {dataset_id}."
        )

    # 2. Get dataset filename
    filename = get_dataset_filename(dataset_id)

    # 3. Load dataset
    file_path = UPLOAD_DIRECTORY / filename
    dataframe = load_dataset(str(file_path))

    # 4. Generate new IDs for each selected identifier column
    for configuration in configurations:
        column_name = configuration["column_name"]

        dataframe = generate_new_ids(
            dataframe,
            column_name,
        )

    # 5. Save generated dataset
    output = save_generated_dataset(
        dataframe,
        dataset_id,
    )

    return {
        "dataframe": dataframe,
        "output": output,
    }