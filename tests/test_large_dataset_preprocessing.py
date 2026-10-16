import time
import numpy as np
import pandas as pd
import pytest

from backend.services.preprocessing_service import preprocess_dataset
from backend.services.data_preparation_service import prepare_data_for_model


def test_large_dataset_preprocessing_no_memory_explosion():
    """
    Test preprocessing on a 50,000 row dataset with high-cardinality IDs
    (mimicking order_items.csv with 40,025 rows).
    Verifies that no O(N^2) memory explosion occurs and execution completes quickly.
    """
    n_rows = 50_000
    
    # 50,000 unique IDs
    df = pd.DataFrame({
        "order_id": [f"ORD_{i:06d}" for i in range(n_rows)],
        "product_id": [f"PROD_{i % 500:04d}" for i in range(n_rows)],
        "category": np.random.choice(["Electronics", "Clothing", "Home"], size=n_rows),
        "price": np.random.uniform(10.0, 500.0, size=n_rows),
        "quantity": np.random.randint(1, 20, size=n_rows),
        "total_cost": np.random.uniform(20.0, 1000.0, size=n_rows),
        "order_date": "2026-01-01",
        "delivery_date": "2026-01-08",
    })

    start_time = time.time()
    result = preprocess_dataset(df)
    elapsed = time.time() - start_time

    assert elapsed < 5.0, f"Preprocessing took too long: {elapsed:.2f}s"
    assert result["validation"]["is_valid"] is True
    
    processed = result["dataframe"]
    assert len(processed) == n_rows
    # Low-cardinality category should be dummy encoded
    assert "category_Electronics" in processed.columns
    assert "category_Clothing" in processed.columns
    assert "category_Home" in processed.columns
    
    # High-cardinality order_id and product_id must NOT be dummy-encoded
    assert "order_id" in processed.columns or "order_id" not in result["categorical_columns"]
    # Total column count should be reasonable (~10-15 columns), NOT 50,000+ columns
    assert len(processed.columns) < 20, f"Unexpectedly large number of columns: {len(processed.columns)}"
    
    # Supply chain features should be generated
    assert "lead_time" in processed.columns
    assert "cost_per_unit" in processed.columns


def test_prepare_data_for_model_skips_high_cardinality():
    """
    Test that prepare_data_for_model skips columns with > max_categories.
    """
    df = pd.DataFrame({
        "low_cat": ["A", "B", "C"] * 100,
        "high_cat": [f"val_{i}" for i in range(300)],
        "number": list(range(300)),
    })

    result = prepare_data_for_model(df, max_categories=10)
    processed = result["dataframe"]
    
    # low_cat had 3 categories <= 10 -> encoded
    assert "low_cat_A" in processed.columns
    assert "low_cat" not in processed.columns
    
    # high_cat had 300 categories > 10 -> preserved, NOT encoded
    assert "high_cat" in processed.columns
    assert "high_cat" not in result["categorical_columns"]


def test_half_million_rows_preprocessing_performance():
    """
    Test that 500,000 rows can be preprocessed swiftly without memory exhaustion.
    """
    n_rows = 500_000
    df = pd.DataFrame({
        "id": range(1, n_rows + 1),
        "status": np.random.choice(["Pending", "Shipped", "Delivered"], size=n_rows),
        "amount": np.random.uniform(5.0, 200.0, size=n_rows),
        "qty": np.random.randint(1, 10, size=n_rows),
    })

    start_time = time.time()
    result = preprocess_dataset(df)
    elapsed = time.time() - start_time

    assert elapsed < 10.0, f"500k rows took {elapsed:.2f}s"
    assert result["validation"]["is_valid"] is True
    assert len(result["dataframe"]) == n_rows
    assert "status_Delivered" in result["dataframe"].columns
