import pandas as pd

from backend.services.outlier_service import (
    detect_outliers_iqr,
    detect_outliers_zscore,
)

from backend.services.missing_value_service import (
    handle_missing_values,
)

from backend.services.data_preparation_service import (
    prepare_data_for_model,
)

from backend.services.feature_engineering_service import (
    generate_supply_chain_features,
)

from backend.services.preprocessing_validator import (
    validate_preprocessing_output,
)

from backend.services.preprocessing_service import (
    preprocess_dataset,
)

def test_iqr_detects_outlier():

    dataframe = pd.DataFrame({
        "price": [
            10,
            11,
            12,
            13,
            14,
            100,
        ]
    })

    result = detect_outliers_iqr(dataframe)

    assert 5 in result["price"]


def test_iqr_no_outlier():

    dataframe = pd.DataFrame({
        "price": [
            10,
            11,
            12,
            13,
            14,
        ]
    })

    result = detect_outliers_iqr(dataframe)

    assert result["price"] == []


def test_zscore_detects_outlier():

    dataframe = pd.DataFrame({
        "price": [
            10,
            11,
            12,
            13,
            14,
            15,
            16,
            17,
            18,
            19,
            20,
            1000,
        ]
    })

    result = detect_outliers_zscore(dataframe)

    assert 11 in result["price"]

def test_zscore_no_outlier():

    dataframe = pd.DataFrame({
        "price": [
            10,
            11,
            12,
            13,
            14,
        ]
    })

    result = detect_outliers_zscore(dataframe)

    assert result["price"] == []


def test_outlier_detection_ignores_categorical_columns():

    dataframe = pd.DataFrame({
        "price": [10, 11, 12, 13, 100],
        "category": [
            "A",
            "B",
            "A",
            "B",
            "A",
        ],
    })

    iqr_result = detect_outliers_iqr(dataframe)
    zscore_result = detect_outliers_zscore(dataframe)

    assert "category" not in iqr_result
    assert "category" not in zscore_result

def test_missing_numerical_values_use_mean():

    dataframe = pd.DataFrame({
        "price": [10, 20, 30, None]
    })

    result = handle_missing_values(dataframe)

    assert result["price"].isna().sum() == 0
    assert result["price"].iloc[3] == 20


def test_missing_numerical_values_with_outliers_use_median():

    dataframe = pd.DataFrame({
        "price": [
            10,
            11,
            12,
            13,
            14,
            1000,
            None,
        ]
    })

    result = handle_missing_values(dataframe)

    assert result["price"].isna().sum() == 0
    assert result["price"].iloc[6] == 12.5


def test_missing_categorical_values_use_mode():

    dataframe = pd.DataFrame({
        "category": [
            "Electronics",
            "Electronics",
            "Furniture",
            None,
        ]
    })

    result = handle_missing_values(dataframe)

    assert result["category"].isna().sum() == 0
    assert result["category"].iloc[3] == "Electronics"


def test_columns_without_missing_values_remain_unchanged():

    dataframe = pd.DataFrame({
        "price": [10, 20, 30],
        "category": ["A", "B", "A"],
    })

    result = handle_missing_values(dataframe)

    pd.testing.assert_frame_equal(result, dataframe)

def test_identifies_numerical_and_categorical_columns():

    dataframe = pd.DataFrame({
        "price": [100, 200, 150],
        "quantity": [5, 3, 4],
        "category": [
            "Electronics",
            "Furniture",
            "Electronics",
        ],
    })

    result = prepare_data_for_model(dataframe)

    assert "price" in result["numerical_columns"]
    assert "quantity" in result["numerical_columns"]
    assert "category" in result["categorical_columns"]


def test_categorical_columns_are_encoded():

    dataframe = pd.DataFrame({
        "price": [100, 200, 150],
        "category": [
            "Electronics",
            "Furniture",
            "Electronics",
        ],
    })

    result = prepare_data_for_model(dataframe)

    prepared_data = result["dataframe"]

    assert "category" not in prepared_data.columns
    assert "category_Electronics" in prepared_data.columns
    assert "category_Furniture" in prepared_data.columns


def test_numerical_columns_are_preserved():

    dataframe = pd.DataFrame({
        "price": [100, 200, 150],
        "quantity": [5, 3, 4],
    })

    result = prepare_data_for_model(dataframe)

    prepared_data = result["dataframe"]

    assert "price" in prepared_data.columns
    assert "quantity" in prepared_data.columns

from backend.services.feature_engineering_service import (
    generate_supply_chain_features,
)

def test_generates_lead_time():

    dataframe = pd.DataFrame({
        "order_date": [
            "2026-01-01",
            "2026-01-10",
        ],
        "delivery_date": [
            "2026-01-06",
            "2026-01-15",
        ],
    })

    result = generate_supply_chain_features(dataframe)

    assert "lead_time" in result.columns
    assert result["lead_time"].tolist() == [5, 5]


def test_generates_cost_per_unit():

    dataframe = pd.DataFrame({
        "total_cost": [1000, 2500],
        "quantity": [100, 50],
    })

    result = generate_supply_chain_features(dataframe)

    assert "cost_per_unit" in result.columns
    assert result["cost_per_unit"].tolist() == [10.0, 50.0]


def test_generates_both_supply_chain_features():

    dataframe = pd.DataFrame({
        "order_date": ["2026-01-01"],
        "delivery_date": ["2026-01-11"],
        "total_cost": [5000],
        "quantity": [100],
    })

    result = generate_supply_chain_features(dataframe)

    assert "lead_time" in result.columns
    assert "cost_per_unit" in result.columns
    assert result["lead_time"].iloc[0] == 10
    assert result["cost_per_unit"].iloc[0] == 50.0


def test_does_not_generate_lead_time_without_dates():

    dataframe = pd.DataFrame({
        "total_cost": [1000],
        "quantity": [100],
    })

    result = generate_supply_chain_features(dataframe)

    assert "lead_time" not in result.columns


def test_does_not_generate_cost_per_unit_without_required_columns():

    dataframe = pd.DataFrame({
        "quantity": [100],
    })

    result = generate_supply_chain_features(dataframe)

    assert "cost_per_unit" not in result.columns


def test_zero_quantity_does_not_create_infinity():

    dataframe = pd.DataFrame({
        "total_cost": [1000],
        "quantity": [0],
    })

    result = generate_supply_chain_features(dataframe)

    assert pd.isna(result["cost_per_unit"].iloc[0])

def test_generates_lead_time():

    dataframe = pd.DataFrame({
        "order_date": [
            "2026-01-01",
            "2026-01-10",
        ],
        "delivery_date": [
            "2026-01-06",
            "2026-01-15",
        ],
    })

    result = generate_supply_chain_features(dataframe)

    assert "lead_time" in result.columns
    assert result["lead_time"].tolist() == [5, 5]


def test_generates_cost_per_unit():

    dataframe = pd.DataFrame({
        "total_cost": [1000, 2500],
        "quantity": [100, 50],
    })

    result = generate_supply_chain_features(dataframe)

    assert "cost_per_unit" in result.columns
    assert result["cost_per_unit"].tolist() == [10.0, 50.0]


def test_generates_both_supply_chain_features():

    dataframe = pd.DataFrame({
        "order_date": ["2026-01-01"],
        "delivery_date": ["2026-01-11"],
        "total_cost": [5000],
        "quantity": [100],
    })

    result = generate_supply_chain_features(dataframe)

    assert "lead_time" in result.columns
    assert "cost_per_unit" in result.columns
    assert result["lead_time"].iloc[0] == 10
    assert result["cost_per_unit"].iloc[0] == 50.0


def test_does_not_generate_lead_time_without_dates():

    dataframe = pd.DataFrame({
        "total_cost": [1000],
        "quantity": [100],
    })

    result = generate_supply_chain_features(dataframe)

    assert "lead_time" not in result.columns


def test_does_not_generate_cost_per_unit_without_required_columns():

    dataframe = pd.DataFrame({
        "quantity": [100],
    })

    result = generate_supply_chain_features(dataframe)

    assert "cost_per_unit" not in result.columns


def test_zero_quantity_does_not_create_infinity():

    dataframe = pd.DataFrame({
        "total_cost": [1000],
        "quantity": [0],
    })

    result = generate_supply_chain_features(dataframe)

    assert pd.isna(result["cost_per_unit"].iloc[0])

def test_valid_preprocessing_output():

    original = pd.DataFrame({
        "price": [100, 200, 300],
        "quantity": [5, 10, 15],
    })

    processed = pd.DataFrame({
        "price": [100, 200, 300],
        "quantity": [5, 10, 15],
    })

    result = validate_preprocessing_output(
        original,
        processed,
    )

    assert result["is_valid"] is True
    assert result["errors"] == []


def test_detects_remaining_missing_values():

    original = pd.DataFrame({
        "price": [100, 200, 300],
    })

    processed = pd.DataFrame({
        "price": [100, None, 300],
    })

    result = validate_preprocessing_output(
        original,
        processed,
    )

    assert result["is_valid"] is False
    assert "price" in result["errors"][0]


def test_detects_changed_row_count():

    original = pd.DataFrame({
        "price": [100, 200, 300],
    })

    processed = pd.DataFrame({
        "price": [100, 200],
    })

    result = validate_preprocessing_output(
        original,
        processed,
    )

    assert result["is_valid"] is False
    assert "Row count changed" in result["errors"][0]


def test_detects_infinite_values():

    original = pd.DataFrame({
        "price": [100, 200, 300],
    })

    processed = pd.DataFrame({
        "price": [100, float("inf"), 300],
    })

    result = validate_preprocessing_output(
        original,
        processed,
    )

    assert result["is_valid"] is False
    assert "infinite values" in result["errors"][0]


def test_detects_empty_output():

    original = pd.DataFrame({
        "price": [100, 200, 300],
    })

    processed = pd.DataFrame()

    result = validate_preprocessing_output(
        original,
        processed,
    )

    assert result["is_valid"] is False
    assert "empty" in result["errors"][0]

def test_preprocess_dataset():

    dataframe = pd.DataFrame({
        "price": [100, 200, None, 300],
        "quantity": [5, 10, 15, 20],
        "category": [
            "Electronics",
            "Furniture",
            "Electronics",
            "Furniture",
        ],
    })

    result = preprocess_dataset(dataframe)

    processed_data = result["dataframe"]

    assert not processed_data.empty
    assert len(processed_data) == len(dataframe)
    assert processed_data.isna().sum().sum() == 0

    assert "price" in processed_data.columns
    assert "quantity" in processed_data.columns

    assert "category_Electronics" in processed_data.columns
    assert "category_Furniture" in processed_data.columns

    assert result["validation"]["is_valid"] is True

def test_preprocess_supply_chain_dataset():

    dataframe = pd.DataFrame({
        "order_date": [
            "2026-01-01",
            "2026-01-05",
            "2026-01-10",
        ],
        "delivery_date": [
            "2026-01-06",
            "2026-01-12",
            "2026-01-15",
        ],
        "total_cost": [
            1000,
            2000,
            1500,
        ],
        "quantity": [
            100,
            200,
            150,
        ],
        "category": [
            "Electronics",
            "Furniture",
            "Electronics",
        ],
    })

    result = preprocess_dataset(dataframe)

    processed_data = result["dataframe"]

    assert "lead_time" in processed_data.columns
    assert "cost_per_unit" in processed_data.columns

    assert processed_data["lead_time"].tolist() == [5, 7, 5]
    assert processed_data["cost_per_unit"].tolist() == [
        10.0,
        10.0,
        10.0,
    ]

    assert result["validation"]["is_valid"] is True


