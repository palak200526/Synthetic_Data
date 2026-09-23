from pathlib import Path

from scipy import datasets

from backend.services.relationship_analysis_service import (
    identify_related_tables,
)
from backend.services.dataset_loader import load_dataset
from backend.repositories.dataset_repository import get_dataset_filename
from backend.services.generated_dataset_service import (
    save_generated_dataset,
)
from backend.generation import get_generator

UPLOAD_DIRECTORY = Path("data/uploads")


def load_group_datasets(group_id: int):
    """
    Load all datasets belonging to a dataset group.
    """

    relationship_data = identify_related_tables(group_id)

    datasets = {}

    for dataset_id in relationship_data["dataset_ids"]:
        filename = get_dataset_filename(dataset_id)

        dataframe = load_dataset(
            str(UPLOAD_DIRECTORY / filename)
        )

        datasets[dataset_id] = {
            "dataset_id": dataset_id,
            "filename": filename,
            "dataframe": dataframe,
        }

    return {
        "group_id": group_id,
        "datasets": datasets,
        "relationships": relationship_data["relationships"],
    }

def generate_linked_tables(
    group_id: int,
    model_name: str = "gaussian_copula",
    parameters: dict | None = None,
):
    """
    Generate synthetic datasets for a dataset group while
    preserving configured parent-child relationships.
    """

    group_data = load_group_datasets(group_id)

    datasets = group_data["datasets"]
    relationships = group_data["relationships"]

    if not relationships:
        raise ValueError(
            f"No relationships found for dataset group {group_id}."
        )

    generated_tables = {}

    # --------------------------------------------------
    # 1. Generate each dataset
    # --------------------------------------------------

    for dataset_id, dataset_info in datasets.items():

        dataframe = dataset_info["dataframe"]

        generator = get_generator(
            model_name,
            **(parameters or {})
        )

        generator.fit(dataframe)

        synthetic_dataframe = generator.generate(
            len(dataframe)
        )

        generated_tables[dataset_id] = {
            "dataset_id": dataset_id,
            "source_filename": dataset_info["filename"],
            "dataframe": synthetic_dataframe,
        }

    # --------------------------------------------------
    # 2. Preserve parent-child relationships
    # --------------------------------------------------

    for relationship in relationships:

        parent_dataset_id = relationship["parent_dataset_id"]
        parent_column = relationship["parent_column"]

        child_dataset_id = relationship["child_dataset_id"]
        child_column = relationship["child_column"]

        parent_dataframe = generated_tables[
            parent_dataset_id
        ]["dataframe"]

        child_dataframe = generated_tables[
            child_dataset_id
        ]["dataframe"]

        if parent_column not in parent_dataframe.columns:
            raise ValueError(
                f"Parent column '{parent_column}' "
                f"not found in dataset {parent_dataset_id}."
            )

        if child_column not in child_dataframe.columns:
            raise ValueError(
                f"Child column '{child_column}' "
                f"not found in dataset {child_dataset_id}."
            )

        parent_keys = (
            parent_dataframe[parent_column]
            .dropna()
            .unique()
            .tolist()
        )

        if not parent_keys:
            raise ValueError(
                f"No parent keys found for "
                f"{parent_dataset_id}.{parent_column}."
            )

        # Temporary FK mapping.
        # Every child FK must come from the generated
        # parent key set.
        
        # Get the original parent-child relationship distribution
        original_parent_dataframe = datasets[
            parent_dataset_id
        ]["dataframe"]

        original_child_dataframe = datasets[
            child_dataset_id
        ]["dataframe"]

        relationship_counts = (
            original_child_dataframe[child_column]
            .value_counts()
        )

            # Map original parent keys -> newly generated parent keys
        original_parent_keys = (
            original_parent_dataframe[parent_column]
            .dropna()
            .unique()
            .tolist()
        )

        if len(original_parent_keys) != len(parent_keys):
            raise ValueError(
                f"Parent key count changed for relationship "
                f"{parent_dataset_id}.{parent_column}."
            )

        key_mapping = dict(
            zip(
                original_parent_keys,
                parent_keys
            )
        )

            # Build synthetic child FK values
        synthetic_child_keys = []

        for original_key, count in relationship_counts.items():

            if original_key not in key_mapping:
                continue

            synthetic_key = key_mapping[original_key]

            synthetic_child_keys.extend(
                [synthetic_key] * count
            )

            # Ensure generated child row count matches
        if len(synthetic_child_keys) != len(child_dataframe):
            raise ValueError(
                "Synthetic child FK mapping does not match "
                "the generated child row count."
            )

            # Assign relationship-preserving foreign keys
        child_dataframe[child_column] = synthetic_child_keys

        generated_tables[
            child_dataset_id
        ]["dataframe"] = child_dataframe

    # --------------------------------------------------
    # 3. Save generated tables
    # --------------------------------------------------

    saved_tables = {}

    for dataset_id, table_info in generated_tables.items():

        saved = save_generated_dataset(
            dataframe=table_info["dataframe"],
            dataset_id=dataset_id,
            model_name=f"{model_name}_group_{group_id}",
        )

        saved_tables[dataset_id] = {
            **table_info,
            "file_name": saved["file_name"],
            "file_path": saved["file_path"],
            "row_count": saved["row_count"],
            "column_count": saved["column_count"],
        }
        
    return {
    "group_id": group_id,
    "model_name": model_name,
    "tables": saved_tables,
    "relationships": relationships,
} 