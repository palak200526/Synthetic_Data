import pandas as pd
import pytest

from backend.services.referential_integrity_service import (
    evaluate_referential_integrity,
)


def test_us027_valid_foreign_key_relationship():
    # Parent table: customers
    customers_df = pd.DataFrame({
        "customer_id": ["C1", "C2", "C3", "C4", "C5"],
        "name": ["Alice", "Bob", "Charlie", "David", "Eve"],
    })

    # Child table: orders (100% of foreign keys exist in parent)
    orders_df = pd.DataFrame({
        "order_id": ["O1", "O2", "O3", "O4", "O5", "O6"],
        "customer_id": ["C1", "C2", "C1", "C3", "C4", "C5"],
        "amount": [100, 200, 150, 300, 250, 400],
    })

    relationships = [
        {
            "relationship_id": 1,
            "parent_dataset_id": 10,
            "child_dataset_id": 20,
            "parent_column": "customer_id",
            "child_column": "customer_id",
            "relationship_type": "foreign_key",
        }
    ]

    tables = {
        10: customers_df,
        20: orders_df,
    }

    result = evaluate_referential_integrity(
        relationships=relationships,
        tables=tables,
    )

    assert result["metric"] == "relationship_integrity"
    assert result["status"] == "evaluated"
    assert result["valid"] is True
    assert result["overall_score"] == 100.0
    assert result["referential_integrity_score"] == 100.0

    rel_metric = result["relationships"][0]
    assert rel_metric["valid"] is True
    assert rel_metric["total_synthetic_child_records"] == 6
    assert rel_metric["valid_synthetic_child_records"] == 6
    assert rel_metric["invalid_synthetic_child_records"] == 0
    assert rel_metric["referential_integrity_score"] == 100.0


def test_us027_partially_invalid_foreign_key_relationship():
    customers_df = pd.DataFrame({
        "customer_id": ["C1", "C2", "C3"],
    })

    # Child table: orders with 2 invalid keys out of 5 (60% valid)
    orders_df = pd.DataFrame({
        "order_id": ["O1", "O2", "O3", "O4", "O5"],
        "customer_id": ["C1", "C2", "C-GHOST-1", "C3", "C-GHOST-2"],
    })

    relationships = [
        {
            "relationship_id": 2,
            "parent_dataset_id": 100,
            "child_dataset_id": 200,
            "parent_column": "customer_id",
            "child_column": "customer_id",
        }
    ]

    tables = {
        100: customers_df,
        200: orders_df,
    }

    result = evaluate_referential_integrity(
        relationships=relationships,
        tables=tables,
    )

    assert result["status"] == "evaluated"
    assert result["valid"] is False
    assert result["overall_score"] == 60.0

    rel_metric = result["relationships"][0]
    assert rel_metric["valid"] is False
    assert rel_metric["total_synthetic_child_records"] == 5
    assert rel_metric["valid_synthetic_child_records"] == 3
    assert rel_metric["invalid_synthetic_child_records"] == 2
    assert rel_metric["referential_integrity_score"] == 60.0
    assert "C-GHOST-1" in rel_metric["invalid_sample"]


def test_us027_no_relationships_returns_not_applicable():
    result = evaluate_referential_integrity(relationships=[])

    assert result["metric"] == "relationship_integrity"
    assert result["status"] == "not_applicable"
    assert result["overall_score"] is None
    assert "No cross-table" in result["reason"]
