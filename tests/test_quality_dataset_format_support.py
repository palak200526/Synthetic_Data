from pathlib import Path

import pandas as pd
import pytest

from backend.services.dataset_loader import load_dataset


def test_quality_input_loader_supports_csv(tmp_path: Path):
    path = tmp_path / "generic_dataset.csv"
    pd.DataFrame({"amount": [10, 20], "category": ["A", "B"]}).to_csv(path, index=False)

    result = load_dataset(str(path))

    assert result.shape == (2, 2)
    assert result.columns.tolist() == ["amount", "category"]


def test_quality_input_loader_supports_excel(tmp_path: Path):
    pytest.importorskip("openpyxl")
    path = tmp_path / "generic_dataset.xlsx"
    pd.DataFrame({"amount": [10, 20], "category": ["A", "B"]}).to_excel(path, index=False)

    result = load_dataset(str(path))

    assert result.shape == (2, 2)
    assert result.columns.tolist() == ["amount", "category"]


def test_quality_input_loader_rejects_unsupported_file(tmp_path: Path):
    path = tmp_path / "generic_dataset.json"
    path.write_text('{"amount": 10}', encoding="utf-8")

    with pytest.raises(ValueError, match="Unable to read the dataset|Unsupported file type"):
        load_dataset(str(path))
