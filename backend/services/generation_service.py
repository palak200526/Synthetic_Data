import pandas as pd

from backend.services.generated_dataset_service import (
    prepare_dataset_for_generation,
    save_generated_dataset,
)

from backend.generation.generator_factory import (
    get_generator
)

from backend.services.business_rule_detector import (
    detect_arithmetic_relationships,
    apply_business_rules,
)

from backend.repositories.generation_repository import (
    create_generation_run,
    save_model_configuration,
    save_generated_result,
    update_generation_run_status,
)

from backend.repositories.validation_rules_repository import (
    get_validation_rules,
)

from backend.services.validation_resampling_service import (
    generate_valid_rows,
)

from backend.repositories.dataset_repository import (
    get_dataset_user_id,
)


SUPPORTED_MODELS = {
    "gaussian_copula",
    "ctgan",
    "tvae",
}


# ==========================================================
# COLUMN ACTION HELPERS
# ==========================================================

def _get_columns_by_action(
    configurations: list,
    action: str,
) -> list[str]:
    """
    Return column names configured with a specific action.
    """

    return [
        config["column_name"]
        for config in configurations
        if config["action"] == action
    ]


def _generate_unique_ids(
    result: pd.DataFrame,
    column_name: str,
) -> pd.DataFrame:
    """
    Generate new unique identifiers for a column.

    Requirements:
    - IDs must be unique.
    - IDs must not match any original/generated ID
      already present in the column.
    - Number of IDs must equal number of rows.
    """

    if column_name not in result.columns:
        return result

    # --------------------------------------------------
    # Preserve existing values before replacing them
    # --------------------------------------------------

    existing_values = set(
        result[column_name]
        .dropna()
        .astype(str)
        .tolist()
    )

    generated_ids = []

    index = 1

    while len(generated_ids) < len(result):

        new_id = (
            f"{column_name}_synthetic_{index:06d}"
        )

        if new_id not in existing_values:
            generated_ids.append(new_id)

        index += 1

    result[column_name] = generated_ids

    return result


# ==========================================================
# APPLY COLUMN ACTIONS
# ==========================================================

def _apply_column_actions(
    synthetic_dataframe: pd.DataFrame,
    configurations: list,
) -> pd.DataFrame:
    """
    Apply configured column actions after synthetic generation.

    Supported actions:
    - keep
    - remove
    - generalize
    - new_id
    - derived
    """

    result = synthetic_dataframe.copy()

    # ==================================================
    # VALIDATE CONFIGURATIONS
    # ==================================================

    supported_actions = {
        "keep",
        "remove",
        "generalize",
        "new_id",
        "derived",
    }

    for config in configurations:

        action = config.get("action")
        column_name = config.get("column_name")

        if action not in supported_actions:
            raise ValueError(
                f"Unsupported column action "
                f"'{action}' for column "
                f"'{column_name}'"
            )

    # ==================================================
    # REMOVE
    # ==================================================

    remove_columns = _get_columns_by_action(
        configurations,
        "remove",
    )

    if remove_columns:

        result = result.drop(
            columns=remove_columns,
            errors="ignore",
        )


    # ==================================================
    # GENERALIZE
    # ==================================================

    generalize_columns = _get_columns_by_action(
        configurations,
        "generalize",
    )

    for column in generalize_columns:

        if column not in result.columns:
            continue

        # Numeric generalization
        if pd.api.types.is_numeric_dtype(
            result[column]
        ):

            result[column] = (
                result[column]
                .round(0)
            )

        # String/text generalization
        else:

            result[column] = (
                result[column]
                .astype(str)
                .str[:3]
            )

    # ==================================================
    # NEW ID
    # ==================================================

    new_id_columns = _get_columns_by_action(
        configurations,
        "new_id",
    )

    for column in new_id_columns:

        if column not in result.columns:
            continue

        result = _generate_unique_ids(
            result=result,
            column_name=column,
        )

    # ==================================================
    # DERIVED
    # ==================================================

    derived_configurations = [
        config
        for config in configurations
        if config["action"] == "derived"
    ]

    for config in derived_configurations:

        column_name = config["column_name"]

        rule = config.get("rule")

        if not rule:
            continue

        operation = rule.get(
            "operation"
        )

        operands = rule.get(
            "operands",
            [],
        )

        if len(operands) < 2:
            continue

        left = operands[0]
        right = operands[1]

        if (
            left not in result.columns
            or right not in result.columns
        ):
            continue

        # --------------------------------------------------
        # ADD
        # --------------------------------------------------

        if operation == "add":

            result[column_name] = (
                result[left]
                + result[right]
            )

        # --------------------------------------------------
        # SUBTRACT
        # --------------------------------------------------

        elif operation == "subtract":

            result[column_name] = (
                result[left]
                - result[right]
            )

        # --------------------------------------------------
        # MULTIPLY
        # --------------------------------------------------

        elif operation == "multiply":

            result[column_name] = (
                result[left]
                * result[right]
            )

        # --------------------------------------------------
        # DIVIDE
        # --------------------------------------------------

        elif operation == "divide":

            result[column_name] = 0.0

            non_zero = (
                result[right] != 0
            )

            result.loc[
                non_zero,
                column_name,
            ] = (
                result.loc[
                    non_zero,
                    left,
                ]
                /
                result.loc[
                    non_zero,
                    right,
                ]
            )

        else:

            raise ValueError(
                f"Unsupported derived "
                f"operation '{operation}' "
                f"for column '{column_name}'"
            )

    return result


# ==========================================================
# PREPARE DATAFRAME FOR GENERATION
# ==========================================================

def _prepare_generation_dataframe(
    dataframe: pd.DataFrame,
    configurations: list,
) -> pd.DataFrame:
    """
    Prepare dataframe before model training.

    Columns configured as 'remove' are excluded
    from model training.
    """

    remove_columns = _get_columns_by_action(
        configurations,
        "remove",
    )

    generation_dataframe = (
        dataframe
        .drop(
            columns=remove_columns,
            errors="ignore",
        )
        .copy()
    )

    if generation_dataframe.empty:

        raise ValueError(
            "No columns available for "
            "synthetic generation."
        )

    return generation_dataframe


# ==========================================================
# GENERATE USING SELECTED MODEL
# ==========================================================

def _generate_with_model(
    model_name: str,
    dataframe: pd.DataFrame,
    configurations: list,
    parameters: dict,
    num_rows: int,
) -> pd.DataFrame:
    """
    Train the selected generator and generate
    synthetic records.

    Identifier columns configured as new_id are
    passed to the generator so that generators
    can treat them separately.
    """

    # --------------------------------------------------
    # Prepare dataframe
    # --------------------------------------------------

    generation_dataframe = (
        _prepare_generation_dataframe(
            dataframe=dataframe,
            configurations=configurations,
        )
    )

    # --------------------------------------------------
    # Get identifier columns
    # --------------------------------------------------

    identifier_columns = (
        _get_columns_by_action(
            configurations,
            "new_id",
        )
    )

    identifier_columns = [
        column
        for column in identifier_columns
        if column in generation_dataframe.columns
    ]

    # --------------------------------------------------
    # Generator parameters
    # --------------------------------------------------

    generator_parameters = dict(
        parameters
    )

    # Identifier handling is controlled by
    # column configuration.
    generator_parameters.pop(
        "identifier_columns",
        None,
    )

    # --------------------------------------------------
    # Create generator
    # --------------------------------------------------

    generator = get_generator(
        model_name,
        **generator_parameters,
    )

    # --------------------------------------------------
    # Train
    # --------------------------------------------------

    generator.fit(
        generation_dataframe,
        identifier_columns=identifier_columns,
    )

    # --------------------------------------------------
    # Generate
    # --------------------------------------------------

    synthetic_dataframe = (
        generator.generate(
            num_rows=num_rows
        )
    )

    return synthetic_dataframe


# ==========================================================
# MAIN GENERATION SERVICE
# ==========================================================

def generate_synthetic_dataset(
    dataset_id,
    model_name,
    user_id,
    parameters: dict | None = None,
):
    """
    Main synthetic data generation service.

    Flow:

    1. Validate dataset ownership
    2. Validate generation model
    3. Create generation run
    4. Load dataset and configurations
    5. Load validation rules
    6. Detect business rules
    7. Train selected generator
    8. Generate synthetic data
    9. Apply business rules
    10. Apply configured column actions
    11. Validate/resample
    12. Save generated dataset
    13. Save generation result
    14. Update generation run
    15. Return API response
    """

    # ==================================================
    # 1. DATASET OWNERSHIP
    # ==================================================

    dataset_user_id = get_dataset_user_id(
        dataset_id
    )

    if dataset_user_id != user_id:

        raise PermissionError(
            "You do not have permission to "
            "generate data for this dataset."
        )

    # ==================================================
    # 2. VALIDATE MODEL
    # ==================================================

    if not model_name:

        raise ValueError(
            "Model name is required."
        )

    model_name = (
        model_name
        .strip()
        .lower()
    )

    if model_name not in SUPPORTED_MODELS:

        raise ValueError(
            f"Unsupported model: {model_name}. "
            f"Supported models: "
            f"{', '.join(sorted(SUPPORTED_MODELS))}."
        )

    parameters = parameters or {}

    # ==================================================
    # 3. CREATE GENERATION RUN
    # ==================================================

    run_id = create_generation_run(
        dataset_id=dataset_id,
        model_name=model_name,
    )

    save_model_configuration(
        run_id=run_id,
        model_name=model_name,
        parameters=parameters,
    )

    # ==================================================
    # 4. PREPARE DATASET
    # ==================================================

    preparation = (
        prepare_dataset_for_generation(
            dataset_id
        )
    )

    dataframe = preparation[
        "dataframe"
    ]

    filename = preparation[
        "filename"
    ]

    configurations = preparation[
        "configurations"
    ]

    # ==================================================
    # 5. VALIDATION RULES
    # ==================================================

    validation_rules = (
        get_validation_rules(
            dataset_id
        )
    )

    # ==================================================
    # 6. DETECT BUSINESS RULES
    # ==================================================

    business_rules = (
        detect_arithmetic_relationships(
            dataframe
        )
    )

    # ==================================================
    # 7. GENERATION FUNCTION
    # ==================================================

    def generate_rows(count):

        generated = _generate_with_model(
            model_name=model_name,
            dataframe=dataframe,
            configurations=configurations,
            parameters=parameters,
            num_rows=count,
        )

        # --------------------------------------------------
        # Apply business rules
        # --------------------------------------------------

        generated = apply_business_rules(
            generated,
            business_rules,
        )

        # --------------------------------------------------
        # Apply column actions
        # --------------------------------------------------

        generated = _apply_column_actions(
            synthetic_dataframe=generated,
            configurations=configurations,
        )

        return generated

    # ==================================================
    # 8. GENERATE + VALIDATE
    # ==================================================

    if validation_rules:

        validation_result = (
            generate_valid_rows(
                generate_function=generate_rows,
                target_row_count=len(dataframe),
                rules=validation_rules,
                max_attempts=10,
            )
        )

        synthetic_dataframe = (
            validation_result["dataframe"]
        )

    else:

        synthetic_dataframe = generate_rows(
            len(dataframe)
        )

        validation_result = {

            "dataframe":
                synthetic_dataframe,

            "target_row_count":
                len(dataframe),

            "total_generated_rows":
                len(synthetic_dataframe),

            "total_valid_rows":
                len(synthetic_dataframe),

            "total_rejected_rows":
                0,

            "attempts":
                1,

            "validation_history":
                [],

            "final_validation": {

                "valid":
                    True,

                "valid_row_count":
                    len(synthetic_dataframe),

                "invalid_row_count":
                    0,

                "invalid_rows":
                    [],

                "rules":
                    [],
            },
        }

    # ==================================================
    # 9. SAVE GENERATED DATASET
    # ==================================================

    generated_dataset = (
        save_generated_dataset(
            synthetic_dataframe,
            dataset_id,
            model_name,
        )
    )

    # ==================================================
    # 10. SAVE GENERATION RESULT
    # ==================================================

    result_id = save_generated_result(
        run_id=run_id,

        file_name=generated_dataset[
            "file_name"
        ],

        file_path=generated_dataset[
            "file_path"
        ],

        row_count=generated_dataset[
            "row_count"
        ],

        column_count=generated_dataset[
            "column_count"
        ],
    )

    # ==================================================
    # 11. UPDATE GENERATION RUN STATUS
    # ==================================================

    update_generation_run_status(
        run_id=run_id,
        status="completed",
    )

    # ==================================================
    # 12. API RESPONSE
    # ==================================================

    return {

        "status":
            "success",

        "message":
            "Synthetic dataset generated successfully.",

        "data": {

            "run_id":
                run_id,

            "result_id":
                result_id,

            "dataset_id":
                dataset_id,

            "model_name":
                model_name,

            "parameters":
                parameters,

            "source_filename":
                filename,

            "configurations":
                configurations,

            "generated_dataset":
                generated_dataset,

            "business_rules":
                business_rules,

            "validation": {

                "target_row_count":
                    validation_result[
                        "target_row_count"
                    ],

                "total_generated_rows":
                    validation_result[
                        "total_generated_rows"
                    ],

                "total_valid_rows":
                    validation_result[
                        "total_valid_rows"
                    ],

                "total_rejected_rows":
                    validation_result[
                        "total_rejected_rows"
                    ],

                "attempts":
                    validation_result[
                        "attempts"
                    ],

                "final_validation":
                    validation_result[
                        "final_validation"
                    ],
            },
        },
    }