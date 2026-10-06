import inspect

from backend.generation.gaussian_copula import (
    GaussianCopulaGenerator
)
from backend.generation.llm_text import (
    LLMTextGenerator
)


def _init_kwargs(cls, kwargs: dict) -> dict:
    """Keep tabular constructors isolated from LLM/unrelated parameters."""
    try:
        params = inspect.signature(cls.__init__).parameters
    except (TypeError, ValueError):
        return kwargs
    if any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in params.values()
    ):
        return kwargs
    return {
        key: value
        for key, value in kwargs.items()
        if key in params and key != "self"
    }


def get_generator(model_name: str, **kwargs):
    """
    Return the requested synthetic data generator.

    Supported models:
    - Gaussian Copula
    - CTGAN
    - TVAE
    - LLM Text Generation
    """

    if not model_name:
        raise ValueError(
            "model_name is required."
        )

    name = model_name.lower().strip()

    if name in (
        "gaussian_copula",
        "gaussian copula",
        "gaussiancopula"
    ):
        return GaussianCopulaGenerator(
            **_init_kwargs(GaussianCopulaGenerator, kwargs)
        )

    if name == "ctgan":
        from backend.generation.ctgan import CTGANGenerator
        return CTGANGenerator(
            **_init_kwargs(CTGANGenerator, kwargs)
        )

    if name == "tvae":
        from backend.generation.tvae import TVAEGenerator
        return TVAEGenerator(
            **_init_kwargs(TVAEGenerator, kwargs)
        )

    if name in (
        "llm",
        "llm_text",
        "llm text",
        "text"
    ):
        allowed = {
            key: value
            for key, value in kwargs.items()
            if key in {
                "model",
                "ollama_url",
                "batch_size",
                "timeout",
                "max_retries",
                "similarity_threshold",
                "skip_health_check",
            }
        }
        return LLMTextGenerator(**allowed)

    raise ValueError(
        f"Unsupported generation model: {model_name}. "
        "Supported models: Gaussian Copula, CTGAN, TVAE, LLM Text."
    )