import numpy as np
import pandas as pd

from scipy.stats import norm
from sklearn.preprocessing import QuantileTransformer


class GaussianCopulaGenerator:
    """
    Gaussian Copula generator for tabular data.

    Learns:
    - Marginal distributions of numerical columns
    - Category distributions of categorical columns
    - Correlation structure between numerical columns

    Identifier columns are handled separately so that
    synthetic records receive new unique identifiers.
    """

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.rng = np.random.default_rng(random_state)

        self.columns = None
        self.numeric_columns = []
        self.categorical_columns = []
        self.identifier_columns = []

        self.quantile_transformers = {}
        self.category_probabilities = {}
        self.correlation_matrix = None
        self.original_dtypes = {}

    def fit(self, df: pd.DataFrame):
        """
        Learn the distribution and dependency structure
        from the input dataset.
        """

        if df.empty:
            raise ValueError("Input dataset cannot be empty.")

        # Store original column names
        self.columns = list(df.columns)

        # Store original data types
        self.original_dtypes = df.dtypes.to_dict()

        # Detect identifier columns
        self.identifier_columns = [
            column
            for column in df.columns
            if column.lower().endswith("_id")
            or column.lower() == "id"
        ]

        # Detect numerical columns
        self.numeric_columns = df.select_dtypes(
            include=[np.number]
        ).columns.tolist()

        # Detect categorical columns
        # Identifier columns are excluded because they
        # should not be sampled like normal categories.
        self.categorical_columns = [
            column
            for column in df.columns
            if column not in self.numeric_columns
            and column not in self.identifier_columns
        ]

        # Prepare numerical columns
        transformed_data = []

        for column in self.numeric_columns:

            series = df[column].copy()

            # Fill missing numerical values
            series = series.fillna(series.median())

            transformer = QuantileTransformer(
                output_distribution="normal",
                random_state=self.random_state,
                n_quantiles=min(1000, len(df))
            )

            transformed = transformer.fit_transform(
                series.to_numpy().reshape(-1, 1)
            ).flatten()

            self.quantile_transformers[column] = transformer

            transformed_data.append(transformed)

        # Learn categorical distributions
        for column in self.categorical_columns:

            probabilities = (
                df[column]
                .fillna("__MISSING__")
                .value_counts(normalize=True)
            )

            self.category_probabilities[column] = probabilities

        # Learn correlation between numerical columns
        if len(self.numeric_columns) >= 2:

            numeric_matrix = np.column_stack(
                transformed_data
            )

            self.correlation_matrix = np.corrcoef(
                numeric_matrix,
                rowvar=False
            )

            # Numerical stability
            self.correlation_matrix += (
                np.eye(len(self.numeric_columns)) * 1e-6
            )

        elif len(self.numeric_columns) == 1:

            self.correlation_matrix = np.array([[1.0]])

        return self

    def generate(self, num_rows: int) -> pd.DataFrame:
        """
        Generate synthetic records.
        """

        if self.columns is None:
            raise RuntimeError(
                "Model has not been fitted. Call fit() first."
            )

        if num_rows <= 0:
            raise ValueError(
                "num_rows must be greater than zero."
            )

        synthetic_data = {}

        # Generate new unique identifiers

        for column in self.identifier_columns:

            synthetic_data[column] = [
                f"PROD{index:04d}"
                for index in range(1, num_rows + 1)
            ]

        # Generate numerical columns

        if self.numeric_columns:

            num_numeric = len(self.numeric_columns)

            if num_numeric == 1:

                latent_values = self.rng.normal(
                    size=(num_rows, 1)
                )

            else:

                latent_values = self.rng.multivariate_normal(
                    mean=np.zeros(num_numeric),
                    cov=self.correlation_matrix,
                    size=num_rows
                )

            for index, column in enumerate(
                self.numeric_columns
            ):

                transformer = self.quantile_transformers[column]

                # Convert normal values to uniform values
                uniform_values = norm.cdf(
                    latent_values[:, index]
                )

                # Convert uniform values back to
                # the original distribution
                synthetic_values = transformer.inverse_transform(
                    uniform_values.reshape(-1, 1)
                ).flatten()

                # Preserve integer columns
                if pd.api.types.is_integer_dtype(
                    self.original_dtypes[column]
                ):
                    synthetic_values = np.round(
                        synthetic_values
                    ).astype(
                        self.original_dtypes[column]
                    )

                synthetic_data[column] = synthetic_values

        # Generate categorical columns

        for column in self.categorical_columns:

            probabilities = self.category_probabilities[
                column
            ]

            categories = probabilities.index.to_numpy()

            probabilities_array = (
                probabilities.to_numpy()
            )

            values = self.rng.choice(
                categories,
                size=num_rows,
                p=probabilities_array
            )

            synthetic_data[column] = values

        # Restore original column order

        synthetic_df = pd.DataFrame(
            synthetic_data,
            columns=self.columns
        )

        return synthetic_df