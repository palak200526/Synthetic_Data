import numpy as np
import pandas as pd
from scipy.stats import norm

from backend.services.generated_dataset_service import (
    prepare_dataset_for_generation,
    save_generated_dataset,
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
) -> pd.DataFrame:

    rng = np.random.default_rng(random_state)

    # -----------------------------------------
    # 1. Determine columns based on configuration
    # -----------------------------------------
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

    # -----------------------------------------
    # 2. Separate numerical and categorical data
    # -----------------------------------------
    numerical_columns = working_dataframe.select_dtypes(
        include=np.number
    ).columns.tolist()

    categorical_columns = [
        column
        for column in working_dataframe.columns
        if column not in numerical_columns
    ]

    synthetic_dataframe = pd.DataFrame(
        index=range(len(dataframe))
    )

    # -----------------------------------------
    # 3. Generate numerical columns
    # -----------------------------------------
    if numerical_columns:

        numerical_data = working_dataframe[
            numerical_columns
        ].copy()

        # Rank -> uniform -> Gaussian transformation
        gaussian_data = pd.DataFrame(
            index=numerical_data.index
        )

        for column in numerical_columns:

            values = numerical_data[column].to_numpy()

            ranks = pd.Series(values).rank(
                method="average"
            ).to_numpy()

            uniform_values = (
                ranks - 0.5
            ) / len(values)

            gaussian_values = norm.ppf(
                uniform_values
            )

            gaussian_data[column] = gaussian_values

        # Correlation structure
        correlation_matrix = gaussian_data.corr().fillna(0)

        correlation_matrix = (
            correlation_matrix
            + np.eye(len(correlation_matrix)) * 1e-6
        )

        # Make matrix positive definite
        eigenvalues, eigenvectors = np.linalg.eigh(
            correlation_matrix
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
        generated_gaussian = rng.multivariate_normal(
            mean=np.zeros(len(numerical_columns)),
            cov=correlation_matrix,
            size=len(dataframe),
        )

        # Transform back to original distributions
        for index, column in enumerate(
            numerical_columns
        ):

            original_values = numerical_data[
                column
            ].dropna().to_numpy()

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

    # -----------------------------------------
    # 4. Generate categorical columns
    # -----------------------------------------
    for column in categorical_columns:

        value_counts = (
            working_dataframe[column]
            .value_counts(normalize=True)
        )

        categories = value_counts.index.tolist()
        probabilities = value_counts.values

        synthetic_dataframe[column] = rng.choice(
            categories,
            size=len(dataframe),
            p=probabilities,
        )

    # -----------------------------------------
    # 5. Restore original column order
    # -----------------------------------------
    synthetic_dataframe = synthetic_dataframe[
        working_dataframe.columns
    ]

    # -----------------------------------------
    # 6. Restore integer columns
    # -----------------------------------------
    for column in numerical_columns:

        if pd.api.types.is_integer_dtype(
            dataframe[column]
        ):
            synthetic_dataframe[column] = (
                np.rint(
                    synthetic_dataframe[column]
                ).astype(int)
            )

    return synthetic_dataframe


def generate_synthetic_dataset(
    dataset_id: int,
    model_name: str,
    parameters: dict | None = None,
):

    # -----------------------------------------
    # 1. Validate model
    # -----------------------------------------
    if not model_name:
        raise ValueError(
            "Model name is required."
        )

    model_name = model_name.strip().lower()

    if model_name not in SUPPORTED_MODELS:
        raise ValueError(
            f"Unsupported model: {model_name}. "
            f"Supported models are: "
            f"{', '.join(sorted(SUPPORTED_MODELS))}."
        )

    parameters = parameters or {}

    # -----------------------------------------
    # 2. Prepare dataset
    # -----------------------------------------
    preparation = prepare_dataset_for_generation(
        dataset_id
    )

    dataframe = preparation["dataframe"]
    filename = preparation["filename"]
    configurations = preparation["configurations"]

    # -----------------------------------------
    # 3. Generation
    # -----------------------------------------
    if model_name == "gaussian_copula":

        random_state = parameters.get(
            "random_state",
            42,
        )

        synthetic_dataframe = (
            _generate_gaussian_copula(
                dataframe=dataframe,
                configurations=configurations,
                random_state=random_state,
            )
        )

    else:

        raise NotImplementedError(
            f"{model_name} generation algorithm "
            "is not implemented yet."
        )

    # -----------------------------------------
    # 4. Save generated dataset
    # -----------------------------------------
    generated_dataset = save_generated_dataset(
        synthetic_dataframe,
        dataset_id,
    )

    # -----------------------------------------
    # 5. Return API response
    # -----------------------------------------
    return {
        "status": "success",
        "message": (
            "Synthetic dataset generated successfully."
        ),
        "data": {
            "dataset_id": dataset_id,
            "model_name": model_name,
            "parameters": parameters,
            "source_filename": filename,
            "configurations": configurations,
            "generated_dataset": generated_dataset,
        },
    }