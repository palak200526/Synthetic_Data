"""Regression tests for avoiding LLM text generation on categorical columns."""
from backend.services.smart_column_filter import (
    is_freeform_text_profile,
    is_obvious_column,
)


def test_reason_column_with_repeated_identifier_and_many_nulls_is_not_llm_text():
    profile = {
        "column_name": "Reason",
        "dtype": "string",
        "row_count": 11,
        "unique_count": 1,
        "unique_ratio": 0.091,
        "null_count": 7,
        "null_ratio": 0.636,
        "sample_values": ["identifier", "identifier", "identifier", "identifier"],
        "string_length": {"average": 10, "min": 10, "max": 10},
        "patterns": [],
    }

    assert is_freeform_text_profile(profile) is False
    recommendation = is_obvious_column(profile)
    assert recommendation is not None
    assert recommendation["action"] == "remove"


def test_short_controlled_labels_are_not_llm_text():
    profile = {
        "column_name": "Status",
        "dtype": "object",
        "row_count": 100,
        "unique_count": 3,
        "unique_ratio": 0.03,
        "null_ratio": 0,
        "sample_values": ["open", "closed", "pending"],
        "string_length": {"average": 6, "min": 4, "max": 7},
        "patterns": [],
    }
    assert is_freeform_text_profile(profile) is False


def test_actual_free_form_reason_sentences_can_use_llm_text():
    profile = {
        "column_name": "Reason",
        "dtype": "object",
        "row_count": 100,
        "unique_count": 85,
        "unique_ratio": 0.85,
        "null_ratio": 0.02,
        "sample_values": [
            "Shipment was delayed because the supplier missed the dispatch window.",
            "The item arrived damaged during transport and needs replacement.",
            "Inventory was unavailable when the customer order was confirmed.",
        ],
        "string_length": {"average": 62, "min": 50, "max": 80},
        "patterns": [],
    }
    assert is_freeform_text_profile(profile) is True
    recommendation = is_obvious_column(profile)
    assert recommendation is not None
    assert recommendation["action"] == "llm"
