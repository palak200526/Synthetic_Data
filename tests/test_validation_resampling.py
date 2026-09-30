import pandas as pd

from backend.services.validation_resampling_service import (
    generate_valid_rows,
)


def test_reject_and_resample():

    calls = {
        "count": 0
    }

    def generate_data(count):

        calls["count"] += 1

        if calls["count"] == 1:
            return pd.DataFrame({
                "unit_cost": [-10, -20, 30, 40]
            })

        return pd.DataFrame({
            "unit_cost": [50, 60, 70, 80]
        })

    rules = [
        {
            "rule_id": 1,
            "rule_name": "Non Negative Unit Cost",
            "rule_type": "non_negative",
            "rule_definition": {
                "column": "unit_cost"
            },
            "is_active": True,
        }
    ]

    result = generate_valid_rows(
        generate_function=generate_data,
        target_row_count=4,
        rules=rules,
        max_attempts=5,
    )

    dataframe = result["dataframe"]

    assert len(dataframe) == 4

    assert (
        dataframe["unit_cost"] >= 0
    ).all()

    assert result["total_rejected_rows"] == 2

    assert result["total_generated_rows"] == 6

    assert result["final_validation"]["valid"] is True

    assert calls["count"] == 2