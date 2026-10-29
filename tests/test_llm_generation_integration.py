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
            f"The delivery was delayed and the package arrived damaged on attempt {index}."
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
                "The product did not work well for my skin.",
                "The quality was very good and the product worked effectively.",
                "The results were average and did not meet my expectations.",
                "I really liked the product and would recommend it to others.",
                "I was not satisfied because the product did not work as expected.",
                "The product was good quality and provided a pleasant experience.",
                "The product was okay but could be improved further.",
                "It works well and feels comfortable when applied.",
                "I was disappointed because the product did not meet my expectations.",
                "Overall, I had a good experience using this product.",
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
    mock_ready.assert_called_once()

    original_feedback = set(df["feedback"].astype(str))
    assert original_feedback.isdisjoint(set(result["feedback"].astype(str)))


@patch("backend.services.generation_service.ensure_ollama_ready")
@patch("backend.generation.llm_text.ollama_generate")
def test_generate_rows_accepts_llm_text_model(mock_generate, mock_ready):
    # Each invocation returns fresh values. The generator makes multiple calls
    # for different batches and may retry invalid or duplicate outputs.
    call_number = 0

    def mock_llm_response(prompt, **kwargs):
        nonlocal call_number
        call_number += 1
        templates = [
            "A courier delivered the parcel late, and its cardboard carton was crushed.",
            "The item performed reliably and the instructions were easy to follow.",
            "Several components were missing when the customer opened the shipment.",
            "Support staff arranged a replacement after the original product malfunctioned.",
            "The purchase was convenient, although the protective wrapping was inadequate.",
        ]
        return "\n".join(
            f"{templates[(index - 1) % len(templates)]} Reference {call_number}-{index}."
            for index in range(1, 6)
        )

    mock_generate.side_effect = mock_llm_response

    df = pd.DataFrame(
        {
            "customer_feedback": [
                "I enjoyed using this product because it was easy to operate.",
                "The product quality was poor and the packaging was damaged.",
                "The item worked as expected but delivery took several days.",
                "I would purchase this product again because the results were excellent.",
                "The product did not meet my expectations and needs improvement.",
                "The packaging was secure and the item arrived in excellent condition.",
                "The overall experience was average because customer support was slow.",
                "The product performed well and provided good value for the price.",
                "I was disappointed because the item arrived with a broken component.",
                "The product was reliable and the ordering experience was convenient.",
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
            "column_name": "customer_feedback",
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

    assert set(result.columns) == {"customer_feedback", "Sentiment"}
    assert len(result) == 10
    assert mock_generate.call_count >= 1
    mock_ready.assert_called_once()


def test_llm_parameters_do_not_break_tabular_factory():
    generator = get_generator(
        "gaussian_copula",
        llm_text_batch_size=8,
        epochs=50,
        default_distribution="beta",
    )

    assert isinstance(generator, GaussianCopulaGenerator)
