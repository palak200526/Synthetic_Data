import pandas as pd

from backend.generation.generator_factory import (
    get_generator
)
from backend.generation.validators import (
    validate_synthetic_dataset
)


df = pd.read_csv(
    "data/sample_supply_chain/products.csv"
)


def test_model_selection(model_name, **kwargs):

    print(f"\n{'=' * 50}")
    print(f"Testing {model_name.upper()}")
    print(f"{'=' * 50}")

    generator = get_generator(
        model_name,
        **kwargs
    )

    print("Generator selected:")
    print(type(generator).__name__)

    generator.fit(df)

    print("Training completed.")

    synthetic_df = generator.generate(
        num_rows=100
    )

    print("\nSynthetic shape:")
    print(synthetic_df.shape)

    print("\nColumns:")
    print(
        synthetic_df.columns.tolist()
    )

    validation = validate_synthetic_dataset(
        original_df=df,
        synthetic_df=synthetic_df,
        required_rows=100
    )

    print("\nValidation:")
    print(validation)

    print("\nProduct ID unique:")
    print(
        synthetic_df["product_id"].is_unique
    )

    assert validation["valid"] is True

    assert synthetic_df.shape == (100, 7)

    assert (
        synthetic_df.columns.tolist()
        == df.columns.tolist()
    )

    assert synthetic_df["product_id"].is_unique


# 1. Gaussian Copula

print("\nTesting Gaussian Copula...")

test_model_selection(
    "gaussian_copula",
    random_state=42
)


# 2. CTGAN
print("\nTesting CTGAN...")

test_model_selection(
    "ctgan",
    epochs=50,
    batch_size=32,
    learning_rate=0.0002,
    random_state=42
)


# 3. TVAE

print("\nTesting TVAE...")

test_model_selection(
    "tvae",
    latent_dim=16,
    epochs=50,
    batch_size=32,
    learning_rate=0.001,
    random_state=42
)


print("\n" + "=" * 50)
print("ALL THREE GENERATION MODELS PASSED")
print("=" * 50)