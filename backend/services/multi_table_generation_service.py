from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.generation.generator_factory import get_generator
from backend.repositories.dataset_repository import (
    get_dataset_file_path,
    get_dataset_filename,
)
from backend.repositories.generation_repository import (
    create_generation_run,
    save_generated_result,
    update_generation_run_status,
)
from backend.services.dataset_loader import load_dataset
from backend.services.generated_dataset_service import (
    save_generated_dataset,
)
from backend.services.relationship_analysis_service import (
    identify_related_tables,
)

logger = logging.getLogger(__name__)

UPLOAD_DIRECTORY = Path("data/uploads")


def load_group_datasets(group_id: int):
    """
    Load all datasets belonging to a dataset group.
    """
    relationship_data = identify_related_tables(group_id)

    datasets = {}

    for dataset_id in relationship_data["dataset_ids"]:
        filename = get_dataset_filename(dataset_id)

        try:
            file_path = get_dataset_file_path(dataset_id)
            dataframe = load_dataset(str(file_path))
        except Exception as e:
            logger.warning(
                "Could not resolve file path for dataset %s: %s. Using default upload directory.",
                dataset_id,
                e,
            )
            dataframe = load_dataset(str(UPLOAD_DIRECTORY / filename))

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

    # Filter out LLM or incompatible params for tabular generator
    tabular_params = {
        k: v
        for k, v in (parameters or {}).items()
        if not k.startswith("llm_") and k not in {"ollama_url", "prompt_template"}
    }

    generated_tables = {}

    # --------------------------------------------------
    # 1. Generate each dataset
    # --------------------------------------------------

    for dataset_id, dataset_info in datasets.items():
        dataframe = dataset_info["dataframe"]

        generator = get_generator(
            model_name,
            **tabular_params,
        )

        generator.fit(dataframe)

        synthetic_dataframe = generator.generate(
            len(dataframe)
        )

        generated_tables[dataset_id] = {
            "dataset_id": dataset_id,
            "source_filename": dataset_info["filename"],
            "dataframe": synthetic_dataframe.copy(),
        }

    # --------------------------------------------------
    # 2. Preserve parent-child relationships
    # --------------------------------------------------

    for relationship in relationships:
        parent_dataset_id = relationship["parent_dataset_id"]
        parent_column = relationship["parent_column"]

        child_dataset_id = relationship["child_dataset_id"]
        child_column = relationship["child_column"]

        if parent_dataset_id not in generated_tables or child_dataset_id not in generated_tables:
            continue

        parent_dataframe = generated_tables[parent_dataset_id]["dataframe"]
        child_dataframe = generated_tables[child_dataset_id]["dataframe"]

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

        original_parent_dataframe = datasets[parent_dataset_id]["dataframe"]
        original_child_dataframe = datasets[child_dataset_id]["dataframe"]

        # Ensure parent table has valid, non-empty primary keys.
        # If the original parent column had unique values (e.g. PK), ensure the
        # synthetic parent column also maintains unique, valid keys.
        orig_parent_keys = (
            original_parent_dataframe[parent_column]
            .dropna()
            .unique()
            .tolist()
        )
        is_orig_parent_unique = original_parent_dataframe[parent_column].is_unique
        current_parent_keys = (
            parent_dataframe[parent_column]
            .dropna()
            .unique()
            .tolist()
        )

        if is_orig_parent_unique or len(current_parent_keys) < len(parent_dataframe):
            if len(parent_dataframe) <= len(original_parent_dataframe):
                parent_dataframe[parent_column] = (
                    original_parent_dataframe[parent_column]
                    .iloc[: len(parent_dataframe)]
                    .values
                )
            else:
                orig_vals = list(original_parent_dataframe[parent_column].values)
                extra_needed = len(parent_dataframe) - len(orig_vals)
                if orig_vals and isinstance(orig_vals[0], (int, np.integer)):
                    max_val = max(orig_vals)
                    extended = orig_vals + list(
                        range(max_val + 1, max_val + 1 + extra_needed)
                    )
                else:
                    extended = orig_vals + [
                        f"PK_{i}"
                        for i in range(len(orig_vals) + 1, len(orig_vals) + 1 + extra_needed)
                    ]
                parent_dataframe[parent_column] = extended[: len(parent_dataframe)]

        final_parent_keys = (
            parent_dataframe[parent_column]
            .dropna()
            .unique()
            .tolist()
        )
        if not final_parent_keys:
            final_parent_keys = orig_parent_keys
            parent_dataframe[parent_column] = [
                final_parent_keys[i % len(final_parent_keys)]
                for i in range(len(parent_dataframe))
            ]

        # Map original parent keys -> newly generated parent keys
        key_mapping = {
            orig_k: final_parent_keys[i % len(final_parent_keys)]
            for i, orig_k in enumerate(orig_parent_keys)
        }

        # Build synthetic child foreign keys
        n_child = len(child_dataframe)
        orig_child_fks = (
            original_child_dataframe[child_column].tolist()
            if child_column in original_child_dataframe.columns
            else []
        )

        if len(orig_child_fks) == n_child:
            synthetic_child_keys = [
                key_mapping.get(val, final_parent_keys[0])
                for val in orig_child_fks
            ]
        else:
            rel_counts = (
                original_child_dataframe[child_column].value_counts().to_dict()
                if child_column in original_child_dataframe.columns
                else {}
            )
            weights = [rel_counts.get(k, 1) for k in orig_parent_keys] if orig_parent_keys else [1]
            total_w = sum(weights) or 1
            probs = [w / total_w for w in weights]
            mapped_parent_keys = [
                key_mapping.get(k, final_parent_keys[0]) for k in orig_parent_keys
            ] or final_parent_keys
            synthetic_child_keys = np.random.choice(
                mapped_parent_keys,
                size=n_child,
                p=probs,
            ).tolist()

        child_dataframe[child_column] = synthetic_child_keys

        generated_tables[parent_dataset_id]["dataframe"] = parent_dataframe
        generated_tables[child_dataset_id]["dataframe"] = child_dataframe

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

        run_id = None
        result_id = None
        try:
            run_id = create_generation_run(
                dataset_id=dataset_id,
                model_name=f"{model_name}_group_{group_id}",
            )
            result_id = save_generated_result(
                run_id=run_id,
                file_name=saved["file_name"],
                file_path=saved["file_path"],
                row_count=saved["row_count"],
                column_count=saved["column_count"],
            )
            update_generation_run_status(run_id, "completed")
        except Exception as e:
            logger.warning(
                "Could not register generation run in DB for dataset %s: %s",
                dataset_id,
                e,
            )

        saved_tables[dataset_id] = {
            **table_info,
            "file_name": saved["file_name"],
            "file_path": saved["file_path"],
            "row_count": saved["row_count"],
            "column_count": saved["column_count"],
            "run_id": run_id,
            "result_id": result_id,
        }

    return {
        "group_id": group_id,
        "model_name": model_name,
        "tables": saved_tables,
        "relationships": relationships,
    }