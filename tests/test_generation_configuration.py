from backend.services.generation_configuration_service import (
    get_generation_configuration,
    group_columns_by_action,
)


DATASET_ID = 309


def main():

    print("\n========== GENERATION CONFIGURATION ==========\n")

    configurations = get_generation_configuration(
        DATASET_ID
    )

    print("Configurations loaded:")

    for config in configurations:
        print(
            f"{config['column_name']} "
            f"-> {config['action']}"
        )

    print("\n========== GROUPED ACTIONS ==========\n")

    grouped = group_columns_by_action(
        configurations
    )

    for action, columns in grouped.items():

        print(f"{action.upper()}:")

        if columns:
            for column in columns:
                print(f"  - {column}")
        else:
            print("  None")

        print()


if __name__ == "__main__":
    main()