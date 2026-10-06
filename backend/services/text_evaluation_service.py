from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any

import numpy as np
import pandas as pd

from backend.generation.llm_validator import (
    validate_rating_consistency,
    validate_sentiment_consistency,
)
from backend.services.statistical_evaluation_service import (
    TEXT_KEYWORDS,
    _is_text_series,
    determine_column_eligibility,
)

logger = logging.getLogger(__name__)


def _compute_near_duplicate_rate(
    texts: list[str],
    sample_limit: int = 50,
    threshold: float = 0.85,
) -> float:
    """Compute near-duplicate rate on a sample of generated texts."""
    if len(texts) < 2:
        return 0.0

    sample = texts[:sample_limit]
    n = len(sample)
    near_dupes = 0
    pairs = 0

    for i in range(n):
        s1 = sample[i].casefold().strip()
        for j in range(i + 1, n):
            s2 = sample[j].casefold().strip()
            pairs += 1
            if SequenceMatcher(None, s1, s2).ratio() >= threshold:
                near_dupes += 1
                break

    return round(near_dupes / max(n, 1), 4)


def evaluate_text_quality(
    real_dataframe: pd.DataFrame,
    synthetic_dataframe: pd.DataFrame,
    column_configurations: list[dict] | None = None,
    dataset_profile: dict | None = None,
) -> dict[str, Any]:
    """
    Evaluate free-form string/text columns separately from statistical evaluation.

    Metrics:
    - exact / near-duplicate rate (uniqueness)
    - originality / overlap with real text (verbatim copy check)
    - text length similarity (average characters and words)
    - vocabulary / pattern similarity (token overlap / Jaccard)
    - semantic consistency with relevant labels (e.g. Sentiment, Rating)
    """
    if real_dataframe.empty or synthetic_dataframe.empty:
        return {
            "metric": "text_evaluation",
            "status": "not_applicable",
            "reason": "Empty dataset provided",
            "overall_score": None,
            "columns": {},
        }

    common_columns = [
        c
        for c in real_dataframe.columns
        if c in synthetic_dataframe.columns
    ]

    config_map = {}
    if column_configurations:
        for cfg in column_configurations:
            if isinstance(cfg, dict) and "column_name" in cfg:
                config_map[cfg["column_name"]] = cfg

    profile_map = {}
    if dataset_profile and isinstance(dataset_profile, dict):
        col_info = (
            dataset_profile.get("column_information")
            or dataset_profile.get("columns")
            or []
        )
        if isinstance(col_info, list):
            for col_prof in col_info:
                if isinstance(col_prof, dict) and "column_name" in col_prof:
                    profile_map[col_prof["column_name"]] = col_prof
        elif isinstance(col_info, dict):
            profile_map = col_info

    # Identify free-form text columns
    text_columns = []
    for col in common_columns:
        cfg = config_map.get(col)
        prof = profile_map.get(col)
        status, reason, col_type = determine_column_eligibility(
            column_name=col,
            real_series=real_dataframe[col],
            configuration=cfg,
            profile_column=prof,
        )

        is_text = False
        if col_type == "free_form_text" or reason == "free_form_text":
            is_text = True
        elif cfg and str(cfg.get("action", "")).lower() in ("llm", "text"):
            is_text = True
        elif col.strip().lower() in TEXT_KEYWORDS or _is_text_series(real_dataframe[col]):
            is_text = True

        if is_text:
            text_columns.append(col)

    if not text_columns:
        return {
            "metric": "text_evaluation",
            "status": "not_applicable",
            "reason": "No free-form text columns identified in dataset",
            "overall_score": None,
            "text_columns_count": 0,
            "columns": {},
        }

    # Detect structured columns for semantic consistency in synthetic data
    sentiment_col = None
    rating_col = None
    for c in synthetic_dataframe.columns:
        c_low = c.strip().lower()
        if c_low in ("sentiment", "tone", "sentiment_label") and sentiment_col is None:
            sentiment_col = c
        elif c_low in ("rating", "stars", "score_rating") and rating_col is None:
            rating_col = c

    column_results: dict[str, Any] = {}
    valid_scores: list[float] = []

    for col in text_columns:
        real_s = real_dataframe[col].dropna().astype(str).str.strip()
        synth_s = synthetic_dataframe[col].dropna().astype(str).str.strip()
        real_s = real_s[real_s != ""]
        synth_s = synth_s[synth_s != ""]

        if len(real_s) == 0 or len(synth_s) == 0:
            column_results[col] = {
                "status": "excluded",
                "reason": "insufficient_text_data",
                "score": None,
            }
            continue

        synth_list = synth_s.tolist()
        synth_total = len(synth_s)

        # 1. Exact and Near-Duplicate Rate
        exact_dupes = synth_total - synth_s.nunique()
        exact_duplicate_rate = round(exact_dupes / max(synth_total, 1), 4)
        near_duplicate_rate = _compute_near_duplicate_rate(synth_list)
        uniqueness_score = round(max(0.0, 1.0 - exact_duplicate_rate) * 100, 2)

        # 2. Originality / Overlap with Real Text
        real_exact_set = {s.casefold() for s in real_s}
        verbatim_copies = sum(1 for s in synth_s if s.casefold() in real_exact_set)
        verbatim_copy_rate = round(verbatim_copies / max(synth_total, 1), 4)
        originality_rate = round(1.0 - verbatim_copy_rate, 4)
        originality_score = round(originality_rate * 100, 2)

        # 3. Text Length Similarity
        real_char_lens = real_s.str.len()
        synth_char_lens = synth_s.str.len()
        real_avg_len = round(float(real_char_lens.mean()), 2)
        synth_avg_len = round(float(synth_char_lens.mean()), 2)

        real_words = real_s.apply(lambda x: len(x.split()))
        synth_words = synth_s.apply(lambda x: len(x.split()))
        real_avg_words = round(float(real_words.mean()), 2)
        synth_avg_words = round(float(synth_words.mean()), 2)

        len_diff_ratio = abs(real_avg_len - synth_avg_len) / max(real_avg_len, 1.0)
        length_similarity_score = round(max(0.0, 1.0 - min(len_diff_ratio, 1.0)) * 100, 2)

        # 4. Vocabulary / Pattern Similarity
        real_tokens = re.findall(r"\b[a-zA-Z]{3,}\b", " ".join(real_s).lower())
        synth_tokens = re.findall(r"\b[a-zA-Z]{3,}\b", " ".join(synth_s).lower())
        real_vocab = set(real_tokens)
        synth_vocab = set(synth_tokens)

        vocab_overlap = len(real_vocab & synth_vocab)
        vocab_union = len(real_vocab | synth_vocab)
        jaccard_similarity = round(vocab_overlap / max(vocab_union, 1), 4)
        vocabulary_similarity_score = round(jaccard_similarity * 100, 2)

        lexical_diversity = round(len(synth_vocab) / max(len(synth_tokens), 1), 4)

        # 5. Semantic Consistency with Structured Columns
        semantic_score = None
        semantic_rate = None
        semantic_label = None

        if sentiment_col and sentiment_col in synthetic_dataframe.columns:
            matched_count = 0
            evaluated_count = 0
            for text_val, sent_val in zip(
                synthetic_dataframe[col], synthetic_dataframe[sentiment_col]
            ):
                if pd.isna(text_val) or pd.isna(sent_val):
                    continue
                evaluated_count += 1
                if validate_sentiment_consistency(str(text_val), str(sent_val)):
                    matched_count += 1

            if evaluated_count > 0:
                semantic_rate = round(matched_count / evaluated_count, 4)
                semantic_score = round(semantic_rate * 100, 2)
                semantic_label = f"sentiment ({sentiment_col})"

        elif rating_col and rating_col in synthetic_dataframe.columns:
            matched_count = 0
            evaluated_count = 0
            for text_val, rating_val in zip(
                synthetic_dataframe[col], synthetic_dataframe[rating_col]
            ):
                if pd.isna(text_val) or pd.isna(rating_val):
                    continue
                try:
                    r_int = int(round(float(rating_val)))
                except (ValueError, TypeError):
                    continue
                evaluated_count += 1
                if validate_rating_consistency(str(text_val), r_int, column_name=col):
                    matched_count += 1

            if evaluated_count > 0:
                semantic_rate = round(matched_count / evaluated_count, 4)
                semantic_score = round(semantic_rate * 100, 2)
                semantic_label = f"rating ({rating_col})"

        # Aggregate Column Score
        comp_scores = [
            uniqueness_score,
            originality_score,
            length_similarity_score,
            vocabulary_similarity_score,
        ]
        if semantic_score is not None:
            comp_scores.append(semantic_score)

        column_score = round(float(np.mean(comp_scores)), 2)
        valid_scores.append(column_score)

        column_results[col] = {
            "status": "evaluated",
            "score": column_score,
            "metrics": {
                "uniqueness_score": uniqueness_score,
                "uniqueness_rate": round(1.0 - near_duplicate_rate, 4),
                "exact_duplicate_rate": exact_duplicate_rate,
                "near_duplicate_rate": near_duplicate_rate,
                "originality_score": originality_score,
                "originality_rate": round(1.0 - verbatim_copy_rate, 4),
                "verbatim_copy_rate": verbatim_copy_rate,
                "length_similarity_score": length_similarity_score,
                "char_length_similarity": round(length_similarity_score / 100.0, 4),
                "length_similarity": {
                    "char_length_similarity": round(length_similarity_score / 100.0, 4),
                    "real_avg_chars": real_avg_len,
                    "synthetic_avg_chars": synth_avg_len,
                },
                "real_avg_chars": real_avg_len,
                "synthetic_avg_chars": synth_avg_len,
                "real_avg_words": real_avg_words,
                "synthetic_avg_words": synth_avg_words,
                "vocabulary_similarity_score": vocabulary_similarity_score,
                "vocabulary_jaccard": jaccard_similarity,
                "vocabulary_similarity": {
                    "jaccard": jaccard_similarity,
                    "lexical_diversity": lexical_diversity,
                },
                "lexical_diversity": lexical_diversity,
                "semantic_consistency_score": semantic_score,
                "semantic_consistency_rate": semantic_rate,
                "semantic_consistency": {
                    "consistency_rate": semantic_rate,
                    "target_column": semantic_label,
                },
                "semantic_target": semantic_label,
            },
        }

    overall_score = (
        round(float(np.mean(valid_scores)), 2) if valid_scores else None
    )

    return {
        "metric": "text_evaluation",
        "status": "evaluated" if valid_scores else "not_applicable",
        "overall_score": overall_score,
        "text_columns_count": len(text_columns),
        "columns": column_results,
        "message": (
            f"Text evaluation completed across {len(valid_scores)} text columns."
            if valid_scores
            else "No text columns could be evaluated."
        ),
    }
