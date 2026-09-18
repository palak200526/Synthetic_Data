import pandas as pd
import pytest

from backend.services.train_test_split_service import (
    create_train_test_split,
)


def test_create_train_test_split():
    dataframe = pd.DataFrame({
        "price": range(100),
        "quantity": range(100, 200),
    })

    result = create_train_test_split(
        dataframe,
        test_size=0.2,
        random_state=42,
    )

    assert len(result["train_dataframe"]) == 80
    assert len(result["test_dataframe"]) == 20


def test_train_test_split_preserves_total_rows():
    dataframe = pd.DataFrame({
        "price": range(50),
        "quantity": range(50, 100),
    })

    result = create_train_test_split(dataframe)

    total_rows = (
        len(result["train_dataframe"])
        + len(result["test_dataframe"])
    )

    assert total_rows == len(dataframe)


def test_train_test_split_is_reproducible():
    dataframe = pd.DataFrame({
        "price": range(50),
        "quantity": range(50, 100),
    })

    result_1 = create_train_test_split(
        dataframe,
        test_size=0.2,
        random_state=42,
    )

    result_2 = create_train_test_split(
        dataframe,
        test_size=0.2,
        random_state=42,
    )

    assert result_1["train_dataframe"].equals(
        result_2["train_dataframe"]
    )

    assert result_1["test_dataframe"].equals(
        result_2["test_dataframe"]
    )


def test_train_test_split_rejects_empty_dataset():
    dataframe = pd.DataFrame()

    with pytest.raises(ValueError):
        create_train_test_split(dataframe)


def test_train_test_split_rejects_invalid_test_size():
    dataframe = pd.DataFrame({
        "price": [100, 200, 300],
    })

    with pytest.raises(ValueError):
        create_train_test_split(
            dataframe,
            test_size=1.5,
        )