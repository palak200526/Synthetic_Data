import pytest

from backend.repositories.session_repository import (
    create_processing_session,
)

from backend.repositories.dataset_repository import (
    create_dataset,
    get_dataset_id_by_filename,
    get_dataset_filename,
    save_dataset_profile,
)


def test_create_processing_session():

    session_id = create_processing_session()

    assert session_id is not None
    assert isinstance(session_id, int)


def test_multiple_sessions_have_unique_ids():

    session_id_1 = create_processing_session()
    session_id_2 = create_processing_session()

    assert session_id_1 != session_id_2


def test_dataset_is_linked_to_session():

    session_id = create_processing_session()

    dataset_id = create_dataset(
        "persistence_test.csv",
        3,
        3,
        session_id,
    )

    assert dataset_id is not None

    retrieved_dataset_id = get_dataset_id_by_filename(
        "persistence_test.csv"
    )

    assert retrieved_dataset_id == dataset_id


def test_dataset_metadata_is_stored():

    session_id = create_processing_session()

    dataset_id = create_dataset(
        "metadata_test.csv",
        100,
        5,
        session_id,
    )

    filename = get_dataset_filename(dataset_id)

    assert filename == "metadata_test.csv"


def test_profile_is_persisted():

    session_id = create_processing_session()

    dataset_id = create_dataset(
        "profile_persistence.csv",
        3,
        3,
        session_id,
    )

    profile_data = {
        "basic": {
            "row_count": 3,
            "column_count": 3,
        },
        "column_types": {
            "numerical_columns": ["age"],
            "categorical_columns": ["gender"],
        },
    }

    result = save_dataset_profile(
        dataset_id,
        profile_data,
    )

    assert result["profile_id"] is not None
    assert result["dataset_id"] == dataset_id


def test_profile_is_linked_to_correct_dataset():

    session_id = create_processing_session()

    dataset_id_1 = create_dataset(
        "dataset_one.csv",
        10,
        4,
        session_id,
    )

    dataset_id_2 = create_dataset(
        "dataset_two.csv",
        20,
        5,
        session_id,
    )

    profile_1 = save_dataset_profile(
        dataset_id_1,
        {"rows": 10},
    )

    profile_2 = save_dataset_profile(
        dataset_id_2,
        {"rows": 20},
    )

    assert profile_1["dataset_id"] == dataset_id_1
    assert profile_2["dataset_id"] == dataset_id_2
    assert profile_1["dataset_id"] != profile_2["dataset_id"]


def test_nonexistent_dataset_filename_raises_error():

    with pytest.raises(ValueError):

        get_dataset_id_by_filename(
            "does_not_exist.csv"
        )


def test_nonexistent_dataset_id_raises_error():

    with pytest.raises(ValueError):

        get_dataset_filename(999999999)


def test_dataset_row_and_column_metadata():

    session_id = create_processing_session()

    dataset_id = create_dataset(
        "large_dataset.csv",
        500,
        24,
        session_id,
    )

    assert dataset_id is not None

    filename = get_dataset_filename(dataset_id)

    assert filename == "large_dataset.csv"


def test_profile_can_store_complex_data():

    session_id = create_processing_session()

    dataset_id = create_dataset(
        "complex_profile.csv",
        5,
        4,
        session_id,
    )

    profile_data = {
        "basic": {
            "row_count": 5,
            "column_count": 4,
        },
        "missing_values": {
            "age": 1,
            "income": 0,
        },
        "numerical_statistics": {
            "age": {
                "mean": 25.5,
                "min": 20,
                "max": 30,
            },
        },
        "sensitive_detection": [
            {
                "column_name": "email",
                "is_sensitive": True,
                "is_identifier": False,
            }
        ],
    }

    result = save_dataset_profile(
        dataset_id,
        profile_data,
    )

    assert result["profile_id"] is not None
    assert result["dataset_id"] == dataset_id