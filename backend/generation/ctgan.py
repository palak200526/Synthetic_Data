import numpy as np
import pandas as pd
import torch
import torch.nn as nn


# ============================================================
# Generator Network
# ============================================================

class Generator(nn.Module):

    def __init__(self, input_dim, output_dim):
        super().__init__()

        self.model = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),

            nn.Linear(128, 256),
            nn.ReLU(),

            nn.Linear(256, output_dim),
            nn.Sigmoid()
        )

    def forward(self, x):
        return self.model(x)


# ============================================================
# Discriminator Network
# ============================================================

class Discriminator(nn.Module):

    def __init__(self, input_dim):
        super().__init__()

        self.model = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.LeakyReLU(0.2),

            nn.Linear(256, 128),
            nn.LeakyReLU(0.2),

            nn.Linear(128, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        return self.model(x)


# ============================================================
# CTGAN Generator
# ============================================================

class CTGANGenerator:
    """
    Lightweight CTGAN-style generator for tabular data.

    Handles:
    - Numerical columns
    - Categorical columns
    - Identifier columns

    Identifier columns are excluded from GAN training
    and generated separately as new unique values.

    Numerical columns use:
    - Min-max normalization during training
    - GAN-generated latent values
    - Quantile calibration during reconstruction

    Quantile calibration prevents the numerical output
    from collapsing toward only one end of the original
    numerical range.
    """

    def __init__(
        self,
        epochs=100,
        batch_size=32,
        learning_rate=0.0002,
        random_state=42
    ):

        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.random_state = random_state

        self.rng = np.random.default_rng(
            random_state
        )

        torch.manual_seed(
            random_state
        )

        self.columns = None

        self.numeric_columns = []
        self.categorical_columns = []
        self.identifier_columns = []

        self.category_mappings = {}
        self.category_probabilities = {}

        self.numeric_values = {}
        self.numeric_min = {}
        self.numeric_max = {}

        self.generator = None
        self.discriminator = None

    # ========================================================
    # FIT
    # ========================================================

    def fit(
        self,
        df: pd.DataFrame,
        identifier_columns: list[str] | None = None
    ):
        """
        Learn the dataset representation.

        Identifier columns are supplied from the column
        configuration and excluded from GAN training.
        """

        if df.empty:
            raise ValueError(
                "Input dataset cannot be empty."
            )

        # ----------------------------------------------------
        # Store columns
        # ----------------------------------------------------

        self.columns = list(
            df.columns
        )

        # ----------------------------------------------------
        # Identifier columns
        # ----------------------------------------------------

        self.identifier_columns = [
            column
            for column in (identifier_columns or [])
            if column in df.columns
        ]

        # ----------------------------------------------------
        # Numerical columns
        # ----------------------------------------------------

        self.numeric_columns = (
            df.select_dtypes(
                include=[np.number]
            )
            .columns
            .tolist()
        )

        # ----------------------------------------------------
        # Categorical columns
        # ----------------------------------------------------

        self.categorical_columns = [
            column
            for column in df.columns
            if column not in self.numeric_columns
            and column not in self.identifier_columns
        ]

        encoded_data = []

        # ====================================================
        # Numerical columns
        # ====================================================

        for column in self.numeric_columns:

            values = (
                df[column]
                .fillna(
                    df[column].median()
                )
                .astype(float)
            )

            numeric_array = values.to_numpy()

            self.numeric_values[column] = (
                numeric_array
            )

            min_value = numeric_array.min()
            max_value = numeric_array.max()

            self.numeric_min[column] = (
                min_value
            )

            self.numeric_max[column] = (
                max_value
            )

            # ----------------------------------------------
            # Min-max normalization
            # ----------------------------------------------

            if max_value == min_value:

                normalized = np.zeros(
                    len(numeric_array)
                )

            else:

                normalized = (
                    (numeric_array - min_value)
                    / (max_value - min_value)
                )

            encoded_data.append(
                normalized.reshape(-1, 1)
            )

        # ====================================================
        # Categorical columns
        # ====================================================

        for column in self.categorical_columns:

            values = (
                df[column]
                .fillna("__MISSING__")
                .astype(str)
            )

            categories = (
                values.unique()
                .tolist()
            )

            mapping = {
                category: index
                for index, category
                in enumerate(categories)
            }

            self.category_mappings[column] = (
                mapping
            )

            probabilities = (
                values
                .value_counts(
                    normalize=True
                )
            )

            self.category_probabilities[column] = (
                probabilities
            )

            encoded = (
                values
                .map(mapping)
                .to_numpy()
            )

            if len(categories) > 1:

                encoded = (
                    encoded
                    / (len(categories) - 1)
                )

            else:

                encoded = np.zeros(
                    len(values)
                )

            encoded_data.append(
                encoded.reshape(-1, 1)
            )

        # ====================================================
        # Training data
        # ====================================================

        if not encoded_data:

            raise ValueError(
                "No numerical or categorical columns "
                "available for training."
            )

        data = np.concatenate(
            encoded_data,
            axis=1
        ).astype(
            np.float32
        )

        data_tensor = torch.tensor(
            data
        )

        input_dim = data.shape[1]
        output_dim = data.shape[1]

        # ====================================================
        # Networks
        # ====================================================

        self.generator = Generator(
            input_dim=input_dim,
            output_dim=output_dim
        )

        self.discriminator = Discriminator(
            input_dim=output_dim
        )

        optimizer_g = torch.optim.Adam(
            self.generator.parameters(),
            lr=self.learning_rate
        )

        optimizer_d = torch.optim.Adam(
            self.discriminator.parameters(),
            lr=self.learning_rate
        )

        criterion = nn.BCELoss()

        # ====================================================
        # GAN training
        # ====================================================

        for epoch in range(
            self.epochs
        ):

            indices = torch.randperm(
                len(data_tensor)
            )

            for start in range(
                0,
                len(data_tensor),
                self.batch_size
            ):

                batch_indices = indices[
                    start:start + self.batch_size
                ]

                real_data = data_tensor[
                    batch_indices
                ]

                current_batch_size = len(
                    real_data
                )

                # ------------------------------------------
                # Train discriminator
                # ------------------------------------------

                noise = torch.randn(
                    current_batch_size,
                    input_dim
                )

                fake_data = self.generator(
                    noise
                )

                real_labels = torch.ones(
                    current_batch_size,
                    1
                )

                fake_labels = torch.zeros(
                    current_batch_size,
                    1
                )

                optimizer_d.zero_grad()

                real_output = (
                    self.discriminator(
                        real_data
                    )
                )

                fake_output = (
                    self.discriminator(
                        fake_data.detach()
                    )
                )

                loss_real = criterion(
                    real_output,
                    real_labels
                )

                loss_fake = criterion(
                    fake_output,
                    fake_labels
                )

                loss_d = (
                    loss_real
                    + loss_fake
                )

                loss_d.backward()

                optimizer_d.step()

                # ------------------------------------------
                # Train generator
                # ------------------------------------------

                optimizer_g.zero_grad()

                noise = torch.randn(
                    current_batch_size,
                    input_dim
                )

                generated = self.generator(
                    noise
                )

                output = self.discriminator(
                    generated
                )

                loss_g = criterion(
                    output,
                    real_labels
                )

                loss_g.backward()

                optimizer_g.step()

        print(
            "Training completed."
        )

        return self

    # ========================================================
    # NUMERICAL QUANTILE CALIBRATION
    # ========================================================

    def _reconstruct_numeric_column(
        self,
        generated_values,
        column
    ):
        """
        Convert GAN output into values following the
        learned empirical numerical distribution.

        The GAN output determines the ordering/ranks,
        while the original numerical distribution provides
        the actual value scale.

        This prevents numerical mode collapse toward one
        end of the range.
        """

        original_values = (
            self.numeric_values[column]
        )

        if len(original_values) == 0:
            return generated_values

        # ----------------------------------------------------
        # Sort GAN-generated values
        # ----------------------------------------------------

        generated_values = np.asarray(
            generated_values
        )

        generated_values = np.clip(
            generated_values,
            0.0,
            1.0
        )

        # ----------------------------------------------------
        # Convert generated values to ranks
        # ----------------------------------------------------

        ranks = np.argsort(
            np.argsort(
                generated_values
            )
        )

        if len(generated_values) == 1:
            quantiles = np.array([0.5])
        else:
            quantiles = (
                ranks + 0.5
            ) / len(
                generated_values
            )

        # ----------------------------------------------------
        # Original empirical distribution
        # ----------------------------------------------------

        sorted_original = np.sort(
            original_values
        )

        original_positions = (
            np.arange(
                len(sorted_original)
            )
            / max(
                len(sorted_original) - 1,
                1
            )
        )

        # ----------------------------------------------------
        # Interpolate generated quantiles
        # ----------------------------------------------------

        reconstructed = np.interp(
            quantiles,
            original_positions,
            sorted_original
        )

        return reconstructed

    # ========================================================
    # GENERATE
    # ========================================================

    def generate(
        self,
        num_rows: int
    ) -> pd.DataFrame:
        """
        Generate synthetic records.

        Identifier columns are NOT generated by the GAN.
        They are created separately as unique synthetic IDs.
        """

        if self.generator is None:

            raise RuntimeError(
                "Model has not been fitted. "
                "Call fit() first."
            )

        if num_rows <= 0:

            raise ValueError(
                "num_rows must be greater than zero."
            )

        model_columns = (
            self.numeric_columns
            + self.categorical_columns
        )

        input_dim = len(
            model_columns
        )

        if input_dim == 0:

            raise RuntimeError(
                "No columns available for generation."
            )

        # ====================================================
        # Generate GAN output
        # ====================================================

        noise = torch.randn(
            num_rows,
            input_dim
        )

        with torch.no_grad():

            generated = (
                self.generator(
                    noise
                )
                .numpy()
            )

        synthetic_data = {}

        column_index = 0

        # ====================================================
        # Numerical columns
        # ====================================================

        for column in self.numeric_columns:

            generated_values = (
                generated[
                    :,
                    column_index
                ]
            )

            # ----------------------------------------------
            # Quantile calibration
            # ----------------------------------------------

            values = (
                self._reconstruct_numeric_column(
                    generated_values,
                    column
                )
            )

            original_dtype = (
                self.numeric_values[
                    column
                ].dtype
            )

            # ----------------------------------------------
            # Preserve integer columns
            # ----------------------------------------------

            if pd.api.types.is_integer_dtype(
                original_dtype
            ):

                values = np.round(
                    values
                ).astype(int)

            synthetic_data[column] = (
                values
            )

            column_index += 1

        # ====================================================
        # Categorical columns
        # ====================================================

        for column in self.categorical_columns:

            probabilities = (
                self.category_probabilities[
                    column
                ]
            )

            categories = (
                probabilities.index
                .tolist()
            )

            probabilities_array = (
                probabilities
                .to_numpy()
            )

            values = self.rng.choice(
                categories,
                size=num_rows,
                p=probabilities_array
            )

            synthetic_data[column] = (
                values
            )

            column_index += 1

        # ====================================================
        # Generate new identifiers
        # ====================================================

        for column in self.identifier_columns:

            synthetic_data[column] = [
                f"{column}_{index:06d}"
                for index in range(
                    1,
                    num_rows + 1
                )
            ]

        # ====================================================
        # Create final DataFrame
        # ====================================================

        synthetic_df = pd.DataFrame(
            synthetic_data
        )

        # ====================================================
        # Restore original column order
        # ====================================================

        synthetic_df = synthetic_df[
            self.columns
        ]

        return synthetic_df