from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any, Callable, Optional

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
from backend.services.id_pattern_service import generate_ids_like
from backend.services.multi_table_integrity_service import (
    analyze_table,
    apply_key_functions,
    postprocess_generated,
    prepare_training_frame,
    validate_linked_tables,
)
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
    job_id: str | None = None,
    resume: bool = False,
    progress_callback: Optional[Callable[[dict], None]] = None,
):
    """Generate related tables with durable per-table checkpoints for resume."""

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
        if not k.startswith("llm_") and not k.startswith("_multi_table_") and k not in {"ollama_url", "prompt_template"}
    }

    generated_tables = {}

    rng = np.random.default_rng((parameters or {}).get("random_state"))
    checkpoint_path = Path("data/checkpoints") / str(job_id) / "multi_table.pkl" if job_id else None
    if resume and checkpoint_path and checkpoint_path.exists():
        try:
            with checkpoint_path.open("rb") as handle:
                generated_tables = pickle.load(handle)
        except Exception as exc:
            logger.warning("Could not load multi-table checkpoint for %s: %s", job_id, exc)
            generated_tables = {}

    def save_multi_checkpoint():
        if not checkpoint_path:
            return None
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = checkpoint_path.with_suffix(".tmp")
        with temporary.open("wb") as handle:
            pickle.dump(generated_tables, handle, protocol=pickle.HIGHEST_PROTOCOL)
        temporary.replace(checkpoint_path)
        return str(checkpoint_path)

    def update_progress(done, message):
        if not progress_callback:
            return
        progress_callback({
            "stage": "multi_table_generation",
            "stage_label": "Multi-table generation",
            "message": message,
            "generated_rows": sum(len(v.get("dataframe", [])) for v in generated_tables.values()),
            "total_rows": sum(len(v["dataframe"]) for v in datasets.values()),
            "current_batch": done,
            "total_batches": len(datasets),
            "percent": int(done * 100 / max(len(datasets), 1)),
            "checkpoint_path": str(checkpoint_path) if checkpoint_path else None,
        })

    # Which columns take part in a relationship (per dataset)
    parent_key_columns: dict = {}
    foreign_key_columns: dict = {}
    for relationship in relationships:
        parent_key_columns.setdefault(
            relationship["parent_dataset_id"], set()
        ).add(relationship["parent_column"])
        foreign_key_columns.setdefault(
            relationship["child_dataset_id"], set()
        ).add(relationship["child_column"])

    profiles = {}

    # --------------------------------------------------
    # 1. Generate each dataset
    #    IDs, keys, derived columns and key-derived names are NOT
    #    modelled; they are rebuilt afterwards so they stay valid.
    # --------------------------------------------------

    for dataset_id, dataset_info in datasets.items():
        dataframe = dataset_info["dataframe"]
        profile = analyze_table(
            dataframe,
            parent_key_columns=parent_key_columns.get(dataset_id),
            foreign_key_columns=foreign_key_columns.get(dataset_id),
        )
        profiles[dataset_id] = profile

    for table_index, (dataset_id, dataset_info) in enumerate(datasets.items(), start=1):
        if dataset_id in generated_tables:
            update_progress(table_index, f"Restored checkpoint for {dataset_info['filename']}")
            continue
        dataframe = dataset_info["dataframe"]
        profile = profiles[dataset_id]
        training_dataframe = prepare_training_frame(dataframe, profile)

        generator = get_generator(
            model_name,
            **tabular_params,
        )

        generator.fit(training_dataframe)

        synthetic_dataframe = generator.generate(
            len(dataframe)
        )

        synthetic_dataframe = postprocess_generated(
            original=dataframe,
            synthetic=synthetic_dataframe,
            profile=profile,
            rng=rng,
        )

        generated_tables[dataset_id] = {
            "dataset_id": dataset_id,
            "source_filename": dataset_info["filename"],
            "dataframe": synthetic_dataframe.copy(),
        }
        saved_checkpoint = save_multi_checkpoint()
        update_progress(table_index, f"Generated {dataset_info['filename']} ({table_index}/{len(datasets)} tables)")

        if job_id:
            from backend.services.generation_checkpoint_service import check_job_control
            from backend.repositories.generation_job_repository import update_generation_job_progress
            control = check_job_control(job_id, idle_pause=True)
            update_generation_job_progress(
                job_id=job_id,
                generated_rows=sum(len(v.get("dataframe", [])) for v in generated_tables.values()),
                current_batch=table_index,
                total_batches=len(datasets),
                progress_percent=int(table_index * 100 / max(len(datasets), 1)),
                stage="multi_table_generation",
                stage_message=f"Checkpoint saved after {table_index}/{len(datasets)} tables",
                checkpoint_path=saved_checkpoint,
            )
            if control == "pause":
                return {"status": "paused", "group_id": group_id, "completed_tables": table_index, "total_tables": len(datasets)}
            if control == "cancel":
                return {"status": "cancelled", "group_id": group_id, "completed_tables": table_index, "total_tables": len(datasets)}

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
                    # Continue in the same format as the real keys
                    # (e.g. CUST-0042 -> CUST-0043) instead of "PK_n".
                    extended = orig_vals + generate_ids_like(
                        source=original_parent_dataframe[parent_column],
                        count=extra_needed,
                    )
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

        # Columns that are a function of the key (e.g. supplier_name for
        # SUP017 -> "Supplier 17") are rebuilt from the final keys.
        key_fn_columns = profiles[parent_dataset_id].key_function_columns.get(
            parent_column, []
        )
        if key_fn_columns:
            parent_dataframe = apply_key_functions(
                original=original_parent_dataframe,
                synthetic=parent_dataframe,
                key_column=parent_column,
                columns=key_fn_columns,
            )

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
    # 2b. Validate integrity of the generated tables
    # --------------------------------------------------

    integrity_report = validate_linked_tables(
        tables={k: v["dataframe"] for k, v in generated_tables.items()},
        originals={k: v["dataframe"] for k, v in datasets.items()},
        relationships=relationships,
        profiles=profiles,
    )

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
        "integrity_report": integrity_report,
    }