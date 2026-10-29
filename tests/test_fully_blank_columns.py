import numpy as np
import pandas as pd

from backend.services.missing_value_service import handle_missing_values


def test_fully_blank_numeric_column_becomes_unknown():
    df = pd.DataFrame({"amount": [np.nan, np.nan, np.nan], "region": ["North", "South", "North"]})
    result = handle_missing_values(df)
    assert result["amount"].tolist() == ["unknown", "unknown", "unknown"]
    assert len(result) == len(df)


def test_fully_blank_date_named_column_becomes_unknown():
    df = pd.DataFrame({"delivery_date": [None, None, None]})
    result = handle_missing_values(df)
    assert result["delivery_date"].tolist() == ["unknown"] * 3


def test_whitespace_only_column_becomes_unknown():
    df = pd.DataFrame({"notes": ["", "   ", None]})
    result = handle_missing_values(df)
    assert result["notes"].tolist() == ["unknown"] * 3


def test_partially_missing_column_keeps_normal_imputation():
    df = pd.DataFrame({"region": ["North", None, "North", "South"]})
    result = handle_missing_values(df)
    assert result["region"].isna().sum() == 0
    assert result["region"].iloc[1] == "North"
