from pathlib import Path

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
    session_id=None
):

    validate_filename(file.filename)
    validate_file_extension(file.filename)

    file_content = await file.read()

    validate_file_size(
        len(file_content)
    )

    file_path = UPLOAD_DIRECTORY / file.filename

    with open(file_path, "wb") as output_file:
        output_file.write(file_content)

    dataframe = load_dataset(
        str(file_path)
    )

    metadata = get_dataset_metadata(
        dataframe,
        file.filename
    )

    if session_id is None:
        session_id = create_processing_session()

    dataset_id = create_dataset(
        file.filename,
        len(dataframe),
        len(dataframe.columns),
        session_id,
        group_id,
        domain_type
    )
    
    return {
        "status": "success",
        "message": "Dataset uploaded successfully.",
        "dataset_id": dataset_id,
        "session_id": session_id,
        "group_id": group_id,
        "domain_type": domain_type,
        "data": metadata,
    }