"""
Local-Ollama generator for free-form STRING/TEXT columns.

Sends only column profile metadata and a small sample of values.
Never uploads the full dataset to an external API.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from difflib import SequenceMatcher
from typing import Any, Callable, Iterable, Optional

import pandas as pd

from backend.services.ollama_client import (
    OLLAMA_UNAVAILABLE_MESSAGE,
    ensure_ollama_ready,
    ollama_generate,
)

logger = logging.getLogger(__name__)

_LINE_PREFIX = re.compile(r"^\s*(?:[-*•]|\d+[.)\:])\s+")
_FENCE = re.compile(r"^```(?:json|text|markdown)?\s*|\s*```$", re.IGNORECASE)
_SKIP_LINE = re.compile(
    r"^(here (are|is)|sure[,.]?|output[:]?|generated (values|text)|"
    r"the following|note:|explanation:|json)",
    re.IGNORECASE,
)
_JSON_OBJECT = re.compile(r"\{[\s\S]*\}")
_JSON_ARRAY = re.compile(r"\[[\s\S]*\]")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def parse_llm_output(raw: str) -> list[str]:
    """
    Extract usable string values from numbered lists, bullets,
    markdown, JSON, or mixed LLM output.
    """
    if raw is None:
        return []

    text = str(raw).strip()
    if not text:
        return []

    text = _FENCE.sub("", text).strip()

    values = _try_parse_json_values(text)
    if values:
        return [_clean_generated_value(v) for v in values if _clean_generated_value(v)]

    parsed: list[str] = []
    for line in text.splitlines():
        line = _LINE_PREFIX.sub("", line).strip().strip('"').strip("'")
        if not line:
            continue
        if _SKIP_LINE.match(line):
            continue
        if line in ("{", "}", "[", "]"):
            continue
        cleaned = _clean_generated_value(line.rstrip(","))
        if cleaned:
            parsed.append(cleaned)
    return parsed


def _try_parse_json_values(text: str) -> list[str]:
    candidates = [text]
    obj = _JSON_OBJECT.search(text)
    arr = _JSON_ARRAY.search(text)
    if obj:
        candidates.append(obj.group(0))
    if arr:
        candidates.append(arr.group(0))

    for candidate in candidates:
        try:
            loaded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        extracted = _values_from_json(loaded)
        if extracted:
            return extracted
    return []


def _values_from_json(loaded: Any) -> list[str]:
    if isinstance(loaded, list):
        return [str(item) for item in loaded if item is not None and str(item).strip()]
    if isinstance(loaded, dict):
        for key in ("values", "texts", "items", "data", "records"):
            inner = loaded.get(key)
            if isinstance(inner, list):
                return [
                    str(item)
                    for item in inner
                    if item is not None and str(item).strip()
                ]
        if len(loaded) == 1:
            only = next(iter(loaded.values()))
            if isinstance(only, list):
                return [
                    str(item)
                    for item in only
                    if item is not None and str(item).strip()
                ]
    return []


def _clean_generated_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = _LINE_PREFIX.sub("", text).strip()
    text = text.strip('"').strip("'").strip()
    if text.lower() in {"none", "null", "n/a", "nan"}:
        return ""
    return text


def is_too_similar(
    generated: str,
    source_values: Iterable[str],
    threshold: float,
) -> bool:
    """Exact-match plus SequenceMatcher similarity against source examples."""
    candidate = (generated or "").strip()
    if not candidate:
        return True

    candidate_fold = candidate.casefold()
    for source in source_values:
        original = (source or "").strip()
        if not original:
            continue
        if candidate_fold == original.casefold():
            return True
        if threshold <= 0:
            continue
        ratio = SequenceMatcher(None, candidate_fold, original.casefold()).ratio()
        if ratio >= threshold:
            return True
    return False


def _truncate_sample(value: str, max_chars: int = 400) -> str:
    text = str(value).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def infer_column_purpose(column_name: str, profile: Optional[dict], samples: list[str]) -> str:
    name = (column_name or "").lower()
    hints = {
        "text": "free-form social or natural-language text",
        "feedback": "free-form customer feedback",
        "comment": "free-form comments",
        "review": "product or service reviews",
        "description": "descriptive text",
        "complaint": "customer complaints",
        "remark": "remarks or notes",
        "reason": "explanatory reasons",
        "message": "messages",
        "note": "notes",
        "summary": "summaries",
        "tweet": "short social-media posts",
        "content": "free-form content",
    }
    for key, purpose in hints.items():
        if key in name:
            return purpose

    avg_len = 0.0
    if profile:
        length_info = profile.get("string_length") or {}
        avg_len = float(length_info.get("average") or 0)
    elif samples:
        avg_len = sum(len(s) for s in samples) / max(len(samples), 1)

    if avg_len >= 40:
        return "free-form natural language text"
    if avg_len >= 15:
        return "short free-form text"
    return "string values"


class LLMTextGenerator:
    """
    Generates synthetic free-form text using a locally hosted Ollama model.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        ollama_url: Optional[str] = None,
        batch_size: Optional[int] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        skip_health_check: bool = False,
    ):
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        # Accept either base URL or full /api/generate URL for backward compatibility
        if ollama_url:
            self.base_url = ollama_url.replace("/api/generate", "").rstrip("/")
        else:
            self.base_url = base

        self.ollama_url = f"{self.base_url}/api/generate"
        resolved_batch = (
            _env_int("LLM_TEXT_BATCH_SIZE", 20)
            if batch_size is None
            else int(batch_size)
        )
        if resolved_batch < 1:
            raise ValueError("batch_size must be >= 1")
        self.batch_size = resolved_batch
        self.timeout = (
            _env_int("LLM_TEXT_TIMEOUT", 300)
            if timeout is None
            else int(timeout)
        )
        self.max_retries = (
            _env_int("LLM_TEXT_MAX_RETRIES", 3)
            if max_retries is None
            else int(max_retries)
        )
        self.similarity_threshold = (
            _env_float("LLM_TEXT_SIMILARITY_THRESHOLD", 0.92)
            if similarity_threshold is None
            else float(similarity_threshold)
        )
        self.skip_health_check = skip_health_check

    def generate_text(
        self,
        column_name: str,
        context: str,
        count: int = 1,
        row_context: str = "",
        profile: Optional[dict] = None,
        sample_values: Optional[list[str]] = None,
        source_values: Optional[Iterable[str]] = None,
        row_contexts: Optional[list[str]] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> list[str]:
        """
        Backward-compatible entry point used by tests and generation_service.
        """
        samples = list(sample_values or [])
        if not samples and context:
            samples = [
                line.lstrip("- ").strip()
                for line in str(context).splitlines()
                if line.strip().startswith("- ")
            ]

        return self.generate(
            column_name=column_name,
            count=count,
            sample_values=samples,
            profile=profile,
            extra_context=context,
            row_context=row_context,
            row_contexts=row_contexts,
            source_values=source_values or samples,
            progress_callback=progress_callback,
        )

    def generate(
        self,
        *,
        column_name: str,
        count: int,
        sample_values: Optional[list[str]] = None,
        profile: Optional[dict] = None,
        extra_context: str = "",
        row_context: str = "",
        row_contexts: Optional[list[str]] = None,
        source_values: Optional[Iterable[str]] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> list[str]:
        if count < 0:
            raise ValueError("count must be >= 0")
        if count == 0:
            return []

        if not self.skip_health_check:
            ensure_ollama_ready(model=self.model, base_url=self.base_url)

        samples = [_truncate_sample(v) for v in (sample_values or []) if str(v).strip()]
        raw_sources = [
            str(v).strip()
            for v in (source_values if source_values is not None else samples)
            if str(v).strip()
        ]
        source_exact = {value.casefold() for value in raw_sources}
        similarity_refs = samples or raw_sources[:8]
        unique_ratio = float((profile or {}).get("unique_ratio") or 0.0)
        enforce_unique = unique_ratio >= 0.5

        started = time.monotonic()
        logger.info(
            "LLM generation started column=%s requested=%s batch_size=%s model=%s",
            column_name,
            count,
            self.batch_size,
            self.model,
        )

        accepted: list[str] = []
        accepted_fold: set[str] = set()
        duplicate_regenerations = 0
        batch_number = 0
        consecutive_failures = 0
        empty_batches = 0
        max_empty = max(self.max_retries * 4, 8)

        while len(accepted) < count:
            remaining = count - len(accepted)
            this_size = min(self.batch_size, remaining)
            # Ask for a few extras so filtering does not stall the loop
            request_count = min(this_size + 2, max(self.batch_size, this_size))

            batch_row_context = row_context
            if row_contexts:
                start = len(accepted)
                end = min(start + request_count, len(row_contexts))
                slice_ctx = row_contexts[start:end]
                batch_row_context = "\n".join(
                    f"Row {i + 1}: {ctx}" for i, ctx in enumerate(slice_ctx)
                )
                request_count = max(len(slice_ctx), 1)

            batch_number += 1
            prompt = self._build_prompt(
                column_name=column_name,
                profile=profile,
                samples=samples,
                extra_context=extra_context,
                row_context=batch_row_context,
                count=request_count,
            )

            try:
                raw = ollama_generate(
                    prompt,
                    model=self.model,
                    base_url=self.base_url,
                    timeout=self.timeout,
                )
                consecutive_failures = 0
            except (RuntimeError, TimeoutError, ValueError) as exc:
                consecutive_failures += 1
                logger.warning(
                    "LLM batch failed column=%s batch=%s retry=%s/%s reason=%s",
                    column_name,
                    batch_number,
                    consecutive_failures,
                    self.max_retries,
                    type(exc).__name__,
                )
                if consecutive_failures >= self.max_retries:
                    raise RuntimeError(
                        f"LLM text generation failed for column '{column_name}' "
                        f"after {self.max_retries} retries: {exc}"
                    ) from exc
                continue

            parsed = parse_llm_output(raw)
            usable_this_batch = 0
            for value in parsed:
                if len(accepted) >= count:
                    break
                if not isinstance(value, str):
                    value = str(value)
                cleaned = _clean_generated_value(value)
                if not cleaned:
                    continue
                folded = cleaned.casefold()
                if folded in source_exact:
                    duplicate_regenerations += 1
                    continue
                if is_too_similar(cleaned, similarity_refs, self.similarity_threshold):
                    duplicate_regenerations += 1
                    continue
                if enforce_unique and folded in accepted_fold:
                    duplicate_regenerations += 1
                    continue
                accepted.append(cleaned)
                accepted_fold.add(folded)
                usable_this_batch += 1

            if usable_this_batch == 0:
                empty_batches += 1
                logger.warning(
                    "LLM batch produced no usable strings column=%s batch=%s",
                    column_name,
                    batch_number,
                )
                if empty_batches >= max_empty:
                    raise RuntimeError(
                        f"Could not generate {count} valid strings for column "
                        f"'{column_name}'. Only {len(accepted)} usable values "
                        f"were produced after {batch_number} batches."
                    )
            else:
                empty_batches = 0

            logger.info(
                "LLM batch complete column=%s batch=%s batch_size=%s "
                "usable=%s generated_total=%s/%s duplicate_regenerations=%s",
                column_name,
                batch_number,
                request_count,
                usable_this_batch,
                len(accepted),
                count,
                duplicate_regenerations,
            )

            if progress_callback:
                progress_callback(
                    {
                        "stage": "llm_text",
                        "column": column_name,
                        "batch": batch_number,
                        "generated": len(accepted),
                        "requested": count,
                        "percent": int((len(accepted) / count) * 100),
                    }
                )

        elapsed = time.monotonic() - started
        logger.info(
            "LLM generation finished column=%s rows=%s batches=%s "
            "duplicate_regenerations=%s seconds=%.2f",
            column_name,
            len(accepted),
            batch_number,
            duplicate_regenerations,
            elapsed,
        )

        if len(accepted) != count:
            raise RuntimeError(
                f"LLM generated {len(accepted)} values but {count} were required "
                f"for column '{column_name}'."
            )

        return accepted

    def generate_series(self, *args, **kwargs) -> pd.Series:
        values = self.generate(*args, **kwargs)
        return pd.Series(values, dtype="string")

    def _build_prompt(
        self,
        *,
        column_name: str,
        profile: Optional[dict],
        samples: list[str],
        extra_context: str,
        row_context: str,
        count: int,
    ) -> str:
        profile = profile or {}
        purpose = infer_column_purpose(column_name, profile, samples)
        dtype = profile.get("dtype") or "string"
        length_info = profile.get("string_length") or {}
        avg_len = length_info.get("average")
        min_len = length_info.get("min")
        max_len = length_info.get("max")
        unique_ratio = profile.get("unique_ratio")
        patterns = profile.get("patterns") or []

        example_block = "\n".join(f"- {item}" for item in samples[:8]) or "- (no examples)"

        length_line = "approximately similar to the examples"
        if avg_len:
            length_line = (
                f"about {int(avg_len)} characters "
                f"(range {min_len or '?'}–{max_len or '?'})"
            )

        style_notes = []
        if unique_ratio is not None:
            style_notes.append(f"unique_ratio={round(float(unique_ratio), 3)}")
        if patterns:
            style_notes.append("detected_patterns=" + ",".join(str(p) for p in patterns))

        extra = extra_context.strip() if extra_context else ""
        row_block = row_context.strip() if row_context else ""

        return f"""You are generating synthetic data for a dataset.

Column: {column_name}
Type: {purpose} (dtype={dtype})
Approximate text length: {length_line}
Profile notes: {'; '.join(style_notes) if style_notes else 'none'}

Examples:
{example_block}

{extra}

{('Synthetic row context:\n' + row_block) if row_block else ''}

Generate {count} NEW synthetic values for this column.

Requirements:
- Preserve the general domain, vocabulary, patterns, and style of the examples.
- Do NOT copy any example verbatim. Generate realistic, diverse text using new sentence structures and varied vocabulary.
- Semantic consistency: If the row context specifies a Sentiment (e.g., Positive, Negative, Neutral) or Rating (e.g. 1-5), the generated text MUST semantically reflect that exact sentiment and tone (e.g. Positive -> satisfied, praising; Negative -> issue, complaint, frustrated; Neutral -> balanced, matter-of-fact).
- Do not mention that the text is synthetic or AI-generated.
- Do not add numbering, bullets, quotation marks around lines, labels, or explanations.
- Return ONLY the generated values, one per line.
- Do not output JSON unless a value itself is JSON.
"""
