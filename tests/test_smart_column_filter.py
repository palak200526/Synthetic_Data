from backend.services.smart_column_filter import (
    is_freeform_text_profile,
    is_obvious_column,
)


def test_freeform_feedback_column_is_recommended_llm():
    profile = {
        "column_name": "feedback",
        "dtype": "object",
        "unique_ratio": 0.9,
        "null_ratio": 0.0,
        "unique_count": 50,
        "string_length": {"average": 42},
        "patterns": [],
    }
    assert is_freeform_text_profile(profile) is True
    recommendation = is_obvious_column(profile)
    assert recommendation["action"] == "llm"
    assert recommendation["is_identifier"] is False


def test_text_column_is_recommended_llm():
    profile = {
        "column_name": "Text",
        "dtype": "object",
        "unique_ratio": 0.98,
        "null_ratio": 0.0,
        "unique_count": 200,
        "string_length": {"average": 64},
        "patterns": [],
    }
    assert is_freeform_text_profile(profile) is True
    recommendation = is_obvious_column(profile)
    assert recommendation["action"] == "llm"
    assert recommendation["is_identifier"] is False


def test_email_and_id_columns_are_not_llm_text():
    email_profile = {
        "column_name": "email",
        "dtype": "object",
        "unique_ratio": 1.0,
        "null_ratio": 0.0,
        "unique_count": 100,
        "string_length": {"average": 24},
        "patterns": ["email"],
    }
    assert is_freeform_text_profile(email_profile) is False

    id_profile = {
        "column_name": "user_id",
        "dtype": "object",
        "unique_ratio": 1.0,
        "null_ratio": 0.0,
        "unique_count": 100,
        "string_length": {"average": 12},
        "patterns": [],
    }
    recommendation = is_obvious_column(id_profile)
    assert recommendation["action"] == "new_id"
