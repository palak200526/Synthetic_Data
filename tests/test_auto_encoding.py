import pandas as pd
from backend.services.data_preparation_service import prepare_data_for_model


def test_low_cardinality_uses_onehot_and_reports_comparison():
    df = pd.DataFrame({"status": ["open", "closed", "open", "pending"] * 5})
    result = prepare_data_for_model(df)
    assert "status" not in result["dataframe"].columns
    assert result["encoding_metadata"]["status"]["selected_method"] == "onehot"
    assert "candidate_scores" in result["encoding_metadata"]["status"]


def test_identifier_like_column_is_not_encoded():
    df = pd.DataFrame({"customer_id": [f"C{i}" for i in range(30)]})
    result = prepare_data_for_model(df)
    assert "customer_id" in result["dataframe"].columns
    assert result["encoding_metadata"]["customer_id"]["selected_method"] == "skip_identifier"


def test_medium_cardinality_selects_compact_method_automatically():
    df = pd.DataFrame({"category": [f"category_{i % 40}" for i in range(400)]})
    result = prepare_data_for_model(df)
    metadata = result["encoding_metadata"]["category"]
    assert metadata["selected_method"] in {"binary", "frequency", "count", "hashing", "onehot"}
    assert metadata["candidate_scores"]
    assert "category" not in result["dataframe"].columns or metadata["selected_method"] in {"frequency", "count"}
