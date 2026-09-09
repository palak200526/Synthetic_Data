from pathlib import Path


ALLOWED_EXTENSIONS = {".csv", ".xls", ".xlsx"}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def validate_file_extension(filename: str) -> None:
    """
    Validate that the uploaded file has a supported extension.
    """

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. "
            "Only CSV, XLS, and XLSX files are allowed."
        )


def validate_file_size(file_size: int) -> None:
    """
    Validate that the uploaded file does not exceed
    the maximum allowed size.
    """

    if file_size <= 0:
        raise ValueError("The uploaded file is empty.")

    if file_size > MAX_FILE_SIZE:
        raise ValueError(
            "File size exceeds the maximum allowed limit of 50 MB."
        )


def validate_filename(filename: str) -> None:
    """
    Validate that a filename is provided.
    """

    if not filename or not filename.strip():
        raise ValueError("Filename cannot be empty.")