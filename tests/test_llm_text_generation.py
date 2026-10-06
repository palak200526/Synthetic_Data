from unittest.mock import patch

import pytest

from backend.generation.llm_text import (
    LLMTextGenerator,
    infer_column_purpose,
    is_too_similar,
    parse_llm_output,
)


def _generator(**kwargs) -> LLMTextGenerator:
    defaults = {
        "batch_size": 4,
        "timeout": 5,
        "max_retries": 3,
        "similarity_threshold": 0.92,
        "skip_health_check": True,
    }
    defaults.update(kwargs)
    return LLMTextGenerator(**defaults)


def test_parse_numbered_list_and_bullets():
    raw = """
    Here are the values:
    1. Delayed shipping on my last order
    2. The bottle leaked during transit
    - Fragrance faded after two days
    """
    parsed = parse_llm_output(raw)
    assert parsed == [
        "Delayed shipping on my last order",
        "The bottle leaked during transit",
        "Fragrance faded after two days",
    ]


def test_parse_json_object_and_array():
    as_object = '{"values": ["First synthetic comment", "Second synthetic comment"]}'
    as_array = '["Third synthetic comment", "Fourth synthetic comment"]'
    assert parse_llm_output(as_object) == [
        "First synthetic comment",
        "Second synthetic comment",
    ]
    assert parse_llm_output(as_array) == [
        "Third synthetic comment",
        "Fourth synthetic comment",
    ]


def test_parse_skips_malformed_and_empty():
    assert parse_llm_output("") == []
    assert parse_llm_output("   ") == []
    assert parse_llm_output("Sure, I can help with that.") == []


def test_is_too_similar_detects_exact_and_near_copies():
    sources = ["The product did not work well."]
    assert is_too_similar("The product did not work well.", sources, 0.92)
    assert is_too_similar("the product did not work well.", sources, 0.92)
    assert not is_too_similar(
        "Delivery was late and the seal was broken.",
        sources,
        0.92,
    )


def test_infer_column_purpose_from_name_and_length():
    assert infer_column_purpose("customer_feedback", {}, []) == (
        "free-form customer feedback"
    )
    assert infer_column_purpose(
        "notes",
        {"string_length": {"average": 12}},
        ["short note"],
    ) == "notes"


def test_batch_size_must_be_positive():
    with pytest.raises(ValueError):
        LLMTextGenerator(batch_size=0, skip_health_check=True)


@patch("backend.generation.llm_text.ollama_generate")
def test_generates_exact_row_count_in_batches(mock_generate):
    calls = []

    def _fake(prompt, **kwargs):
        calls.append(prompt)
        return "\n".join(
            [
                f"Package arrived late on attempt {len(calls)}-{index}"
                for index in range(1, 6)
            ]
        )

    mock_generate.side_effect = _fake
    generator = _generator(batch_size=3)
    values = generator.generate(
        column_name="feedback",
        count=7,
        sample_values=["The scent faded quickly."],
        source_values=["The scent faded quickly."],
    )

    assert len(values) == 7
    assert mock_generate.call_count >= 3
    assert mock_generate.call_count < 7
    assert "The scent faded quickly." not in values
    assert all("Generate 7 NEW" not in prompt for prompt in calls)


@patch("backend.generation.llm_text.ollama_generate")
def test_rejects_source_copies_and_retries(mock_generate):
    responses = [
        "The product did not work well.\nI like it.",
        "Late delivery damaged the outer box\nSeal was already broken on arrival\n",
    ]
    mock_generate.side_effect = lambda *args, **kwargs: responses.pop(0)

    generator = _generator(batch_size=2, max_retries=3)
    values = generator.generate(
        column_name="feedback",
        count=2,
        sample_values=["The product did not work well."],
        source_values=["The product did not work well.", "I like it."],
    )

    assert values == [
        "Late delivery damaged the outer box",
        "Seal was already broken on arrival",
    ]
    assert mock_generate.call_count == 2


@patch("backend.generation.llm_text.ollama_generate")
def test_retries_on_ollama_failure_then_succeeds(mock_generate):
    mock_generate.side_effect = [
        TimeoutError("timed out"),
        "Courier left the parcel in the rain\nBottle cap was not sealed tightly\n",
    ]
    generator = _generator(batch_size=2, max_retries=3)
    values = generator.generate(
        column_name="complaint",
        count=2,
        sample_values=["Packaging arrived crushed."],
        source_values=["Packaging arrived crushed."],
    )
    assert len(values) == 2
    assert mock_generate.call_count == 2


@patch("backend.generation.llm_text.ollama_generate")
def test_raises_after_retry_budget(mock_generate):
    mock_generate.side_effect = RuntimeError("Ollama down")
    generator = _generator(batch_size=2, max_retries=2)
    with pytest.raises(RuntimeError, match="after 2 retries"):
        generator.generate(
            column_name="feedback",
            count=2,
            sample_values=["Average experience overall."],
        )


@patch("backend.generation.llm_text.ollama_generate")
def test_raises_when_output_never_usable(mock_generate):
    mock_generate.return_value = "Sure, I can help with that."
    generator = _generator(batch_size=2, max_retries=1)
    with pytest.raises(RuntimeError, match="Could not generate"):
        generator.generate(
            column_name="feedback",
            count=3,
            sample_values=["Average experience overall."],
        )


@patch("backend.generation.llm_text.ensure_ollama_ready")
@patch("backend.generation.llm_text.ollama_generate")
def test_health_check_uses_local_ollama_only(mock_generate, mock_ready):
    mock_generate.return_value = "Arrived two days late with a dented lid"
    generator = LLMTextGenerator(
        batch_size=1,
        skip_health_check=False,
        model="qwen2.5:1.5b",
        ollama_url="http://localhost:11434",
    )
    values = generator.generate(
        column_name="feedback",
        count=1,
        sample_values=["The box was crushed."],
        source_values=["The box was crushed."],
    )
    mock_ready.assert_called_once()
    assert mock_ready.call_args.kwargs["base_url"] == "http://localhost:11434"
    assert len(values) == 1
