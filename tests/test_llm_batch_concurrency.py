"""
Unit and integration tests for batched and bounded concurrent LLM text generation.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.generation.llm_text import (
    LLMTextGenerator,
    parse_structured_llm_output,
)
from backend.services.ollama_client import async_ollama_generate


def _make_generator(**kwargs) -> LLMTextGenerator:
    defaults = {
        "batch_size": 4,
        "max_concurrency": 2,
        "timeout": 5,
        "max_retries": 3,
        "similarity_threshold": 0.92,
        "skip_health_check": True,
    }
    defaults.update(kwargs)
    return LLMTextGenerator(**defaults)


# 1. Structured JSON Parsing Tests
def test_parse_structured_json_records():
    raw = """
    ```json
    [
        {"id": 0, "text": "Super fast shipping and pristine packaging"},
        {"id": 1, "text": "Item arrived with slight box scuffing"},
        {"id": 2, "text": "Exceptional customer support team"}
    ]
    ```
    """
    parsed = parse_structured_llm_output(raw, expected_ids=[0, 1, 2])
    assert parsed == {
        0: "Super fast shipping and pristine packaging",
        1: "Item arrived with slight box scuffing",
        2: "Exceptional customer support team",
    }


def test_parse_structured_json_with_relative_ids():
    raw = """
    [
        {"id": 0, "text": "First relative text"},
        {"id": 1, "text": "Second relative text"}
    ]
    """
    parsed = parse_structured_llm_output(raw, expected_ids=[10, 11])
    assert parsed == {
        10: "First relative text",
        11: "Second relative text",
    }


def test_parse_structured_json_dict_wrapper():
    raw = """
    {
        "records": [
            {"id": 5, "text": "High quality fabric and true to size"}
        ]
    }
    """
    parsed = parse_structured_llm_output(raw, expected_ids=[5])
    assert parsed == {5: "High quality fabric and true to size"}


def test_parse_structured_fallback_to_string_array():
    raw = '["Comment A", "Comment B"]'
    parsed = parse_structured_llm_output(raw, expected_ids=[100, 101])
    assert parsed == {100: "Comment A", 101: "Comment B"}


# 2. Concurrency Limit and Semaphore Bounds
def test_bounded_concurrency_respected():
    generator = _make_generator(batch_size=2, max_concurrency=2)
    active_concurrent = 0
    max_active_observed = 0

    async def _mock_ollama(prompt, **kwargs):
        nonlocal active_concurrent, max_active_observed
        active_concurrent += 1
        if active_concurrent > max_active_observed:
            max_active_observed = active_concurrent
        await asyncio.sleep(0.05)
        active_concurrent -= 1
        return '[{"id": 0, "text": "Mock text A"}, {"id": 1, "text": "Mock text B"}]'

    async def _run():
        with patch.object(generator, "_call_ollama", side_effect=_mock_ollama):
            results = await generator.async_generate(
                column_name="review",
                count=8,  # 8 items with batch_size=2 = 4 batches
            )
            assert len(results) == 8
            assert max_active_observed <= 2
            assert generator.last_stats["concurrency"] == 2
            assert generator.last_stats["num_batches"] == 4

    asyncio.run(_run())


# 3. Partial Batch Retry (Only Failed Items Retried)
def test_partial_batch_retry_requests_only_missing_ids():
    generator = _make_generator(batch_size=3, max_concurrency=1)
    call_prompts = []

    async def _mock_ollama(prompt, **kwargs):
        call_prompts.append(prompt)
        if len(call_prompts) == 1:
            # First attempt: only returns ID 0 and ID 2 (ID 1 missing)
            return """
            [
                {"id": 0, "text": "Valid response for zero"},
                {"id": 2, "text": "Valid response for two"}
            ]
            """
        else:
            # Second attempt: returns missing ID 1
            return """
            [
                {"id": 1, "text": "Valid response for one"}
            ]
            """

    async def _run():
        with patch.object(generator, "_call_ollama", side_effect=_mock_ollama):
            results = await generator.async_generate(
                column_name="notes",
                count=3,
            )
            assert len(results) == 3
            assert results[0] == "Valid response for zero"
            assert results[1] == "Valid response for one"
            assert results[2] == "Valid response for two"
            assert len(call_prompts) == 2
            assert "ID 1" in call_prompts[1]
            assert "ID 0" not in call_prompts[1]
            assert "ID 2" not in call_prompts[1]

    asyncio.run(_run())


# 4. Deterministic Row-Context Alignment (Both Async and Sync)
def test_deterministic_row_context_alignment():
    generator = _make_generator(batch_size=2, max_concurrency=2)
    contexts = [
        "Rating=5, Sentiment=Positive",
        "Rating=1, Sentiment=Negative",
        "Rating=4, Sentiment=Positive",
        "Rating=2, Sentiment=Negative",
    ]

    async def _mock_ollama(prompt, **kwargs):
        lines = []
        for line in prompt.splitlines():
            if "ID " in line and "Row Context:" in line:
                parts = line.split("ID ")[1].split(" | ")
                rec_id = int(parts[0].strip())
                ctx = parts[1].strip()
                if "Sentiment=Positive" in ctx:
                    lines.append(f'{{"id": {rec_id}, "text": "Positive review for {rec_id}"}}')
                else:
                    lines.append(f'{{"id": {rec_id}, "text": "Negative review for {rec_id}"}}')
        return "[" + ", ".join(lines) + "]"

    with patch.object(generator, "_call_ollama", side_effect=_mock_ollama):
        results = generator.generate(
            column_name="feedback",
            count=4,
            row_contexts=contexts,
        )
        assert results == [
            "Positive review for 0",
            "Negative review for 1",
            "Positive review for 2",
            "Negative review for 3",
        ]


# 5. Parameter Validation
def test_batch_size_bounds():
    with pytest.raises(ValueError, match="between 1 and 50"):
        LLMTextGenerator(batch_size=0, skip_health_check=True)
    with pytest.raises(ValueError, match="between 1 and 50"):
        LLMTextGenerator(batch_size=51, skip_health_check=True)


def test_concurrency_bounds():
    with pytest.raises(ValueError, match="between 1 and 16"):
        LLMTextGenerator(max_concurrency=0, skip_health_check=True)
    with pytest.raises(ValueError, match="between 1 and 16"):
        LLMTextGenerator(max_concurrency=17, skip_health_check=True)


# 6. Detailed Statistics Tracking
def test_generation_statistics_populated():
    generator = _make_generator(batch_size=5, max_concurrency=2)

    async def _mock_ollama(prompt, **kwargs):
        return '[{"id": 0, "text": "Alpha"}, {"id": 1, "text": "Beta"}, {"id": 2, "text": "Gamma"}, {"id": 3, "text": "Delta"}, {"id": 4, "text": "Epsilon"}]'

    with patch.object(generator, "_call_ollama", side_effect=_mock_ollama):
        results = generator.generate(
            column_name="comments",
            count=5,
        )
        assert len(results) == 5
        stats = generator.last_stats
        assert stats["requested_count"] == 5
        assert stats["generated_count"] == 5
        assert stats["num_batches"] == 1
        assert stats["failed_or_retried_count"] == 0
        assert stats["total_duration_seconds"] >= 0
        assert stats["records_per_second"] >= 0
        assert stats["batch_size"] == 5
        assert stats["concurrency"] == 2
