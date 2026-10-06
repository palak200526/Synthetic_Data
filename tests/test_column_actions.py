import pandas as pd

from backend.services.column_action_service import (
    apply_column_actions,
)


def main():

    dataframe = pd.DataFrame({
        "product_id": ["P001", "P002", "P003"],
        "product_name": [
            "Laptop",
            "Phone",
            "Monitor",
        ],
        "standard_cost": [
            100.0,
            200.0,
            300.0,
        ],
    })

    grouped_actions = {
        "keep": [
            "product_name",
            "standard_cost",
        ],
        "remove": [],
        "new_id": [
            "product_id",
        ],
        "generalize": [],
        "derived": [],
    }

    configurations = [
        {
            "column_name": "product_id",
            "action": "new_id",
        },
        {
            "column_name": "product_name",
            "action": "keep",
        },
        {
            "column_name": "standard_cost",
            "action": "keep",
        },
    ]

    result = apply_column_actions(
        dataframe,
        grouped_actions,
        configurations,
    )

    print("\n========== ORIGINAL DATA ==========\n")
    print(dataframe)

    print("\n========== AFTER ACTIONS ==========\n")
    print(result)

    print("\n========== VALIDATION ==========\n")

    print(
        "Product IDs unique:",
        result["product_id"].is_unique,
    )

    print(
        "Original IDs preserved:",
        result["product_id"].isin(
            dataframe["product_id"]
        ).any(),
    )


if __name__ == "__main__":
    main()