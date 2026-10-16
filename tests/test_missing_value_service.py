import pandas as pd

from backend.services.missing_value_service import handle_missing_values


def test_fills_numeric_text_and_date_missing_values():
    frame = pd.DataFrame({
        "quantity": [2.0, None, 8.0],
        "status": ["Delivered", "", "Pending"],
        "delivery_date": ["2026-01-02", None, "2026-01-08"],
    })

    result = handle_missing_values(frame)

    assert not result.isna().any().any()
    assert result["quantity"].iloc[1] == 5.0
    assert result["status"].iloc[1] in {"Delivered", "Pending"}
    assert result["delivery_date"].iloc[1] == "2026-01-05"


def test_all_null_columns_get_deterministic_fallbacks():
    frame = pd.DataFrame({
        "amount": [None, None],
        "description": [None, None],
        "delivery_date": [None, None],
    })

    result = handle_missing_values(frame)

    assert not result.isna().any().any()
    assert result["amount"].tolist() == [0, 0]
    assert result["description"].tolist() == ["Unknown", "Unknown"]
    assert result["delivery_date"].tolist() == ["2000-01-01", "2000-01-01"]


def test_generated_data_uses_reference_fill_values():
    reference = pd.DataFrame({"status": ["Delivered", "Delivered", "Pending"]})
    generated = pd.DataFrame({"status": ["", None, "Pending"]})

    result = handle_missing_values(generated, reference_dataframe=reference)

    assert result["status"].tolist() == ["Delivered", "Delivered", "Pending"]
    assert not result.isna().any().any()
