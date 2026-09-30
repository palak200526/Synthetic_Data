import pytest

from backend.generation.generator_factory import get_generator
from backend.generation.gaussian_copula import GaussianCopulaGenerator
from backend.generation.ctgan import CTGANGenerator
from backend.generation.tvae import TVAEGenerator


@pytest.mark.parametrize(
    "model_name, expected_class",
    [
        ("gaussian_copula", GaussianCopulaGenerator),
        ("ctgan", CTGANGenerator),
        ("tvae", TVAEGenerator),
    ],
)
def test_model_selection(model_name, expected_class):
    generator = get_generator(model_name)

    assert isinstance(generator, expected_class)


def test_unsupported_model_raises_error():
    with pytest.raises(ValueError):
        get_generator("invalid_model")


def test_empty_model_name_raises_error():
    with pytest.raises(ValueError):
        get_generator("")