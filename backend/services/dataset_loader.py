from csv import Error as CsvError
from csv import Sniffer
from io import StringIO
from pathlib import Path

import pandas as pd


_CSV_DELIMITERS = ",;\t|"
_ENCODINGS = ("utf-8-sig", "utf-8", "utf-16", "latin-1")


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
            dataframe = _load_csv(path)

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

    dataframe.columns = [
        str(column).strip()
        for column in dataframe.columns
    ]
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

import csv
from io import StringIO
from pathlib import Path

import pandas as pd


def _load_csv(path: Path) -> pd.DataFrame:
    """
    Load CSV files including files where the entire row is
    wrapped inside an extra pair of quotes.
    """

    text = _read_text(path)

    if not text.strip():
        raise ValueError("CSV file is empty.")

    lines = [
        line for line in text.splitlines()
        if line.strip()
    ]

    # ---------------------------------------------------------
    # Detect CSV where the COMPLETE row is wrapped in quotes
    # ---------------------------------------------------------
    if lines:
        first_line = lines[0].strip()

        if (
            first_line.startswith('"')
            and first_line.endswith('"')
        ):
            try:
                # First CSV parsing removes the outer quotation layer.
                unwrapped_lines = []

                for line in lines:
                    outer_reader = csv.reader(
                        [line],
                        quotechar='"',
                        doublequote=True
                    )

                    values = next(outer_reader)

                    if len(values) == 1:
                        unwrapped_lines.append(values[0])
                    else:
                        # If it wasn't actually one wrapped field,
                        # keep the original line.
                        unwrapped_lines.append(line)

                cleaned_text = "\n".join(unwrapped_lines)

                # Parse the actual CSV inside the wrapper.
                dataframe = pd.read_csv(
                    StringIO(cleaned_text),
                    sep=",",
                    quotechar='"',
                    doublequote=True,
                    skipinitialspace=True,
                    engine="python",
                )

                print("CSV DEBUG - wrapped CSV detected")
                print("CSV DEBUG - shape:", dataframe.shape)
                print("CSV DEBUG - columns:", dataframe.columns.tolist())

                if dataframe.shape[1] > 1:
                    return dataframe

            except Exception as error:
                print(
                    "Wrapped CSV parsing failed:",
                    repr(error)
                )

    # ---------------------------------------------------------
    # Normal CSV fallback
    # ---------------------------------------------------------
    for delimiter in [",", ";", "\t", "|"]:
        try:
            dataframe = pd.read_csv(
                StringIO(text),
                sep=delimiter,
                quotechar='"',
                doublequote=True,
                skipinitialspace=True,
                engine="python",
            )

            print(
                f"CSV DEBUG - delimiter {delimiter!r}:",
                dataframe.shape
            )

            if dataframe.shape[1] > 1:
                return dataframe

        except Exception as error:
            print(
                f"CSV parse failed for delimiter {delimiter!r}:",
                repr(error)
            )

    raise ValueError(
        "Unable to parse the CSV file."
    )

def _unwrap_fully_quoted_lines(text: str) -> str:
    """
    Handle CSV files where a complete row is wrapped in quotes.

    Example:
    "Text,Sentiment,Source,Date/Time,User ID,Location,Confidence Score"

    becomes:
    Text,Sentiment,Source,Date/Time,User ID,Location,Confidence Score
    """

    lines = text.splitlines()

    if not lines:
        return text

    result = []

    for line in lines:
        stripped = line.strip()

        if (
            len(stripped) >= 2
            and stripped.startswith('"')
            and stripped.endswith('"')
        ):
            # Remove only the first and last quote.
            line = stripped[1:-1]

        result.append(line)

    return "\n".join(result)

def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    if not raw:
        raise ValueError("The uploaded dataset is empty.")

    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")

    for encoding in _ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    return raw.decode("utf-8", errors="replace")


def _unwrap_fully_quoted_lines(text: str) -> str:
    """
    Excel sometimes saves an entire row as one quoted cell:
    "Text, Sentiment, Source, ..."
    Strip those wrapping quotes so the real delimiter can be detected.
    """

    lines = text.splitlines()
    if not lines:
        return text

    sample = [line.strip() for line in lines[:30] if line.strip()]
    if not sample:
        return text

    fully_quoted = 0
    for line in sample:
        if (
            len(line) >= 2
            and line.startswith('"')
            and line.endswith('"')
            and line.count('"') == 2
        ):
            fully_quoted += 1

    if fully_quoted < max(1, int(len(sample) * 0.8)):
        return text

    unwrapped = []
    for line in lines:
        stripped = line.strip()
        if (
            len(stripped) >= 2
            and stripped.startswith('"')
            and stripped.endswith('"')
            and stripped.count('"') == 2
        ):
            unwrapped.append(stripped[1:-1].replace('""', '"'))
        else:
            unwrapped.append(line)
    return "\n".join(unwrapped)


def _delimiter_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    sample = "\n".join(text.splitlines()[:40])
    try:
        dialect = Sniffer().sniff(sample, delimiters=_CSV_DELIMITERS)
        if dialect.delimiter:
            candidates.append(dialect.delimiter)
    except CsvError:
        pass

    for separator in [",", ";", "\t", "|"]:
        if separator not in candidates:
            candidates.append(separator)
    return candidates


def _csv_parse_score(dataframe: pd.DataFrame) -> int:
    if dataframe is None or dataframe.empty:
        return -1

    column_count = int(dataframe.shape[1])
    unnamed = sum(
        str(column).lower().startswith("unnamed")
        for column in dataframe.columns
    )
    return column_count * 10 - unnamed
