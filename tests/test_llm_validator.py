from backend.generation.llm_validator import validate_rating_consistency


def test_rating_validation_accepts_matching_sentiment():
    assert validate_rating_consistency(
        "The shampoo didn't work as expected after regular use.",
        1,
        "complaint",
    )
    assert validate_rating_consistency(
        "The fragrance was too strong and unpleasant.",
        1,
        "complaint",
    )
    assert validate_rating_consistency(
        "The product was okay overall, but the fragrance could be better.",
        3,
        "complaint",
    )


def test_rating_validation_rejects_mismatched_high_ratings():
    assert not validate_rating_consistency(
        "The product failed to deliver the expected hydration.",
        5,
        "complaint",
    )
    assert not validate_rating_consistency(
        "The packaging was not sealed properly upon delivery.",
        5,
        "complaint",
    )
    assert not validate_rating_consistency(
        "The product worked very well and I am satisfied with it.",
        5,
        "complaint",
    )
