import pandas as pd

from backend.generation.tvae import TVAEGenerator
from backend.generation.validators import (
    validate_synthetic_dataset
)


df = pd.read_csv(
    "data/sample_supply_chain/products.csv"
)

print("Original shape:")
print(df.shape)

print("\nTraining TVAE...")

model = TVAEGenerator(
    latent_dim=16,
    epochs=50,
    batch_size=32,
    learning_rate=0.001,
    random_state=42
)

model.fit(df)

print("Training completed.")

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


validation_result = validate_synthetic_dataset(
    original_df=df,
    synthetic_df=synthetic_df,
    required_rows=100
)

print("\nValidation result:")
print(validation_result)


print("\nProduct ID unique:")
print(
    synthetic_df["product_id"].is_unique
)


print("\nOriginal standard_cost statistics:")
print(
    df["standard_cost"].describe()
)


print("\nSynthetic standard_cost statistics:")
print(
    synthetic_df["standard_cost"].describe()
)


print("\nSynthetic standard_cost unique values:")
print(
    synthetic_df["standard_cost"].nunique()
)