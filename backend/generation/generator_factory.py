from backend.generation.gaussian_copula import (
    GaussianCopulaGenerator
)
from backend.generation.ctgan import (
    CTGANGenerator
)
from backend.generation.tvae import (
    TVAEGenerator
)


def get_generator(model_name: str, **kwargs):
    """
    Return the requested synthetic data generator.

    Supported models:
    - Gaussian Copula
    - CTGAN
    - TVAE
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
            **kwargs
        )

    if name == "ctgan":
        return CTGANGenerator(
            **kwargs
        )

    if name == "tvae":
        return TVAEGenerator(
            **kwargs
        )

    raise ValueError(
        f"Unsupported generation model: {model_name}. "
        "Supported models: Gaussian Copula, CTGAN, TVAE."
    )