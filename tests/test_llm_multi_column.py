from unittest.mock import patch

import pandas as pd

from backend.services.generation_service import _generate_llm_columns


@patch("backend.services.generation_service.ensure_ollama_ready")
@patch("backend.generation.llm_text.ollama_generate")
def test_multiple_llm_columns_fill_synthetic_rows(mock_generate, mock_ready):
    original_df = pd.DataFrame(
        {
            "age": [22, 31, 27, 45, 36],
            "rating": [4, 2, 5, 3, 4],
            "customer_name": [
                "Ananya Sharma",
                "Rahul Mehta",
                "Priya Kapoor",
                "Arjun Verma",
                "Neha Gupta",
            ],
            "complaint": [
                "The product did not work as expected.",
                "The fragrance was too strong.",
                "The packaging was damaged.",
                "The product caused dryness.",
                "I was not satisfied with the results.",
            ],
        }
    )
    synthetic_df = pd.DataFrame(
        {
            "age": [28, 35, 24],
            "rating": [5, 2, 4],
        }
    )
    configurations = [
        {"column_name": "customer_name", "column_type": "string", "action": "llm"},
        {"column_name": "complaint", "column_type": "string", "action": "llm"},
    ]

    column_calls = {"customer_name": 0, "complaint": 0}

    def _fake(prompt, **kwargs):
        if "Column: customer_name" in prompt:
            column_calls["customer_name"] += 1
            return "\n".join(
                ["Ishaan Reddy", "Meera Nair", "Kabir Joshi", "Diya Malhotra"]
            )
        column_calls["complaint"] += 1
        return "\n".join(
            [
                "The pump stopped working after a week",
                "The lotion separated in the bottle",
                "The lid cracked during shipping",
                "The color stained my towel",
            ]
        )

    mock_generate.side_effect = _fake

    result = _generate_llm_columns(
        original_dataframe=original_df,
        synthetic_dataframe=synthetic_df,
        configurations=configurations,
        llm_kwargs={"batch_size": 4, "skip_health_check": True},
    )

    assert len(result) == 3
    assert list(result["customer_name"]) == [
        "Ishaan Reddy",
        "Meera Nair",
        "Kabir Joshi",
    ]
    assert "The product did not work as expected." not in set(result["complaint"])
    assert column_calls["customer_name"] >= 1
    assert column_calls["complaint"] >= 1
    assert mock_ready.called
