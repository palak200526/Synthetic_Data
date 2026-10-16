from contextlib import contextmanager

import numpy as np
import pandas as pd
import torch

MISSING_TOKEN = "__MISSING__"


@contextmanager
def _epoch_progress(module, callback, epochs: int):
    """ctgan me epoch callback nahi hota, wo tqdm(range(epochs)) use karta hai.
    Hum us tqdm ko temporarily badal ke har epoch ke baad callback bulate hain."""
    if callback is None or not hasattr(module, "tqdm"):
        yield
        return
    original = module.tqdm

    def _reporting_tqdm(iterable, *args, **kwargs):
        for index, item in enumerate(iterable, start=1):
            yield item
            callback(index, epochs)

    module.tqdm = _reporting_tqdm
    try:
        yield
    finally:
        module.tqdm = original


class LibraryTabularGenerator:
    _progress_module = None

    def __init__(self, epochs=100, random_state=42):
        self.epochs = int(epochs)
        self.random_state = int(random_state)
        self.columns = None
        self.numeric_columns = []
        self.categorical_columns = []
        self.identifier_columns = []
        self.original_dtypes = {}
        self.numeric_bounds = {}
        self.model = None

    def _build_model(self):
        raise NotImplementedError

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
            series = model_df[column]
            median = series.median()
            model_df[column] = series.fillna(0 if pd.isna(median) else median)
            self.numeric_bounds[column] = (
                float(model_df[column].min()),
                float(model_df[column].max()),
            )

        for column in self.categorical_columns:
            model_df[column] = (
                model_df[column].astype("object")
                .where(model_df[column].notna(), MISSING_TOKEN)
                .astype(str)
            )

        torch.manual_seed(self.random_state)
        np.random.seed(self.random_state)

        self.model = self._build_model()
        with _epoch_progress(self._progress_module, progress_callback, self.epochs):
            self.model.fit(model_df, discrete_columns=self.categorical_columns)
        return self

    def generate(self, num_rows: int) -> pd.DataFrame:
        if self.model is None:
            raise RuntimeError("Model has not been fitted. Call fit() first.")
        if num_rows <= 0:
            raise ValueError("num_rows must be greater than zero.")

        synthetic = self.model.sample(int(num_rows)).reset_index(drop=True)

        for column in self.numeric_columns:
            low, high = self.numeric_bounds[column]
            values = synthetic[column].clip(low, high)
            dtype = self.original_dtypes[column]
            if pd.api.types.is_integer_dtype(dtype):
                values = np.round(values).astype(dtype)
            synthetic[column] = values

        for column in self.categorical_columns:
            synthetic[column] = synthetic[column].where(synthetic[column] != MISSING_TOKEN, np.nan)

        # Placeholder IDs; service layer inhe new_id action se replace kar deti hai.
        for column in self.identifier_columns:
            synthetic[column] = [f"{column}_{i:06d}" for i in range(1, num_rows + 1)]

        return synthetic[self.columns]