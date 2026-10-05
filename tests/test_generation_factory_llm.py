from backend.generation.generator_factory import get_generator
from backend.generation.llm_text import LLMTextGenerator


def test_factory_returns_llm_text_generator():
    generator = get_generator("llm")
    assert isinstance(generator, LLMTextGenerator)


def test_factory_accepts_llm_text_alias_and_kwargs():
    generator = get_generator(
        "llm_text",
        batch_size=12,
        skip_health_check=True,
        epochs=999,
    )
    assert isinstance(generator, LLMTextGenerator)
    assert generator.batch_size == 12
    assert generator.skip_health_check is True
