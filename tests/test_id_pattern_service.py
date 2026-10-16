import re
import uuid

import pandas as pd

from backend.services.id_pattern_service import generate_ids_like


def _check_common(new, original, n):
    assert len(new) == n
    assert len(set(new)) == n
    assert not (set(map(str, new)) & set(map(str, original)))


def test_integer_counter_stays_integer():
    s = pd.Series(range(1001, 1101))
    new = generate_ids_like(s, 50)
    _check_common(new, s, 50)
    assert all(isinstance(v, int) for v in new)
    assert new[0] == 1101


def test_integer_random_same_magnitude():
    s = pd.Series([8472913, 1930284, 5520011, 7710245, 3341876])
    new = generate_ids_like(s, 200, seed=1)
    _check_common(new, s, 200)
    assert all(1930284 <= v <= 8472913 for v in new)


def test_int_with_nan_float_column():
    s = pd.Series([1.0, 2.0, 3.0, None, 5.0])
    new = generate_ids_like(s, 3)
    assert all(isinstance(v, int) for v in new)
    _check_common(new, [1, 2, 3, 5], 3)


def test_prefix_zero_padded_counter():
    s = pd.Series([f"CUST-{i:04d}" for i in range(1, 43)])
    new = generate_ids_like(s, 5)
    assert new == ["CUST-0043", "CUST-0044", "CUST-0045", "CUST-0046", "CUST-0047"]


def test_counter_grows_past_padding():
    s = pd.Series([f"ORD{i:03d}" for i in range(1, 1000)])
    new = generate_ids_like(s, 3)
    assert new == ["ORD1000", "ORD1001", "ORD1002"]


def test_random_alnum_template_kept():
    s = pd.Series(["A9X-4F2", "K3M-7Q1", "P5Z-2D8", "T1B-9C4", "W8N-3H6"])
    new = generate_ids_like(s, 100, seed=7)
    _check_common(new, s, 100)
    assert all(re.fullmatch(r"[A-Z]\d[A-Z]-\d[A-Z]\d", v) for v in new)


def test_uuid_format():
    s = pd.Series([str(uuid.uuid4()) for _ in range(20)])
    new = generate_ids_like(s, 10)
    _check_common(new, s, 10)
    assert all(uuid.UUID(v) for v in new)


def test_variable_length_digit_strings_no_leading_zero():
    s = pd.Series(["7", "52", "913", "4471", "20365", "88", "301"])
    new = generate_ids_like(s, 50, seed=3)
    _check_common(new, s, 50)
    assert all(v.isdigit() and not v.startswith("0") for v in new)


def test_small_space_does_not_hang():
    s = pd.Series(["A1", "B2", "C3", "D4"])
    new = generate_ids_like(s, 500, seed=2)
    _check_common(new, s, 500)


def test_mixed_format_fallback_keeps_prefix():
    s = pd.Series(["EMP-1", "EMP_22", "EMP/333", "EMP:A", "EMP 9"])
    new = generate_ids_like(s, 20, seed=4)
    _check_common(new, s, 20)
    assert all(v.startswith("EMP") for v in new)


def test_existing_values_are_avoided():
    s = pd.Series(["CUST-0001", "CUST-0002"])
    new = generate_ids_like(s, 2, existing=["CUST-0003"])
    assert new == ["CUST-0004", "CUST-0005"]


def test_no_source_gives_plain_integers():
    assert generate_ids_like(None, 3) == [1, 2, 3]
    assert generate_ids_like(pd.Series([], dtype=object), 2) == [1, 2]


def test_zero_count():
    assert generate_ids_like(pd.Series([1, 2]), 0) == []