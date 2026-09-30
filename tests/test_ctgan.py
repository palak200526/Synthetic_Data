import pandas as pd

from backend.generation.ctgan import CTGANGenerator
from backend.generation.validators import (
    validate_synthetic_dataset
)

# Load original dataset


df = pd.read_csv(
    "data/sample_supply_chain/products.csv"
)

print("Original shape:")
print(df.shape)


# Train CTGAN

print("\nTraining CTGAN...")

model = CTGANGenerator(
    epochs=50,
    batch_size=32,
    learning_rate=0.0002,
    random_state=42
)

model.fit(df)

print("Training completed.")


# Generate synthetic data

synthetic_df = model.generate(
    num_rows=100
)

print("\nSynthetic dataset:")
print(synthetic_df.head())

print("\nSynthetic shape:")
print(synthetic_df.shape)

print("\nSynthetic columns:")
print(synthetic_df.columns.tolist())

print("\nSynthetic data types:")
print(synthetic_df.dtypes)


# Validate output

validation_result = validate_synthetic_dataset(
    original_df=df,
    synthetic_df=synthetic_df,
    required_rows=100
)

print("\nValidation result:")
print(validation_result)


# Check identifier uniqueness

print("\nProduct ID unique:")
print(
    synthetic_df["product_id"].is_unique
)


# Numerical distribution sanity check

original_cost = df["standard_cost"]

synthetic_cost = synthetic_df["standard_cost"]

print("\nOriginal standard_cost statistics:")
print(original_cost.describe())

print("\nSynthetic standard_cost statistics:")
print(synthetic_cost.describe())

print("\nSynthetic standard_cost unique values:")
print(synthetic_cost.nunique())
