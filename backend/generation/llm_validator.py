import re


STRONG_NEGATIVE_PATTERNS = [
    r"\bfailed\b",
    r"\bineffective\b",
    r"\bdisappointed\b",
    r"\bdamaged\b",
    r"\boverwhelming\b",
    r"\boverpowering\b",
    r"\bpoor\b",
    r"\bterrible\b",
    r"\bawful\b",
    r"\birritat\w*\b",
    r"\bdelayed\b",
    r"\bnot sealed properly\b",
    r"\bnot properly sealed\b",
    r"\bnot effective\b",
    r"\bnot as expected\b",
    r"\bdid not work\b",
    r"\bdidn't work\b",
    r"\bdid not deliver\b",
    r"\bdidn't deliver\b",
    r"\bnot deliver\b",
    r"\bnot meet\b",
    r"\bcouldn't\b",
    r"\bcould not\b",
    r"\btoo strong\b",
    r"\btoo oily\b",
]

MILD_ISSUE_PATTERNS = [
    r"\bcould be better\b",
    r"\bcould improve\b",
    r"\bslightly\b",
    r"\ba little\b",
    r"\ba bit\b",
    r"\bminor\b",
    r"\bslight\b",
    r"\bdifficult to\b",
    r"\bhard to\b",
    r"\bnot easy to\b",
]

POSITIVE_PATTERNS = [
    r"\bexcellent\b",
    r"\bgreat\b",
    r"\bwonderful\b",
    r"\bworked very well\b",
    r"\bworked well\b",
    r"\bsatisfied\b",
    r"\bhappy\b",
    r"\beffective\b",
    r"\bgood results\b",
    r"\bpleased\b",
]


def _contains_pattern(text: str, patterns: list[str]) -> bool:
    text = text.lower()

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


def validate_rating_consistency(
    text: str,
    rating: int,
    column_name: str = "",
) -> bool:
    """
    Validate generated text against rating and column type.
    """

    if not text or not text.strip():
        return False

    text = text.strip()

    column = column_name.lower().strip()

    is_complaint_column = (
        "complaint" in column
        or "feedback" in column
        or "comment" in column
    )

    strong_negative = _contains_pattern(
        text,
        STRONG_NEGATIVE_PATTERNS,
    )

    mild_issue = _contains_pattern(
        text,
        MILD_ISSUE_PATTERNS,
    )

    positive = _contains_pattern(
        text,
        POSITIVE_PATTERNS,
    )

    # Rating 1
    if rating == 1:
        return strong_negative

    # Rating 2
    if rating == 2:
        return strong_negative or mild_issue

    # Rating 3
    if rating == 3:

        # Should not be strongly one-sided
        if strong_negative and not positive:
            return False

        if positive and not strong_negative:
            return False

        return True

    # Rating 4
    if rating == 4:

        if strong_negative:
            return False

        if is_complaint_column:
            return positive or mild_issue

        return positive

    # Rating 5
    if rating == 5:

        if strong_negative:
            return False

        if is_complaint_column:
            # A complaint column should still contain
            # some issue/limitation rather than pure praise.
            return mild_issue or (
                positive and mild_issue
            )

        return positive

    return True


EXTRA_POSITIVE_PATTERNS = [
    r"\blove\b",
    r"\bloved\b",
    r"\bgreat\b",
    r"\bexcellent\b",
    r"\bamazing\b",
    r"\bwonderful\b",
    r"\bfantastic\b",
    r"\bawesome\b",
    r"\bperfect\b",
    r"\bbest\b",
    r"\bgood\b",
    r"\bhappy\b",
    r"\bpleased\b",
    r"\bhelpful\b",
    r"\bsmooth\b",
    r"\bimpressed\b",
    r"\bsuperb\b",
    r"\benjoyed\b",
    r"\bhighly recommend\b",
    r"\bfast delivery\b",
    r"\bhigh quality\b",
]

EXTRA_NEGATIVE_PATTERNS = [
    r"\bterrible\b",
    r"\bbad\b",
    r"\bhorrible\b",
    r"\bawful\b",
    r"\bworst\b",
    r"\bwaste\b",
    r"\bpoor\b",
    r"\bhate\b",
    r"\bdisappointed\b",
    r"\bdisappointing\b",
    r"\bslow\b",
    r"\bbroken\b",
    r"\bfailed\b",
    r"\brude\b",
    r"\buseless\b",
    r"\bannoying\b",
    r"\bfrustrated\b",
    r"\bnever again\b",
    r"\bunhappy\b",
    r"\bdelayed\b",
    r"\bissue\b",
    r"\bproblem\b",
]


def validate_sentiment_consistency(
    text: str,
    sentiment: str,
) -> bool:
    """
    Validate that generated text semantically matches the target sentiment label.
    """
    if not text or not text.strip():
        return False

    t = text.lower().strip()
    s = str(sentiment).lower().strip()

    all_pos = POSITIVE_PATTERNS + EXTRA_POSITIVE_PATTERNS
    all_neg = STRONG_NEGATIVE_PATTERNS + EXTRA_NEGATIVE_PATTERNS

    has_positive = any(re.search(pat, t) for pat in all_pos)
    has_negative = any(re.search(pat, t) for pat in all_neg)

    if s in ("positive", "pos", "1", "good"):
        # Positive sentiment should not have strong negative complaints
        # and should express satisfaction
        if has_negative and not has_positive:
            return False
        return True

    if s in ("negative", "neg", "0", "bad"):
        # Negative sentiment should not be purely positive praise
        if has_positive and not has_negative:
            return False
        return True

    if s in ("neutral", "neu", "mixed"):
        # Neutral sentiment is acceptable if not extremely polarized
        return True

    return True