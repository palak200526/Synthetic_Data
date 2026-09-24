import numpy as np
import pandas as pd
from scipy.stats import norm

from backend.services.generated_dataset_service import (
    prepare_dataset_for_generation,
    save_generated_dataset,
)

from backend.services.id_generation_service import generate_new_ids

from backend.generation.generator_factory import get_generator

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


SUPPORTED_MODELS = {
    "gaussian_copula",
    "ctgan",
    "tvae",
}


def _generate_gaussian_copula(
    dataframe: pd.DataFrame,
    configurations: list,
    random_state: int = 42,
    num_rows: int | None = None,
) -> pd.DataFrame:

    rng = np.random.default_rng(random_state)
    if num_rows is None:
        num_rows = len(dataframe)

    # 1. Determine columns based on configuration
    remove_columns = {
        config["column_name"]
        for config in configurations
        if config["action"] == "remove"
    }

    working_dataframe = dataframe.drop(
        columns=list(remove_columns),
        errors="ignore",
    ).copy()

    if working_dataframe.empty:
        raise ValueError(
            "No columns available for synthetic generation."
        )

    # 2. Separate numerical and categorical data
    numerical_columns = (
        working_dataframe
        .select_dtypes(include=np.number)
        .columns
        .tolist()
    )

    categorical_columns = [
        column
        for column in working_dataframe.columns
        if column not in numerical_columns
    ]

    synthetic_dataframe = pd.DataFrame(
        index=range(num_rows)
    )

    # 3. Generate numerical columns
    if numerical_columns:

        numerical_data = working_dataframe[
            numerical_columns
        ].copy()

        # Rank -> Uniform -> Gaussian transformation
        gaussian_data = pd.DataFrame(
            index=numerical_data.index
        )

        for column in numerical_columns:

            values = numerical_data[
                column
            ].to_numpy()

            ranks = pd.Series(values).rank(
                method="average"
            ).to_numpy()

            uniform_values = (
                ranks - 0.5
            ) / len(values)

            gaussian_values = norm.ppf(
                uniform_values
            )

            gaussian_data[column] = (
                gaussian_values
            )

        # Correlation structure
        correlation_matrix = (
            gaussian_data
            .corr()
            .fillna(0)
        )

        correlation_matrix = (
            correlation_matrix
            + np.eye(
                len(correlation_matrix)
            ) * 1e-6
        )

        # Make matrix positive definite
        eigenvalues, eigenvectors = (
            np.linalg.eigh(
                correlation_matrix
            )
        )

        eigenvalues = np.maximum(
            eigenvalues,
            1e-6,
        )

        correlation_matrix = (
            eigenvectors
            @ np.diag(eigenvalues)
            @ eigenvectors.T
        )

        # Generate correlated Gaussian samples
        generated_gaussian = (
            rng.multivariate_normal(
                mean=np.zeros(
                    len(numerical_columns)
                ),
                cov=correlation_matrix,
                size=num_rows,
            )
        )

        # Transform back to original distributions
        for index, column in enumerate(
            numerical_columns
        ):

            original_values = (
                numerical_data[column]
                .dropna()
                .to_numpy()
            )

            uniform_values = norm.cdf(
                generated_gaussian[:, index]
            )

            synthetic_values = np.quantile(
                original_values,
                uniform_values,
            )

            synthetic_dataframe[column] = (
                synthetic_values
            )

    # 4. Generate categorical columns
    for column in categorical_columns:

        value_counts = (
            working_dataframe[column]
            .value_counts(
                normalize=True
            )
        )

        categories = (
            value_counts.index.tolist()
        )

        probabilities = (
            value_counts.values
        )

        synthetic_dataframe[column] = (
            rng.choice(
                categories,
                size=num_rows,
                p=probabilities,
            )
        )

    # 5. Restore original column order
    synthetic_dataframe = (
        synthetic_dataframe[
            working_dataframe.columns
        ]
    )

    # 6. Restore integer columns
    for column in numerical_columns:

        if pd.api.types.is_integer_dtype(
            dataframe[column]
        ):

            synthetic_dataframe[column] = (
                np.rint(
                    synthetic_dataframe[
                        column
                    ]
                ).astype(int)
            )

    return synthetic_dataframe


def _apply_column_actions(
    synthetic_dataframe: pd.DataFrame,
    configurations: list,
) -> pd.DataFrame:
    """
    Enforce configured column actions
    on generated data.
    """

    result = synthetic_dataframe.copy()

    for config in configurations:

        column_name = config["column_name"]
        action = config["action"]

        # If the configured column is not
        # present, there is nothing to enforce.
        if column_name not in result.columns:
            continue

        if action == "keep":

            # Keep generated column unchanged.
            continue

        elif action == "remove":

            result = result.drop(
                columns=[column_name],
                errors="ignore",
            )

        elif action == "mask":

            result[column_name] = (
                result[column_name]
                .astype(str)
                .apply(
                    lambda value:
                    "*" * len(value)
                    if value
                    else value
                )
            )

        elif action == "generalize":

            if pd.api.types.is_numeric_dtype(
                result[column_name]
            ):

                result[column_name] = (
                    result[column_name]
                    .round(0)
                )

            else:

                result[column_name] = (
                    result[column_name]
                    .astype(str)
                    .str[:3]
                )

        elif action == "new_id":

            result = generate_new_ids(
                result,
                column_name,
            )

        elif action == "derived":
            rule = config.get("rule")

            if not rule:
                continue

            operation = rule.get("operation")
            operands = rule.get("operands", [])

            if len(operands) < 2:
                continue

            left = operands[0]
            right = operands[1]

            if left not in result.columns or right not in result.columns:
                continue

            if operation == "add":
                result[column_name] = (
                    result[left] + result[right]
                )

            elif operation == "subtract":
                result[column_name] = (
                    result[left] - result[right]
                )

            elif operation == "multiply":
                result[column_name] = (
                    result[left] * result[right]
                )

            elif operation == "divide":
                non_zero = result[right] != 0

                result.loc[non_zero, column_name] = (
                    result.loc[non_zero, left]
                    / result.loc[non_zero, right]
                )
        else:
            raise ValueError(
                f"Unsupported column action '{action}' "
                f"for column '{column_name}'"
            )

    return result


def generate_synthetic_dataset(
    dataset_id: int,
    model_name: str,
    parameters: dict | None = None,
):    
    # --------------------------------------------------
    # 1. Validate model
    # --------------------------------------------------

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

    run_id = create_generation_run(
        dataset_id=dataset_id,
        model_name=model_name,
    )
    
    save_model_configuration(
        run_id=run_id,
        model_name=model_name,
        parameters=parameters,
    )

    # --------------------------------------------------
    # 2. Prepare dataset
    # --------------------------------------------------

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
    validation_rules = get_validation_rules(dataset_id)

    # --------------------------------------------------
    # 3. Detect generalized business rules
    # --------------------------------------------------

    business_rules = (
        detect_arithmetic_relationships(
            dataframe
        )
    )

    # --------------------------------------------------
    # 4. Generate synthetic data

    if model_name == "gaussian_copula":

        random_state = parameters.get(
            "random_state",
            42,
        )

        def generate_rows(count):
            generated = _generate_gaussian_copula(
                dataframe=dataframe,
                configurations=configurations,
                random_state=random_state,
                num_rows=count,
            )

            generated = apply_business_rules(
                generated,
                business_rules,
            )

            return generated

    else:

        # Remove columns configured with "remove"
        remove_columns = {
            config["column_name"]
            for config in configurations
            if config["action"] == "remove"
        }

        generation_dataframe = (
            dataframe.drop(
                columns=list(remove_columns),
                errors="ignore",
            ).copy()
        )

        # Create requested generator
        generator = get_generator(
            model_name,
            **parameters,
        )

        # Train generator
        generator.fit(
            generation_dataframe
        )

        def generate_rows(count):
            generated = generator.generate(
                num_rows=count
            )

            generated = apply_business_rules(
                generated,
                business_rules,
            )

            return generated


    if validation_rules:

        validation_result = generate_valid_rows(
            generate_function=generate_rows,
            target_row_count=len(dataframe),
            rules=validation_rules,
            max_attempts=10,
        )

        synthetic_dataframe = validation_result[
            "dataframe"
        ]

    else:

        synthetic_dataframe = generate_rows(
            len(dataframe)
        )

        validation_result = {
            "dataframe": synthetic_dataframe,
            "target_row_count": len(dataframe),
            "total_generated_rows": len(
                synthetic_dataframe
            ),
            "total_valid_rows": len(
                synthetic_dataframe
            ),
            "total_rejected_rows": 0,
            "attempts": 1,
            "validation_history": [],
            "final_validation": {
                "valid": True,
                "valid_row_count": len(
                    synthetic_dataframe
                ),
                "invalid_row_count": 0,
                "invalid_rows": [],
                "rules": [],
            },
        }
        
       
    # --------------------------------------------------
    # 5. Apply generalized business rules
    # --------------------------------------------------

    # synthetic_dataframe = (
    #     apply_business_rules(
    #         synthetic_dataframe,
    #         business_rules,
    #     )
    # )

    # --------------------------------------------------
    # 6. Enforce column actions
    # --------------------------------------------------

    synthetic_dataframe = (
        _apply_column_actions(
            synthetic_dataframe=(
                synthetic_dataframe
            ),
            configurations=configurations,
        )
    )

    # --------------------------------------------------
    # 7. Save generated dataset
    # --------------------------------------------------

    generated_dataset = (
        save_generated_dataset(
            synthetic_dataframe,
            dataset_id,
            model_name,
        )
    )
    result_id = save_generated_result(
        run_id=run_id,
        file_name=generated_dataset["file_name"],
        file_path=generated_dataset["file_path"],
        row_count=generated_dataset["row_count"],
        column_count=generated_dataset["column_count"],
    )

    update_generation_run_status(
        run_id=run_id,
        status="completed",
    )

    # --------------------------------------------------
    # 8. Return API response
    # --------------------------------------------------

    return {
        "status": "success",
        "message": (
            "Synthetic dataset generated successfully."
        ),
        "data": {
            "run_id": run_id,
            "result_id": result_id,
            "dataset_id": dataset_id,
            "model_name": model_name,
            "parameters": parameters,
            "source_filename": filename,
            "configurations": configurations,
            "generated_dataset": (
                generated_dataset
            ),
            "business_rules": (
                business_rules
            ),
            "validation": {
                "target_row_count": validation_result["target_row_count"],
                "total_generated_rows": validation_result["total_generated_rows"],
                "total_valid_rows": validation_result["total_valid_rows"],
                "total_rejected_rows": validation_result["total_rejected_rows"],
                "attempts": validation_result["attempts"],
                "final_validation": validation_result["final_validation"],
            },
        },
    }