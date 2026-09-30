import pandas as pd

from backend.services.llm_configuration_service import (
    save_llm_configurations,
)


DATASET_PATH = (
    "data/sample_supply_chain/products.csv"
)


def main():

    dataframe = pd.read_csv(
        DATASET_PATH
    )

    print("\nDataset shape:")
    print(dataframe.shape)

    dataset_id = 309

    print(
        "\n========== SAVING LLM CONFIGURATIONS =========="
    )

    results = save_llm_configurations(
        dataframe,
        dataset_id
    )

    for result in results:

        print(
            "\nSaved:"
        )

        print(
            "Configuration ID:",
            result["configuration_id"]
        )

        print(
            "Dataset ID:",
            result["dataset_id"]
        )

        print(
            "Column:",
            result["column_name"]
        )


if __name__ == "__main__":
    main()