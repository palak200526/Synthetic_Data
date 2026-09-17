import pandas as pd

from backend.services.id_generation_service import generate_new_ids


def test_generated_ids_are_unique():
    dataframe = pd.DataFrame({
        "Invoice ID": ["INV001", "INV002", "INV003", "INV004"],
        "Sales": [100, 200, 300, 400],
    })

    result = generate_new_ids(
        dataframe,
        "Invoice ID",
    )

    generated_ids = result["Invoice ID"].tolist()

    assert len(generated_ids) == 4
    assert len(generated_ids) == len(set(generated_ids))

def test_original_ids_are_not_preserved():
    dataframe = pd.DataFrame({
        "Invoice ID": ["INV001", "INV002", "INV003"],
    })

    result = generate_new_ids(
        dataframe,
        "Invoice ID",
    )

    generated_ids = result["Invoice ID"].tolist()

    assert "INV001" not in generated_ids
    assert "INV002" not in generated_ids
    assert "INV003" not in generated_ids

import pytest


def test_invalid_column_raises_error():
    dataframe = pd.DataFrame({
        "Invoice ID": ["INV001", "INV002"],
    })

    with pytest.raises(ValueError):
        generate_new_ids(
            dataframe,
            "customer_id",
        )

def test_empty_dataframe():
    dataframe = pd.DataFrame({
        "Invoice ID": [],
        "Sales": [],
    })

    result = generate_new_ids(
        dataframe,
        "Invoice ID",
    )

    assert result.empty
    assert "Invoice ID" in result.columns

def test_single_row_dataset():
    dataframe = pd.DataFrame({
        "Invoice ID": ["INV001"],
    })

    result = generate_new_ids(
        dataframe,
        "Invoice ID",
    )

    assert len(result) == 1
    assert result["Invoice ID"].iloc[0] != "INV001"
    assert len(set(result["Invoice ID"])) == 1

def test_duplicate_original_ids_generate_unique_ids():
    dataframe = pd.DataFrame({
        "Invoice ID": [
            "INV001",
            "INV001",
            "INV002",
            "INV002",
        ],
    })

    result = generate_new_ids(
        dataframe,
        "Invoice ID",
    )

    generated_ids = result["Invoice ID"].tolist()

    assert len(generated_ids) == 4
    assert len(set(generated_ids)) == 4

def test_original_dataframe_is_not_modified():
    dataframe = pd.DataFrame({
        "Invoice ID": ["INV001", "INV002"],
    })

    original_ids = dataframe["Invoice ID"].tolist()

    generate_new_ids(
        dataframe,
        "Invoice ID",
    )

    assert dataframe["Invoice ID"].tolist() == original_ids

def test_multiple_identifier_columns():
    dataframe = pd.DataFrame({
        "Invoice ID": ["INV001", "INV002", "INV003"],
        "Customer ID": ["C001", "C002", "C003"],
        "Sales": [100, 200, 300],
    })

    result = generate_new_ids(
        dataframe,
        "Invoice ID",
    )

    result = generate_new_ids(
        result,
        "Customer ID",
    )

    invoice_ids = result["Invoice ID"].tolist()
    customer_ids = result["Customer ID"].tolist()

    assert len(set(invoice_ids)) == 3
    assert len(set(customer_ids)) == 3

