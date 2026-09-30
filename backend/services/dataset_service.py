from pathlib import Path
from datetime import datetime
import uuid

from backend.services.dataset_loader import (
    load_dataset,
    get_dataset_metadata,
)

from backend.utils.validators import (
    validate_filename,
    validate_file_extension,
    validate_file_size,
)

from backend.repositories.session_repository import (
    create_processing_session,
)

from backend.repositories.dataset_repository import (
    create_dataset,
)


UPLOAD_DIRECTORY = Path("data/uploads")


async def upload_dataset(
    file,
    group_id=None,
    domain_type=None,
    session_id=None,
    user_id=None
):
    # ---------------------------------------------------------
    # 1. Validate uploaded file
    # ---------------------------------------------------------
    validate_filename(file.filename)
    validate_file_extension(file.filename)

    file_content = await file.read()

    validate_file_size(
        len(file_content)
    )

    # Keep only the actual filename
    original_filename = Path(file.filename).name

    # ---------------------------------------------------------
    # 2. Create date-wise upload directory
    # ---------------------------------------------------------
    upload_date = datetime.now()

    date_directory = (
        UPLOAD_DIRECTORY
        / str(upload_date.year)
        / f"{upload_date.month:02d}"
        / f"{upload_date.day:02d}"
    )

    date_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    # ---------------------------------------------------------
    # 3. Save temporary file
    #
    # Dataset ID does not exist yet, so use a temporary name.
    # ---------------------------------------------------------
    temporary_filename = (
        f"uploading_{uuid.uuid4().hex}_{original_filename}"
    )

    temporary_path = (
        date_directory / temporary_filename
    )

    with open(
        temporary_path,
        "wb"
    ) as output_file:

        output_file.write(file_content)

    try:

        # -----------------------------------------------------
        # 4. Load dataset from temporary file
        # -----------------------------------------------------
        dataframe = load_dataset(
            str(temporary_path)
        )

        metadata = get_dataset_metadata(
            dataframe,
            original_filename
        )

        # -----------------------------------------------------
        # 5. Create processing session if required
        # -----------------------------------------------------
        if session_id is None:
            session_id = create_processing_session()

        # -----------------------------------------------------
        # 6. Create dataset record
        #
        # This gives us the unique dataset_id.
        # -----------------------------------------------------
        dataset_id = create_dataset(
            original_filename,
            len(dataframe),
            len(dataframe.columns),
            session_id,
            group_id,
            domain_type,
            user_id
        )

        # -----------------------------------------------------
        # 7. Rename file using dataset_id
        # -----------------------------------------------------
        final_filename = (
            f"dataset_{dataset_id}_{original_filename}"
        )

        final_path = (
            date_directory / final_filename
        )

        temporary_path.rename(
            final_path
        )

        # Convert Windows Path to a consistent string
        file_path = final_path.as_posix()

        # -----------------------------------------------------
        # 8. Return upload information
        # -----------------------------------------------------
        return {
            "status": "success",
            "message": "Dataset uploaded successfully.",
            "dataset_id": dataset_id,
            "session_id": session_id,
            "group_id": group_id,
            "domain_type": domain_type,
            "file_name": original_filename,
            "stored_file_name": final_filename,
            "file_path": file_path,
            "upload_date": upload_date.isoformat(),
            "data": metadata,
        }

    except Exception:

        # Remove temporary file if anything fails
        if temporary_path.exists():
            temporary_path.unlink()

        raise