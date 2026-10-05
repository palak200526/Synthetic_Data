from unittest.mock import patch

import pandas as pd

from backend.generation.generator_factory import get_generator
from backend.generation.gaussian_copula import GaussianCopulaGenerator
from backend.services.generation_service import generate_rows


@patch("backend.services.generation_service.ensure_ollama_ready")
@patch("backend.generation.llm_text.ollama_generate")
def test_generate_rows_uses_copula_then_mocked_llm(mock_generate, mock_ready):
    mock_generate.side_effect = lambda prompt, **kwargs: "\n".join(
        [
            f"Delivery was delayed and the box was dented {index}"
            for index in range(10)
        ]
    )

    df = pd.DataFrame(
        {
            "product": [
                "Shampoo",
                "Face Wash",
                "Body Lotion",
                "Conditioner",
                "Soap",
                "Moisturizer",
                "Hair Oil",
                "Cleanser",
                "Sunscreen",
                "Serum",
            ],
            "rating": [2, 4, 3, 5, 2, 4, 3, 5, 2, 4],
            "feedback": [
                "The product did not work well.",
                "Very good quality and effective.",
                "The results were average.",
                "I really liked the product.",
                "Not satisfied with the results.",
                "Good product and nice experience.",
                "The product was okay.",
                "Works well and feels good.",
                "I was not happy with the product.",
                "Overall a good experience.",
            ],
        }
    )

    configurations = [
        {
            "dataset_id": 1,
            "column_name": "product",
            "column_type": "string",
            "is_identifier": False,
            "action": "keep",
        },
        {
            "dataset_id": 1,
            "column_name": "rating",
            "column_type": "integer",
            "is_identifier": False,
            "action": "keep",
        },
        {
            "dataset_id": 1,
            "column_name": "feedback",
            "column_type": "string",
            "is_identifier": False,
            "action": "llm",
        },
    ]

    result = generate_rows(
        original_dataframe=df,
        configurations=configurations,
        model_name="gaussian_copula",
        num_rows=10,
        parameters={"llm_text_batch_size": 5},
    )

    assert list(result.columns) == ["product", "rating", "feedback"]
    assert len(result) == 10
    assert mock_generate.call_count >= 1
    assert mock_ready.called
    original_feedback = set(df["feedback"].astype(str))
    assert original_feedback.isdisjoint(set(result["feedback"].astype(str)))


@patch("backend.services.generation_service.ensure_ollama_ready")
@patch("backend.generation.llm_text.ollama_generate")
def test_generate_rows_accepts_llm_text_model(mock_generate, mock_ready):
    mock_generate.side_effect = lambda prompt, **kwargs: "\n".join(
        [f"Synthetic review {index}" for index in range(10)]
    )

    df = pd.DataFrame(
        {
            "Text": [
                "Loved it",
                "Terrible quality",
                "Okay product",
                "Would buy again",
                "Not for me",
                "Excellent",
                "Average",
                "Pretty good",
                "Disappointed",
                "Fantastic",
            ],
            "Sentiment": [
                "Positive",
                "Negative",
                "Neutral",
                "Positive",
                "Negative",
                "Positive",
                "Neutral",
                "Positive",
                "Negative",
                "Positive",
            ],
        }
    )
    configurations = [
        {
            "dataset_id": 1,
            "column_name": "Text",
            "column_type": "string",
            "is_identifier": False,
            "action": "llm",
        },
        {
            "dataset_id": 1,
            "column_name": "Sentiment",
            "column_type": "string",
            "is_identifier": False,
            "action": "keep",
        },
    ]

    result = generate_rows(
        original_dataframe=df,
        configurations=configurations,
        model_name="llm_text",
        num_rows=10,
        parameters={"llm_text_batch_size": 5},
    )

    assert list(result.columns) == ["Sentiment", "Text"]
    assert len(result) == 10
    assert mock_generate.call_count >= 1


def test_llm_parameters_do_not_break_tabular_factory():
    generator = get_generator(
        "gaussian_copula",
        llm_text_batch_size=8,
        epochs=50,
        default_distribution="beta",
    )
    assert isinstance(generator, GaussianCopulaGenerator)
