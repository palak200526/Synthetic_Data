# import numpy as np
# import pandas as pd

# from scipy.stats import norm
# from sklearn.preprocessing import QuantileTransformer


# class GaussianCopulaGenerator:
#     """
#     Gaussian Copula generator for tabular data.

#     Learns:
#     - Marginal distributions of numerical columns
#     - Category distributions of categorical columns
#     - Correlation structure between numerical columns

#     Identifier columns are supplied by the configuration layer
#     and are generated separately with new unique values.
#     """

#     def __init__(self, random_state: int = 42):

#         self.random_state = random_state

#         self.rng = np.random.default_rng(
#             random_state
#         )

#         self.columns = None

#         self.numeric_columns = []

#         self.categorical_columns = []

#         self.identifier_columns = []

#         self.quantile_transformers = {}

#         self.category_probabilities = {}

#         self.correlation_matrix = None

#         self.original_dtypes = {}

#     def fit(
#         self,
#         df: pd.DataFrame,
#         identifier_columns: list[str] | None = None
#     ):
#         """
#         Learn the distribution and dependency structure
#         from the input dataset.
#         """

#         if df.empty:
#             raise ValueError(
#                 "Input dataset cannot be empty."
#             )

#         # ---------------------------------------------------------
#         # 1. Store original dataset information
#         # ---------------------------------------------------------

#         self.columns = list(df.columns)

#         self.original_dtypes = (
#             df.dtypes.to_dict()
#         )

#         # ---------------------------------------------------------
#         # 2. Receive identifier columns from configuration
#         # ---------------------------------------------------------

#         self.identifier_columns = (
#             identifier_columns or []
#         )

#         # Validate identifier columns

#         for column in self.identifier_columns:

#             if column not in df.columns:
#                 raise ValueError(
#                     f"Identifier column '{column}' "
#                     "does not exist in the dataset."
#                 )

#         # ---------------------------------------------------------
#         # 3. Detect numerical columns
#         # ---------------------------------------------------------
#         # Identifier columns must NOT be treated as numerical
#         # variables even if their values are numeric.

#         self.numeric_columns = [
#             column
#             for column in df.select_dtypes(
#                 include=[np.number]
#             ).columns
#             if column not in self.identifier_columns
#         ]

#         # ---------------------------------------------------------
#         # 4. Detect categorical columns
#         # ---------------------------------------------------------
#         # Identifier columns and numerical columns are excluded.

#         self.categorical_columns = [
#             column
#             for column in df.columns
#             if column not in self.numeric_columns
#             and column not in self.identifier_columns
#         ]

#         # ---------------------------------------------------------
#         # 5. Prepare numerical columns
#         # ---------------------------------------------------------

#         transformed_data = []

#         for column in self.numeric_columns:

#             series = df[column].copy()

#             # Fill missing numerical values

#             series = series.fillna(
#                 series.median()
#             )

#             transformer = QuantileTransformer(
#                 output_distribution="normal",
#                 random_state=self.random_state,
#                 n_quantiles=min(
#                     1000,
#                     len(df)
#                 )
#             )

#             transformed = transformer.fit_transform(
#                 series.to_numpy().reshape(-1, 1)
#             ).flatten()

#             self.quantile_transformers[
#                 column
#             ] = transformer

#             transformed_data.append(
#                 transformed
#             )

#         # ---------------------------------------------------------
#         # 6. Learn categorical distributions
#         # ---------------------------------------------------------

#         for column in self.categorical_columns:

#             probabilities = (
#                 df[column]
#                 .fillna("__MISSING__")
#                 .value_counts(
#                     normalize=True
#                 )
#             )

#             self.category_probabilities[
#                 column
#             ] = probabilities

#         # ---------------------------------------------------------
#         # 7. Learn numerical correlation structure
#         # ---------------------------------------------------------

#         if len(self.numeric_columns) >= 2:

#             numeric_matrix = np.column_stack(
#                 transformed_data
#             )

#             self.correlation_matrix = (
#                 np.corrcoef(
#                     numeric_matrix,
#                     rowvar=False
#                 )
#             )

#             # Numerical stability

#             self.correlation_matrix += (
#                 np.eye(
#                     len(self.numeric_columns)
#                 ) * 1e-6
#             )

#         elif len(self.numeric_columns) == 1:

#             self.correlation_matrix = np.array(
#                 [[1.0]]
#             )

#         else:

#             self.correlation_matrix = None

#         return self

#     def generate(
#         self,
#         num_rows: int
#     ) -> pd.DataFrame:
#         """
#         Generate synthetic records.
#         """

#         if self.columns is None:
#             raise RuntimeError(
#                 "Model has not been fitted. "
#                 "Call fit() first."
#             )

#         if num_rows <= 0:
#             raise ValueError(
#                 "num_rows must be greater than zero."
#             )

#         synthetic_data = {}

#         # ---------------------------------------------------------
#         # 1. Generate new identifiers
#         # ---------------------------------------------------------

#         for column in self.identifier_columns:

#             synthetic_data[column] = [
#                 f"{column}_{index:06d}"
#                 for index in range(
#                     1,
#                     num_rows + 1
#                 )
#             ]

#         # ---------------------------------------------------------
#         # 2. Generate numerical columns
#         # ---------------------------------------------------------

#         if self.numeric_columns:

#             num_numeric = len(
#                 self.numeric_columns
#             )

#             if num_numeric == 1:

#                 latent_values = (
#                     self.rng.normal(
#                         size=(num_rows, 1)
#                     )
#                 )

#             else:

#                 latent_values = (
#                     self.rng.multivariate_normal(
#                         mean=np.zeros(
#                             num_numeric
#                         ),
#                         cov=self.correlation_matrix,
#                         size=num_rows
#                     )
#                 )

#             for index, column in enumerate(
#                 self.numeric_columns
#             ):

#                 transformer = (
#                     self.quantile_transformers[
#                         column
#                     ]
#                 )

#                 # Normal → Uniform

#                 uniform_values = norm.cdf(
#                     latent_values[:, index]
#                 )

#                 # Uniform → Original distribution

#                 synthetic_values = (
#                     transformer.inverse_transform(
#                         uniform_values.reshape(
#                             -1,
#                             1
#                         )
#                     ).flatten()
#                 )

#                 # Preserve integer columns

#                 if pd.api.types.is_integer_dtype(
#                     self.original_dtypes[column]
#                 ):

#                     synthetic_values = (
#                         np.round(
#                             synthetic_values
#                         ).astype(
#                             self.original_dtypes[
#                                 column
#                             ]
#                         )
#                     )

#                 synthetic_data[
#                     column
#                 ] = synthetic_values

#         # ---------------------------------------------------------
#         # 3. Generate categorical columns
#         # ---------------------------------------------------------

#         for column in self.categorical_columns:

#             probabilities = (
#                 self.category_probabilities[
#                     column
#                 ]
#             )

#             categories = (
#                 probabilities.index.to_numpy()
#             )

#             probabilities_array = (
#                 probabilities.to_numpy()
#             )

#             values = self.rng.choice(
#                 categories,
#                 size=num_rows,
#                 p=probabilities_array
#             )

#             synthetic_data[
#                 column
#             ] = values

#         # ---------------------------------------------------------
#         # 4. Restore original column order
#         # ---------------------------------------------------------

#         synthetic_df = pd.DataFrame(
#             synthetic_data,
#             columns=self.columns
#         )

#         return synthetic_df

import warnings

import numpy as np
import pandas as pd

from sdv.single_table import GaussianCopulaSynthesizer

try:  # naye SDV versions
    from sdv.metadata import Metadata
except ImportError:  # purane SDV versions
    Metadata = None
    from sdv.metadata import SingleTableMetadata

warnings.filterwarnings("ignore", message=".*save_to_json.*")

_TABLE = "data"


# UI-friendly names -> names SDV understands
_DISTRIBUTION_ALIASES = {"gaussian": "norm", "normal": "norm"}


class GaussianCopulaGenerator:
    """
    Gaussian Copula from SDV (GaussianCopulaSynthesizer).
    Numeric aur categorical dono columns copula ke andar model hote hain.
    Missing values SDV khud handle karta hai (null rate bhi seekhta hai).
    """

    def __init__(
        self,
        random_state=42,
        default_distribution=None,
        enforce_min_max_values=True,
    ):
        self.random_state = int(random_state)
        if isinstance(default_distribution, str):
            default_distribution = _DISTRIBUTION_ALIASES.get(
                default_distribution.strip().lower(),
                default_distribution.strip().lower(),
            )
        self.default_distribution = default_distribution
        self.enforce_min_max_values = bool(enforce_min_max_values)
        self.columns = None
        self.numeric_columns = []
        self.categorical_columns = []
        self.identifier_columns = []
        self.original_dtypes = {}
        self.numeric_bounds = {}
        self.model = None

    def _build_metadata(self, model_df: pd.DataFrame):
        if Metadata is not None:
            metadata = Metadata.detect_from_dataframe(model_df, table_name=_TABLE)
            table = metadata.tables[_TABLE]
            update = lambda col, sd: metadata.update_column(
                column_name=col, sdtype=sd, table_name=_TABLE
            )
        else:
            metadata = SingleTableMetadata()
            metadata.detect_from_dataframe(model_df)
            table = metadata
            update = lambda col, sd: metadata.update_column(
                column_name=col, sdtype=sd
            )

        # SDV unique columns ko auto primary key bana deta hai -> hata do
        for remover in (
            lambda: metadata.remove_primary_key(table_name=_TABLE),
            lambda: metadata.remove_primary_key(),
            lambda: setattr(table, "primary_key", None),
        ):
            try:
                remover()
                break
            except Exception:
                continue

        for column in self.numeric_columns:
            update(column, "numerical")
        for column in self.categorical_columns:
            update(column, "categorical")
        return metadata

    def fit(self, df: pd.DataFrame, identifier_columns=None, progress_callback=None):
        if df.empty:
            raise ValueError("Input dataset cannot be empty.")

        self.identifier_columns = identifier_columns or []
        for column in self.identifier_columns:
            if column not in df.columns:
                raise ValueError(f"Identifier column '{column}' does not exist in the dataset.")

        self.columns = list(df.columns)
        self.original_dtypes = df.dtypes.to_dict()

        model_df = df.drop(columns=self.identifier_columns).copy()
        self.numeric_columns = list(model_df.select_dtypes(include=[np.number]).columns)
        self.categorical_columns = [c for c in model_df.columns if c not in self.numeric_columns]

        if not self.numeric_columns and not self.categorical_columns:
            raise ValueError("No numerical or categorical columns available for training.")

        for column in self.numeric_columns:
            series = model_df[column].dropna()
            if series.empty:
                raise ValueError(f"Numeric column '{column}' has no valid values.")
            self.numeric_bounds[column] = (float(series.min()), float(series.max()))

        for column in self.categorical_columns:
            model_df[column] = model_df[column].astype("object").where(
                model_df[column].notna(), np.nan
            )

        np.random.seed(self.random_state)

        metadata = self._build_metadata(model_df)
        synth_kwargs = {
            "enforce_min_max_values": self.enforce_min_max_values,
        }
        if self.default_distribution:
            synth_kwargs["default_distribution"] = self.default_distribution
        self.model = GaussianCopulaSynthesizer(metadata, **synth_kwargs)
        self.model.fit(model_df)

        if progress_callback is not None:
            progress_callback(1, 1)  # copula me epochs nahi hote
        return self

    def generate(self, num_rows: int) -> pd.DataFrame:
        if self.model is None:
            raise RuntimeError("Model has not been fitted. Call fit() first.")
        if num_rows <= 0:
            raise ValueError("num_rows must be greater than zero.")

        np.random.seed(self.random_state)
        synthetic = self.model.sample(num_rows=int(num_rows)).reset_index(drop=True)

        for column in self.numeric_columns:
            low, high = self.numeric_bounds[column]
            values = synthetic[column]
            if self.enforce_min_max_values:
                values = values.clip(low, high)
            dtype = self.original_dtypes[column]
            if pd.api.types.is_integer_dtype(dtype) and not values.isna().any():
                values = np.round(values).astype(dtype)
            synthetic[column] = values

        # Placeholder IDs; service layer inhe new_id action se replace karti hai
        for column in self.identifier_columns:
            synthetic[column] = [f"{column}_{i:06d}" for i in range(1, num_rows + 1)]

        return synthetic[self.columns]