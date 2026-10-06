import pandas as pd

from backend.services.llm_configuration_service import (
    build_column_configurations,
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

    configurations = (
        build_column_configurations(
            dataframe,
            dataset_id=999
        )
    )

    print(
        "\n========== COLUMN CONFIGURATION OBJECTS =========="
    )

    for configuration in configurations:

        print("\nColumn:", configuration.column_name)
        print("Dataset ID:", configuration.dataset_id)
        print("Type:", configuration.column_type)
        print("Sensitive:", configuration.is_sensitive)
        print("Identifier:", configuration.is_identifier)
        print("Action:", configuration.action)
        print("Rule:", configuration.rule)


if __name__ == "__main__":
    main()