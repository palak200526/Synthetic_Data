from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from backend.repositories.relationship_repository import (
    get_dataset_relationships,
    get_relationships_for_dataset,
)

logger = logging.getLogger(__name__)


def validate_referential_integrity(
    generated_tables: dict,
    relationships: list,
) -> dict:
    """
    Backwards-compatible referential integrity validation
    used during multi-table generation.
    """
    results = []

    for relationship in relationships:
        parent_dataset_id = relationship["parent_dataset_id"]
        parent_column = relationship["parent_column"]

        child_dataset_id = relationship["child_dataset_id"]
        child_column = relationship["child_column"]

        parent_df = generated_tables[parent_dataset_id]["dataframe"]
        child_df = generated_tables[child_dataset_id]["dataframe"]

        parent_keys = set(parent_df[parent_column].dropna().tolist())
        child_keys = set(child_df[child_column].dropna().tolist())

        invalid_keys = child_keys - parent_keys

        results.append({
            "relationship_id": relationship.get("relationship_id"),
            "parent_dataset_id": parent_dataset_id,
            "child_dataset_id": child_dataset_id,
            "parent_column": parent_column,
            "child_column": child_column,
            "valid": len(invalid_keys) == 0,
            "invalid_key_count": len(invalid_keys),
            "invalid_keys": list(invalid_keys),
        })

    return {
        "valid": all(result["valid"] for result in results),
        "relationships": results,
    }


def evaluate_referential_integrity(
    dataset_id: int | None = None,
    group_id: int | None = None,
    relationships: list[dict] | None = None,
    tables: dict[int, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """
    US-027: Cross-Table Referential-Integrity Evaluation.

    Measures whether primary/foreign-key relationships between linked tables
    are preserved in the synthetic datasets.

    Calculates:
    - Primary/foreign-key relationship validity
    - Percentage of synthetic child records whose parent exists
    - Referential-integrity score
    - Cross-table consistency and preservation

    If no relationships exist:
    Returns status="not_applicable", reason="No cross-table relationships available"
    """
    rel_list = relationships

    # If relationships not provided, query from database
    if rel_list is None:
        if group_id is not None:
            try:
                rel_list = get_dataset_relationships(group_id)
            except Exception as e:
                logger.warning("Failed to get relationships for group %s: %s", group_id, e)
                rel_list = []
        elif dataset_id is not None:
            try:
                rel_list = get_relationships_for_dataset(dataset_id)
            except Exception as e:
                logger.warning("Failed to get relationships for dataset %s: %s", dataset_id, e)
                rel_list = []
        else:
            rel_list = []

    if not rel_list:
        return {
            "metric": "relationship_integrity",
            "status": "not_applicable",
            "reason": "No cross-table relationships available",
            "overall_score": None,
            "referential_integrity_score": None,
            "valid": None,
            "total_relationships": 0,
            "valid_relationships": 0,
            "relationships": [],
        }

    results = []
    scores = []

    for rel in rel_list:
        parent_id = rel["parent_dataset_id"]
        parent_col = rel["parent_column"]
        child_id = rel["child_dataset_id"]
        child_col = rel["child_column"]

        # If tables dictionary provided, look up dataframes
        if tables and parent_id in tables and child_id in tables:
            parent_df = tables[parent_id]
            child_df = tables[child_id]
        else:
            # Tables not available in context
            continue

        if parent_col not in parent_df.columns or child_col not in child_df.columns:
            results.append({
                "relationship_id": rel.get("relationship_id"),
                "parent_dataset_id": parent_id,
                "child_dataset_id": child_id,
                "parent_column": parent_col,
                "child_column": child_col,
                "valid": False,
                "reason": "Specified parent or child column missing in tables",
                "referential_integrity_score": 0.0,
            })
            scores.append(0.0)
            continue

        parent_keys = set(parent_df[parent_col].dropna().unique())
        child_values = child_df[child_col].dropna()
        total_child = len(child_values)

        if total_child == 0:
            pct_valid = 100.0
            invalid_count = 0
            invalid_sample = []
        else:
            is_valid_mask = child_values.isin(parent_keys)
            valid_count = int(is_valid_mask.sum())
            invalid_count = total_child - valid_count
            pct_valid = round((valid_count / total_child) * 100.0, 2)
            invalid_sample = child_values[~is_valid_mask].head(5).tolist()

        rel_valid = invalid_count == 0
        scores.append(pct_valid)

        results.append({
            "relationship_id": rel.get("relationship_id"),
            "parent_dataset_id": parent_id,
            "child_dataset_id": child_id,
            "parent_column": parent_col,
            "child_column": child_col,
            "relationship_type": rel.get("relationship_type", "foreign_key"),
            "valid": rel_valid,
            "total_synthetic_child_records": total_child,
            "valid_synthetic_child_records": total_child - invalid_count,
            "invalid_synthetic_child_records": invalid_count,
            "referential_integrity_score": pct_valid,
            "invalid_sample": invalid_sample,
        })

    if not results:
        return {
            "metric": "relationship_integrity",
            "status": "not_applicable",
            "reason": "Tables for defined relationships could not be loaded",
            "overall_score": None,
            "referential_integrity_score": None,
            "valid": None,
            "total_relationships": len(rel_list),
            "valid_relationships": 0,
            "relationships": [],
        }

    overall_score = round(float(np.mean(scores)), 2)
    valid_count = sum(1 for r in results if r.get("valid"))

    return {
        "metric": "relationship_integrity",
        "status": "evaluated",
        "overall_score": overall_score,
        "referential_integrity_score": overall_score,
        "valid": all(r.get("valid") for r in results),
        "total_relationships": len(results),
        "valid_relationships": valid_count,
        "relationships": results,
    }