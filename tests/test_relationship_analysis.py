import pandas as pd
import pytest

from backend.services.relationship_analysis_service import (
    analyze_relationships,
)


def test_analyze_relationships():
    dataframe = pd.DataFrame({
        "price": [100, 200, 300, 400],
        "quantity": [10, 20, 30, 40],
        "category": [
            "A",
            "B",
            "A",
            "B",
        ],
    })

    result = analyze_relationships(dataframe)

    assert "price" in result["numerical_columns"]
    assert "quantity" in result["numerical_columns"]

    assert "category" not in result["numerical_columns"]

    assert "price" in result["correlation_matrix"].columns
    assert "quantity" in result["correlation_matrix"].columns

    assert "price" in result["covariance_matrix"].columns
    assert "quantity" in result["covariance_matrix"].columns


def test_relationship_analysis_ignores_categorical_columns():

    dataframe = pd.DataFrame({
        "price": [100, 200, 300],
        "category": [
            "Electronics",
            "Furniture",
            "Electronics",
        ],
    })

    result = analyze_relationships(dataframe)

    assert result["numerical_columns"] == ["price"]

    assert "category" not in result["correlation_matrix"].columns
    assert "category" not in result["covariance_matrix"].columns


def test_relationship_analysis_rejects_empty_dataset():

    dataframe = pd.DataFrame()

    with pytest.raises(ValueError):
        analyze_relationships(dataframe)


def test_relationship_analysis_requires_numerical_columns():

    dataframe = pd.DataFrame({
        "category": [
            "Electronics",
            "Furniture",
        ]
    })

    with pytest.raises(ValueError):
        analyze_relationships(dataframe)