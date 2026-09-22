import pandas as pd

from backend.services.generation_service import (
    _apply_column_actions,
)


def test_remove_and_keep_actions():
    synthetic_data = pd.DataFrame(
        {
            "product_id": ["PROD0001", "PROD0002"],
            "product_name": [
                "Industrial Sensor",
                "Power Supply",
            ],
            "category": [
                "Electronics",
                "Mechanical",
            ],
            "standard_cost": [1000.50, 2000.75],
        }
    )

    configurations = [
        {
            "column_name": "product_id",
            "action": "remove",
        },
        {
            "column_name": "product_name",
            "action": "keep",
        },
        {
            "column_name": "category",
            "action": "keep",
        },
        {
            "column_name": "standard_cost",
            "action": "keep",
        },
    ]

    result = _apply_column_actions(
        synthetic_dataframe=synthetic_data,
        configurations=configurations,
    )

    # Removed column must not exist
    assert "product_id" not in result.columns

    # Keep columns must remain
    assert "product_name" in result.columns
    assert "category" in result.columns
    assert "standard_cost" in result.columns

    # Row count must remain unchanged
    assert len(result) == len(synthetic_data)

    print("\nRemove/Keep enforcement: PASSED")



def test_mask_and_generalize_actions():
    synthetic_data = pd.DataFrame(
        {
            "customer_name": [
                "Palak",
                "Rahul",
            ],
            "category": [
                "Electronics",
                "Mechanical",
            ],
            "standard_cost": [
                1234.567,
                9876.543,
            ],
        }
    )

    configurations = [
        {
            "column_name": "customer_name",
            "action": "mask",
        },
        {
            "column_name": "category",
            "action": "generalize",
        },
        {
            "column_name": "standard_cost",
            "action": "generalize",
        },
    ]

    result = _apply_column_actions(
        synthetic_dataframe=synthetic_data,
        configurations=configurations,
    )

    # Masked values should not equal original values
    assert result["customer_name"].iloc[0] != "Palak"
    assert result["customer_name"].iloc[1] != "Rahul"

    # Mask should preserve the length
    assert len(result["customer_name"].iloc[0]) == len("Palak")
    assert len(result["customer_name"].iloc[1]) == len("Rahul")

    # Text generalization should reduce the value
    assert result["category"].iloc[0] == "Ele"
    assert result["category"].iloc[1] == "Mec"

    # Numeric generalization should round values
    assert result["standard_cost"].iloc[0] == 1235
    assert result["standard_cost"].iloc[1] == 9877

    # Row count must remain unchanged
    assert len(result) == len(synthetic_data)

    print("\nMask/Generalize enforcement: PASSED")

def test_new_id_action():
    synthetic_data = pd.DataFrame(
        {
            "product_id": [
                "PROD0001",
                "PROD0002",
                "PROD0003",
                "PROD0004",
            ],
            "product_name": [
                "Sensor",
                "Controller",
                "Bearing",
                "Circuit Breaker",
            ],
        }
    )

    configurations = [
        {
            "column_name": "product_id",
            "action": "new_id",
        },
        {
            "column_name": "product_name",
            "action": "keep",
        },
    ]

    result = _apply_column_actions(
        synthetic_dataframe=synthetic_data,
        configurations=configurations,
    )

    generated_ids = result["product_id"].tolist()

    # Correct number of IDs
    assert len(generated_ids) == 4

    # All generated IDs must be unique
    assert len(generated_ids) == len(set(generated_ids))

    # Original IDs must not be preserved
    assert "PROD0001" not in generated_ids
    assert "PROD0002" not in generated_ids
    assert "PROD0003" not in generated_ids
    assert "PROD0004" not in generated_ids

    # Other columns remain
    assert "product_name" in result.columns

    # Row count remains unchanged
    assert len(result) == len(synthetic_data)

    print("\nNew ID enforcement: PASSED")

def test_derived_column_action():
    synthetic_data = pd.DataFrame(
        {
            "quantity_a": [100, 200, 300],
            "quantity_b": [20, 50, 75],
            "total": [0, 0, 0],
        }
    )

    configurations = [
        {
            "column_name": "quantity_a",
            "action": "keep",
        },
        {
            "column_name": "quantity_b",
            "action": "keep",
        },
        {
            "column_name": "total",
            "action": "derived",
            "rule": {
                "operation": "add",
                "operands": ["quantity_a", "quantity_b"],
            },
        },
    ]

    result = _apply_column_actions(
        synthetic_dataframe=synthetic_data,
        configurations=configurations,
    )

    assert "total" in result.columns

    assert result["total"].tolist() == [
        120,
        250,
        375,
    ]

    assert len(result) == len(synthetic_data)

    print("\nDerived column enforcement: PASSED")

if __name__ == "__main__":
    test_remove_and_keep_actions()
    test_mask_and_generalize_actions()
    test_new_id_action()
    test_derived_column_action()

def test_generation_api_enforces_column_actions():
    """
    End-to-end verification that the generation API applies
    the configured column actions.
    """

    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)

    response = client.post(
        "/generation",
        json={
            "dataset_id": 143,
            "model_name": "gaussian_copula",
            "parameters": {
                "random_state": 42
            }
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["status"] == "success"

    data = result["data"]

    # Configuration must be present in API response
    assert "configurations" in data

    configurations = data["configurations"]

    actions = {
        config["column_name"]: config["action"]
        for config in configurations
    }

    # Expected configured actions
    assert actions["inventory_id"] == "new_id"
    assert actions["supplier_id"] == "new_id"
    assert actions["product_id"] == "new_id"

    assert actions["warehouse"] == "keep"
    assert actions["quantity_on_hand"] == "keep"
    assert actions["quantity_reserved"] == "keep"
    assert actions["quantity_available"] == "keep"
    assert actions["reorder_point"] == "keep"
    assert actions["inventory_status"] == "keep"

    generated_dataset = data["generated_dataset"]

    assert generated_dataset["row_count"] == 500
    assert generated_dataset["column_count"] == 9

    print("\nGeneration API column-action enforcement: PASSED")


def test_invalid_column_action_is_rejected():
    """
    Verify that an unsupported column action is not silently accepted.
    """

    from backend.services.generation_service import _apply_column_actions
    import pandas as pd

    synthetic_data = pd.DataFrame(
        {
            "product_id": ["P001", "P002"],
            "product_name": ["Sensor", "Controller"],
        }
    )

    invalid_configuration = [
        {
            "column_name": "product_id",
            "action": "invalid_action",
        }
    ]

    try:
        _apply_column_actions(
            synthetic_dataframe=synthetic_data,
            configurations=invalid_configuration,
        )
    except (ValueError, KeyError):
        print("\nInvalid column action correctly rejected: PASSED")
        return

    raise AssertionError(
        "Invalid column action was silently accepted."
    )