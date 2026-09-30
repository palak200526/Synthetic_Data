import pandas as pd

from backend.generation.gaussian_copula import (
    GaussianCopulaGenerator
)

from backend.generation.validators import (
    validate_synthetic_dataset
)


# Load original dataset
df = pd.read_csv(
    "data/sample_supply_chain/products.csv"
)

print("Original dataset:")
print(df.head())

print("\nOriginal shape:")
print(df.shape)


# Create and fit model
model = GaussianCopulaGenerator(
    random_state=42
)

model.fit(df)


# Generate synthetic records
required_rows = 100

synthetic_df = model.generate(
    num_rows=required_rows
)


print("\nSynthetic dataset:")
print(synthetic_df.head())

print("\nSynthetic shape:")
print(synthetic_df.shape)

print("\nSynthetic columns:")
print(synthetic_df.columns.tolist())

print("\nSynthetic data types:")
print(synthetic_df.dtypes)


# Validate generated dataset
validation_result = validate_synthetic_dataset(
    original_df=df,
    synthetic_df=synthetic_df,
    required_rows=required_rows
)

print("\nValidation result:")
print(validation_result)