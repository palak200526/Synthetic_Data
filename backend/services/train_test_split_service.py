import pandas as pd
from sklearn.model_selection import train_test_split


def create_train_test_split(
    dataframe: pd.DataFrame,
    test_size: float = 0.2,
    random_state: int = 42,
):
    if dataframe.empty:
        raise ValueError("Dataset cannot be empty.")

    if not 0 < test_size < 1:
        raise ValueError("test_size must be between 0 and 1.")

    train_dataframe, test_dataframe = train_test_split(
        dataframe,
        test_size=test_size,
        random_state=random_state,
    )

    return {
        "train_dataframe": train_dataframe,
        "test_dataframe": test_dataframe,
        "test_size": test_size,
        "random_state": random_state,
    }