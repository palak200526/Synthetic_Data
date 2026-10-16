"""
Realistic synthetic identifier generation.

Instead of stamping every new ID with a recognisable marker such as
``customer_id_synthetic_000001``, this module looks at how the ORIGINAL
identifiers in a column are written and produces new values that follow the
same format:

    original                     ->  synthetic
    ---------------------------------------------------------------
    1001, 1002, 1003 (int)       ->  1004, 1005, 1006     (int)
    CUST-0042, CUST-0043         ->  CUST-0044, CUST-0045
    A9X-4F2, K3M-7Q1             ->  R2T-8B5, D6W-1N9
    550e8400-e29b-41d4-...       ->  a fresh UUID (same letter case)
    8472913, 1930284 (random)    ->  random ints of the same size

Guarantees
    * exactly ``count`` values are returned
    * all values are unique
    * no value collides with an original (or already existing) ID
    * integer columns stay integer, string columns stay string
"""

from __future__ import annotations

import random
import re
import uuid
from collections import Counter
from typing import Any, Iterable, Optional

import pandas as pd

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_LOWER = "abcdefghijklmnopqrstuvwxyz"
_DIGITS = "0123456789"

# A signature must describe at least this share of the values to be trusted.
_DOMINANT_SHARE = 0.8
# Columns with IDs this dense (e.g. 1..N) are treated as running counters.
_DENSE_SHARE = 0.9
_MAX_WIDEN_ROUNDS = 6


# ----------------------------------------------------------------------
# Tokenising a string ID into runs, e.g. "CUST-0042" -> U"CUST" S"-" D"0042"
# ----------------------------------------------------------------------

def _char_class(ch: str) -> str:
    if ch.isdigit() and ch.isascii():
        return "D"
    if ch.isascii() and ch.isalpha():
        return "U" if ch.isupper() else "L"
    return "S"


def _tokenise(value: str) -> list[tuple[str, str]]:
    runs: list[tuple[str, str]] = []
    for ch in value:
        cls = _char_class(ch)
        if runs and runs[-1][0] == cls:
            runs[-1] = (cls, runs[-1][1] + ch)
        else:
            runs.append((cls, ch))
    return runs


def _signature(runs: list[tuple[str, str]]) -> tuple:
    return tuple(cls if cls != "S" else ("S", text) for cls, text in runs)


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------

def generate_ids_like(
    source: Optional[pd.Series],
    count: int,
    existing: Optional[Iterable[Any]] = None,
    seed: Optional[int] = None,
) -> list:
    """
    Return ``count`` new, unique IDs written in the same style as ``source``.

    ``source``   original ID column (may be None/empty -> plain integers)
    ``existing`` extra values that must not be reused
    ``seed``     optional, for reproducible output
    """
    if count <= 0:
        return []

    rng = random.Random(seed)

    values = pd.Series(dtype=object) if source is None else source.dropna()

    taken_str = {str(v) for v in values.tolist()}
    if existing is not None:
        taken_str |= {str(v) for v in existing if not _is_null(v)}

    if values.empty:
        return _plain_integers(count, taken_str)

    if pd.api.types.is_integer_dtype(values) or _is_integral_float(values):
        return _generate_integers(values, count, taken_str, rng)

    strings = values.astype(str).tolist()

    if _mostly_uuid(strings):
        return _generate_uuids(strings, count, taken_str)

    return _generate_from_template(strings, count, taken_str, rng)


# ----------------------------------------------------------------------
# Integers
# ----------------------------------------------------------------------

def _is_null(value: Any) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _is_integral_float(values: pd.Series) -> bool:
    # An int column becomes float64 as soon as it contains a NaN.
    if not pd.api.types.is_float_dtype(values):
        return False
    return bool((values == values.round()).all())


def _plain_integers(count: int, taken: set[str]) -> list[int]:
    out: list[int] = []
    n = 1
    while len(out) < count:
        if str(n) not in taken:
            out.append(n)
        n += 1
    return out


def _generate_integers(
    values: pd.Series,
    count: int,
    taken: set[str],
    rng: random.Random,
) -> list[int]:
    ints = [int(v) for v in values.tolist()]
    lo, hi = min(ints), max(ints)
    span = hi - lo + 1

    ascending = all(a <= b for a, b in zip(ints, ints[1:]))
    dense = len(set(ints)) >= _DENSE_SHARE * span

    # Running counter (1, 2, 3 ... or 1001, 1002 ...) -> simply carry on.
    if ascending or dense:
        out: list[int] = []
        n = hi + 1
        while len(out) < count:
            if str(n) not in taken:
                out.append(n)
            n += 1
        return out

    # Random-looking IDs -> random numbers of the same magnitude.
    # Never produce a negative number from a non-negative column.
    low = max(lo, 0) if lo >= 0 else lo
    high = hi
    chosen: set[int] = set()
    out = []
    attempts = 0
    limit = count * 20 + 1000

    while len(out) < count:
        n = rng.randint(low, high)
        attempts += 1
        if n not in chosen and str(n) not in taken:
            chosen.add(n)
            out.append(n)
        if attempts > limit:
            # Range is crowded; grow it a little instead of looping forever.
            high = high + max(count, span)
            attempts = 0
    return out


# ----------------------------------------------------------------------
# UUIDs
# ----------------------------------------------------------------------

def _mostly_uuid(strings: list[str]) -> bool:
    hits = sum(1 for s in strings if _UUID_RE.match(s))
    return hits >= _DOMINANT_SHARE * len(strings)


def _generate_uuids(
    strings: list[str],
    count: int,
    taken: set[str],
) -> list[str]:
    upper = sum(1 for s in strings if s.isupper()) > len(strings) / 2
    out: list[str] = []
    seen: set[str] = set()
    while len(out) < count:
        value = str(uuid.uuid4())
        if upper:
            value = value.upper()
        if value not in seen and value not in taken:
            seen.add(value)
            out.append(value)
    return out


# ----------------------------------------------------------------------
# Templated strings (CUST-0042, A9X-4F2, INV2023-00017 ...)
# ----------------------------------------------------------------------

class _Run:
    """One position of the template: a literal or a random/counter field."""

    def __init__(self, cls: str, texts: list[str]):
        self.cls = cls
        self.constant = len(set(texts)) == 1
        self.literal = texts[0] if self.constant else None
        self.texts = texts
        self.lengths = [len(t) for t in texts]
        self.zero_padded = cls == "D" and any(
            len(t) > 1 and t.startswith("0") for t in texts
        )

    def width(self, rng: random.Random, widen: int) -> int:
        return rng.choice(self.lengths) + widen

    def random_text(self, rng: random.Random, widen: int) -> str:
        if self.constant:
            return self.literal
        if self.cls == "S":
            return rng.choice(self.texts)
        n = self.width(rng, widen)
        if self.cls == "D":
            if self.zero_padded:
                return "".join(rng.choice(_DIGITS) for _ in range(n))
            first = rng.choice(_DIGITS[1:])
            return first + "".join(rng.choice(_DIGITS) for _ in range(n - 1))
        alphabet = _UPPER if self.cls == "U" else _LOWER
        return "".join(rng.choice(alphabet) for _ in range(n))


def _generate_from_template(
    strings: list[str],
    count: int,
    taken: set[str],
    rng: random.Random,
) -> list[str]:
    tokenised = [_tokenise(s) for s in strings]
    sigs = Counter(_signature(r) for r in tokenised)
    top_sig, top_hits = sigs.most_common(1)[0]

    if top_hits < _DOMINANT_SHARE * len(strings):
        return _generate_fallback(strings, count, taken, rng)

    rows = [r for r in tokenised if _signature(r) == top_sig]
    runs = [
        _Run(cls, [row[i][1] for row in rows])
        for i, (cls, _) in enumerate(rows[0])
    ]

    variable = [i for i, r in enumerate(runs) if not r.constant]

    # One changing numeric field and everything else fixed -> a counter.
    if len(variable) == 1 and runs[variable[0]].cls == "D":
        counter = _try_counter(
            strings=[r for r in rows],
            runs=runs,
            index=variable[0],
            count=count,
            taken=taken,
        )
        if counter is not None:
            return counter

    # Otherwise fill every changing field randomly, keeping the layout.
    out: list[str] = []
    seen: set[str] = set()
    widen = 0
    attempts = 0
    limit = count * 20 + 1000

    while len(out) < count:
        candidate = "".join(r.random_text(rng, widen) for r in runs)
        attempts += 1
        if candidate not in seen and candidate not in taken:
            seen.add(candidate)
            out.append(candidate)
        if attempts > limit:
            widen += 1  # make the ID one character longer in each field
            attempts = 0
            if widen > _MAX_WIDEN_ROUNDS:
                return _generate_fallback(strings, count, taken, rng)
    return out


def _try_counter(
    strings: list[list[tuple[str, str]]],
    runs: list[_Run],
    index: int,
    count: int,
    taken: set[str],
) -> Optional[list[str]]:
    run = runs[index]
    numbers = [int(row[index][1]) for row in strings]
    ascending = all(a <= b for a, b in zip(numbers, numbers[1:]))
    span = max(numbers) - min(numbers) + 1
    dense = len(set(numbers)) >= _DENSE_SHARE * span

    if not (ascending or dense):
        return None

    width = max(run.lengths) if run.zero_padded else 0
    nxt = max(numbers) + 1
    out: list[str] = []
    while len(out) < count:
        num = str(nxt).zfill(width)
        parts = [
            num if i == index else r.literal for i, r in enumerate(runs)
        ]
        candidate = "".join(parts)
        if candidate not in taken:
            out.append(candidate)
        nxt += 1
    return out


def _generate_fallback(
    strings: list[str],
    count: int,
    taken: set[str],
    rng: random.Random,
) -> list[str]:
    """Mixed-format column: keep any shared prefix and the typical length."""
    prefix = _common_prefix(strings)
    lengths = sorted(len(s) for s in strings)
    body_len = max(4, lengths[len(lengths) // 2] - len(prefix))
    alphabet = _UPPER + _DIGITS

    out: list[str] = []
    seen: set[str] = set()
    while len(out) < count:
        candidate = prefix + "".join(
            rng.choice(alphabet) for _ in range(body_len)
        )
        if candidate not in seen and candidate not in taken:
            seen.add(candidate)
            out.append(candidate)
        elif len(seen) + len(taken) > len(alphabet) ** body_len // 2:
            body_len += 1
    return out


def _common_prefix(strings: list[str]) -> str:
    if not strings:
        return ""
    first, last = min(strings), max(strings)
    n = 0
    while n < len(first) and n < len(last) and first[n] == last[n]:
        n += 1
    prefix = first[:n]
    # A prefix made only of digits is part of the number, not a label.
    return prefix if prefix and not prefix.isdigit() else ""