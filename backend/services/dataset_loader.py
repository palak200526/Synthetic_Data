from pathlib import Path
import pandas as pd


def load_dataset(file_path: str) -> pd.DataFrame:
    """
    Load a CSV or Excel dataset into a pandas DataFrame.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Dataset file not found: {file_path}"
        )

    extension = path.suffix.lower()

    try:

        if extension == ".csv":
            dataframe = pd.read_csv(path)

        elif extension in {".xls", ".xlsx"}:
            dataframe = pd.read_excel(path)

        else:
            raise ValueError(
                "Unsupported file type."
            )

    except Exception as error:
        raise ValueError(
            f"Unable to read the dataset: {error}"
        ) from error

    if dataframe.empty:
        raise ValueError(
            "The uploaded dataset is empty."
        )

    return dataframe


def get_dataset_metadata(
    dataframe: pd.DataFrame,
    filename: str
) -> dict:
    """
    Generate basic metadata for the uploaded dataset.
    """

    return {
        "filename": filename,
        "rows": len(dataframe),
        "columns": len(dataframe.columns),
        "column_names": dataframe.columns.tolist(),
    }