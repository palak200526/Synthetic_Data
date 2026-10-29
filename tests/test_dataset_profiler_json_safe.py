import json
import numpy as np
import pandas as pd

from backend.services.dataset_profiler import generate_profile


def test_profile_of_fully_blank_numeric_column_is_strict_json_safe():
    df = pd.DataFrame({
        "amount": [np.nan, np.nan, np.nan],
        "category": ["A", "B", "A"],
    })

    profile = generate_profile(df)
    encoded = json.dumps(profile, allow_nan=False)

    assert encoded
    amount_profile = next(
        c for c in profile["columns"] if c["column_name"] == "amount"
    )
    assert amount_profile["statistics"] == {
        "min": None, "max": None, "mean": None, "median": None, "std": None
    }
    assert profile["numerical_statistics"]["amount"]["mean"] is None
