import numpy as np
import pandas as pd
import torch
import torch.nn as nn


class Encoder(nn.Module):
    def __init__(self, input_dim, latent_dim):
        super().__init__()

        self.network = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU()
        )

        self.mu = nn.Linear(64, latent_dim)
        self.logvar = nn.Linear(64, latent_dim)

    def forward(self, x):
        hidden = self.network(x)

        return (
            self.mu(hidden),
            self.logvar(hidden)
        )


class Decoder(nn.Module):
    def __init__(self, latent_dim, output_dim):
        super().__init__()

        self.network = nn.Sequential(
            nn.Linear(latent_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 128),
            nn.ReLU(),
            nn.Linear(128, output_dim),
            nn.Sigmoid()
        )

    def forward(self, z):
        return self.network(z)


class TVAEGenerator:
    """
    Lightweight PyTorch-based TVAE generator.

    Handles:
    - Numerical columns
    - Categorical columns
    - Identifier columns separately

    The model learns a latent representation of the
    tabular dataset and reconstructs synthetic records.
    """

    def __init__(
        self,
        latent_dim=16,
        epochs=100,
        batch_size=32,
        learning_rate=0.001,
        random_state=42
    ):
        self.latent_dim = latent_dim
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.random_state = random_state

        self.rng = np.random.default_rng(
            random_state
        )

        torch.manual_seed(random_state)

        self.columns = None

        self.numeric_columns = []
        self.categorical_columns = []
        self.identifier_columns = []

        self.category_mappings = {}
        self.numeric_values = {}

        self.encoder = None
        self.decoder = None

    def fit(self, df: pd.DataFrame):
        """
        Train the TVAE model.
        """

        if df.empty:
            raise ValueError(
                "Input dataset cannot be empty."
            )

        self.columns = list(df.columns)

        # Identify columns

        self.identifier_columns = [
            column
            for column in df.columns
            if column.lower().endswith("_id")
            or column.lower() == "id"
        ]

        self.numeric_columns = df.select_dtypes(
            include=[np.number]
        ).columns.tolist()

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

            self.numeric_values[column] = (
                values.to_numpy()
            )

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

        # --------------------------------------------------
        # Categorical columns
        # --------------------------------------------------

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

        # --------------------------------------------------
        # Create encoder and decoder
        # --------------------------------------------------

        self.encoder = Encoder(
            input_dim=input_dim,
            latent_dim=self.latent_dim
        )

        self.decoder = Decoder(
            latent_dim=self.latent_dim,
            output_dim=input_dim
        )

        optimizer = torch.optim.Adam(
            list(self.encoder.parameters())
            + list(self.decoder.parameters()),
            lr=self.learning_rate
        )

        # --------------------------------------------------
        # Training
        # --------------------------------------------------

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

                batch = data_tensor[
                    batch_indices
                ]

                # Encoder
                mu, logvar = self.encoder(
                    batch
                )

                # Reparameterization trick
                std = torch.exp(
                    0.5 * logvar
                )

                epsilon = torch.randn_like(
                    std
                )

                z = (
                    mu
                    + epsilon * std
                )

                # Decoder
                reconstructed = self.decoder(
                    z
                )

                # Reconstruction loss
                reconstruction_loss = torch.mean(
                    (reconstructed - batch) ** 2
                )

                # KL divergence
                kl_loss = -0.5 * torch.mean(
                    1
                    + logvar
                    - mu.pow(2)
                    - logvar.exp()
                )

                loss = (
                    reconstruction_loss
                    + 0.01 * kl_loss
                )

                optimizer.zero_grad()

                loss.backward()

                optimizer.step()

        return self

    def generate(self, num_rows: int) -> pd.DataFrame:
        """
        Generate synthetic tabular records.
        """

        if self.encoder is None:
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

        # Sample from latent space

        latent = torch.randn(
            num_rows,
            self.latent_dim
        )

        with torch.no_grad():
            generated = self.decoder(
                latent
            ).numpy()

        synthetic_data = {}

        column_index = 0

        # Numerical columns

        for column in self.numeric_columns:

            original_values = (
                self.numeric_values[column]
            )

            values = generated[
                :, column_index
            ]

            min_value = np.min(
                original_values
            )

            max_value = np.max(
                original_values
            )

            values = (
                values
                * (max_value - min_value)
                + min_value
            )

            # Add small variation
            std = np.std(
                original_values
            )

            if std > 0:
                values += self.rng.normal(
                    0,
                    std * 0.01,
                    num_rows
                )

            values = np.clip(
                values,
                min_value,
                max_value
            )

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

            values = generated[
                :, column_index
            ]

            values = np.clip(
                values,
                0,
                1
            )

            indices = np.round(
                values
                * (len(categories) - 1)
            ).astype(int)

            synthetic_data[column] = [
                categories[index]
                for index in indices
            ]

            column_index += 1

        # Generate unique identifiers

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