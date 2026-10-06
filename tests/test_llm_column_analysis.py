import pandas as pd

from backend.services.column_profile_service import (
    build_dataset_column_profiles,
)

from backend.services.llm_column_analysis_service import (
    analyze_columns,
)


# Change this to your CSV path
CSV_PATH = "data/sample_supply_chain/products.csv"


def main():

    # ---------------------------------------
    # 1. Load dataset
    # ---------------------------------------

    df = pd.read_csv(CSV_PATH)

    print("\nDataset shape:")
    print(df.shape)

    # ---------------------------------------
    # 2. Build column profiles
    # ---------------------------------------

    profiles = build_dataset_column_profiles(df)

    print("\nColumn profiles generated:")
    print(f"Number of columns: {len(profiles)}")

    # ---------------------------------------
    # 3. Send profiles to LLM
    # ---------------------------------------

    result = analyze_columns(profiles)

    # ---------------------------------------
    # 4. Display LLM decisions
    # ---------------------------------------

    print("\n========== LLM ANALYSIS ==========\n")

    for column in result.columns:

        print(f"Column: {column.column_name}")
        print(f"Identifier: {column.is_identifier}")
        print(f"Action: {column.action}")
        print(f"Reason: {column.reason}")

        print("-" * 50)


if __name__ == "__main__":
    main()