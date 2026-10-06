import pandas as pd

from backend.services.statistical_evaluation_service import (
    evaluate_statistical_similarity,
)


real_data = pd.DataFrame(
    {
        "cost": [100, 110, 120, 130, 140],
        "category": [
            "A",
            "A",
            "B",
            "B",
            "C",
        ],
    }
)

synthetic_data = pd.DataFrame(
    {
        "cost": [102, 108, 121, 128, 139],
        "category": [
            "A",
            "A",
            "B",
            "B",
            "C",
        ],
    }
)


result = evaluate_statistical_similarity(
    real_dataframe=real_data,
    synthetic_dataframe=synthetic_data,
)

print("\nSTATISTICAL EVALUATION")
print("======================")

print(
    "Overall score:",
    result["overall_score"],
)

print(
    "Evaluated columns:",
    result["evaluated_columns"],
)

for column, details in result["columns"].items():
    print(
        f"{column}: "
        f"type={details['column_type']}, "
        f"score={details['score']}"
    )
    