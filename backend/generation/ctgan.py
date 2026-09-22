import numpy as np
import pandas as pd
import torch
import torch.nn as nn


class Generator(nn.Module):
    def __init__(self, input_dim, output_dim):
        super().__init__()

        self.model = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 256),
            nn.ReLU(),
            nn.Linear(256, output_dim)
        )

    def forward(self, x):
        return self.model(x)


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


class CTGANGenerator:
    """
    Lightweight PyTorch-based CTGAN-style generator.

    Handles:
    - Numerical columns
    - Categorical columns
    - Identifier columns

    Numerical columns use the learned empirical distribution
    to avoid numerical mode collapse.
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

        self.rng = np.random.default_rng(random_state)
        torch.manual_seed(random_state)

        self.columns = None

        self.numeric_columns = []
        self.categorical_columns = []
        self.identifier_columns = []

        self.category_mappings = {}
        self.numeric_values = {}

        self.generator = None
        self.discriminator = None

    def fit(self, df: pd.DataFrame):
        """
        Train the CTGAN-style model.
        """

        if df.empty:
            raise ValueError(
                "Input dataset cannot be empty."
            )

        self.columns = list(df.columns)

        # Identify ID columns

        self.identifier_columns = [
            column
            for column in df.columns
            if column.lower().endswith("_id")
            or column.lower() == "id"
        ]

        # Identify numerical columns

        self.numeric_columns = df.select_dtypes(
            include=[np.number]
        ).columns.tolist()

        # Identify categorical columns

        self.categorical_columns = [
            column
            for column in df.columns
            if column not in self.numeric_columns
            and column not in self.identifier_columns
        ]

        encoded_data = []

        # Numerical columns

        for column in self.numeric_columns:

            values = (
                df[column]
                .fillna(df[column].median())
                .astype(float)
            )

            # Store original distribution
            self.numeric_values[column] = (
                values.to_numpy()
            )

            # Normalize for GAN training
            min_value = values.min()
            max_value = values.max()

            if max_value == min_value:
                normalized = np.zeros(
                    len(values)
                )
            else:
                normalized = (
                    (values - min_value)
                    / (max_value - min_value)
                )

            encoded_data.append(
                normalized.to_numpy().reshape(-1, 1)
            )

        # Categorical columns

        for column in self.categorical_columns:

            values = (
                df[column]
                .fillna("__MISSING__")
                .astype(str)
            )

            categories = values.unique().tolist()

            mapping = {
                category: index
                for index, category
                in enumerate(categories)
            }

            self.category_mappings[column] = mapping

            encoded = values.map(mapping).to_numpy()

            if len(categories) > 1:
                encoded = (
                    encoded
                    / (len(categories) - 1)
                )

            encoded_data.append(
                encoded.reshape(-1, 1)
            )

        if not encoded_data:
            raise ValueError(
                "No numerical or categorical columns "
                "available for training."
            )

        data = np.concatenate(
            encoded_data,
            axis=1
        ).astype(np.float32)

        data_tensor = torch.tensor(data)

        input_dim = data.shape[1]
        output_dim = data.shape[1]

        # Networks

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

        # Training

        for epoch in range(self.epochs):

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

                # Discriminator
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

                real_output = self.discriminator(
                    real_data
                )

                fake_output = self.discriminator(
                    fake_data.detach()
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
                    loss_real + loss_fake
                )

                loss_d.backward()
                optimizer_d.step()

                # Generator

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

        return self

    def generate(self, num_rows: int) -> pd.DataFrame:
        """
        Generate synthetic tabular records.
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

        input_dim = len(model_columns)

        if input_dim == 0:
            raise RuntimeError(
                "No columns available for generation."
            )

        # Generate GAN output.
        noise = torch.randn(
            num_rows,
            input_dim
        )

        with torch.no_grad():
            generated = self.generator(
                noise
            ).numpy()

        synthetic_data = {}

        column_index = 0

        # Numerical columns
        for column in self.numeric_columns:

            original_values = (
                self.numeric_values[column]
            )

            # Bootstrap from learned empirical distribution
            # and add very small jitter.
            values = self.rng.choice(
                original_values,
                size=num_rows,
                replace=True
            ).astype(float)

            std = np.std(original_values)

            if std > 0:
                jitter = self.rng.normal(
                    loc=0,
                    scale=std * 0.01,
                    size=num_rows
                )

                values = values + jitter

            # Keep values inside original range
            values = np.clip(
                values,
                np.min(original_values),
                np.max(original_values)
            )

            # Preserve integer columns
            original_dtype = (
                pd.Series(original_values).dtype
            )

            if pd.api.types.is_integer_dtype(
                original_dtype
            ):
                values = np.round(
                    values
                ).astype(int)

            synthetic_data[column] = values

            column_index += 1

        # Categorical columns
        for column in self.categorical_columns:

            mapping = self.category_mappings[
                column
            ]

            categories = list(
                mapping.keys()
            )

            # Use the GAN output to select categories.
            values = generated[
                :, column_index
            ]

            values = np.clip(
                values,
                0,
                1
            )

            indices = np.round(
                values * (len(categories) - 1)
            ).astype(int)

            synthetic_data[column] = [
                categories[index]
                for index in indices
            ]

            column_index += 1

        # Unique identifiers

        for column in self.identifier_columns:

            if column.lower() == "product_id":

                synthetic_data[column] = [
                    f"PROD{index:04d}"
                    for index in range(
                        1,
                        num_rows + 1
                    )
                ]

            else:

                prefix = (
                    column
                    .replace("_id", "")
                    .upper()
                )

                synthetic_data[column] = [
                    f"{prefix}{index:04d}"
                    for index in range(
                        1,
                        num_rows + 1
                    )
                ]

        # Restore original column order

        synthetic_df = pd.DataFrame(
            synthetic_data,
            columns=self.columns
        )

        return synthetic_df