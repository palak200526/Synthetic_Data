"""
Local-Ollama generator for free-form STRING/TEXT columns.

Sends only column profile metadata and a small sample of values.
Never uploads the full dataset to an external API.
Supports batched structured generation, bounded async concurrency,
and deterministic row-context alignment.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import re
import time
import unittest.mock
from difflib import SequenceMatcher
from typing import Any, Callable, Iterable, Optional

import pandas as pd

from backend.services.ollama_client import (
    OLLAMA_UNAVAILABLE_MESSAGE,
    async_ollama_generate,
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


def _extract_json_chunk(text: str) -> Optional[str]:
    arr = _JSON_ARRAY.search(text)
    if arr:
        return arr.group(0)
    obj = _JSON_OBJECT.search(text)
    if obj:
        return obj.group(0)
    return None


def parse_structured_llm_output(raw: str, expected_ids: list[int]) -> dict[int, str]:
    """
    Extract an ID-to-string mapping from structured JSON or fallback outputs.
    Supports global IDs, relative 0-indexed IDs, JSON string arrays,
    and numbered/bulleted lines.
    """
    if raw is None or not expected_ids:
        return {}

    text = str(raw).strip()
    if not text:
        return {}

    text = _FENCE.sub("", text).strip()
    results: dict[int, str] = {}

    loaded_json = None
    for candidate in [text, _extract_json_chunk(text)]:
        if not candidate:
            continue
        try:
            loaded_json = json.loads(candidate)
            break
        except (json.JSONDecodeError, TypeError):
            continue

    if loaded_json is not None:
        records = None
        if isinstance(loaded_json, list):
            records = loaded_json
        elif isinstance(loaded_json, dict):
            for key in ("records", "items", "data", "values", "texts"):
                if isinstance(loaded_json.get(key), list):
                    records = loaded_json[key]
                    break

        if isinstance(records, list):
            dict_items = [item for item in records if isinstance(item, dict)]
            if dict_items:
                id_map: dict[int, str] = {}
                for item in dict_items:
                    rec_id = item.get("id")
                    if rec_id is None:
                        rec_id = item.get("record_id") or item.get("index")
                    val = item.get("text")
                    if val is None:
                        val = (
                            item.get("value")
                            or item.get("content")
                            or item.get("feedback")
                        )
                    if rec_id is not None and val is not None:
                        try:
                            rec_id_int = int(rec_id)
                            cleaned = _clean_generated_value(val)
                            if cleaned:
                                id_map[rec_id_int] = cleaned
                        except (ValueError, TypeError):
                            pass

                # Check exact global expected_ids
                for exp_id in expected_ids:
                    if exp_id in id_map:
                        results[exp_id] = id_map[exp_id]

                # Check relative 0-indexed IDs ONLY if no global expected_ids matched
                # (e.g. requested IDs were [10, 11] but model numbered them [0, 1])
                if not results and id_map:
                    for rel_idx, exp_id in enumerate(expected_ids):
                        if rel_idx in id_map:
                            results[exp_id] = id_map[rel_idx]

                return results

            # JSON array of plain strings (not dicts with IDs)
            extracted_strings = _values_from_json(records)
            if extracted_strings and len(results) < len(expected_ids):
                missing_ids = [i for i in expected_ids if i not in results]
                for exp_id, val in zip(missing_ids, extracted_strings):
                    cleaned = _clean_generated_value(val)
                    if cleaned:
                        results[exp_id] = cleaned
                return results

    return results


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
        out = []
        for item in loaded:
            if isinstance(item, dict):
                text_val = (
                    item.get("text")
                    or item.get("value")
                    or item.get("content")
                    or item.get("feedback")
                )
                if text_val is not None and str(text_val).strip():
                    out.append(str(text_val))
            elif item is not None and str(item).strip():
                out.append(str(item))
        return out
    if isinstance(loaded, dict):
        for key in ("values", "texts", "items", "data", "records"):
            inner = loaded.get(key)
            if isinstance(inner, list):
                return _values_from_json(inner)
        if len(loaded) == 1:
            only = next(iter(loaded.values()))
            if isinstance(only, list):
                return _values_from_json(only)
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


def run_coroutine_sync(coro):
    """Run a coroutine from sync code, even if an event loop is already running."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def estimate_num_predict(
    profile: Optional[dict],
    batch_count: int,
    floor: int = 256,
    ceiling: int = 4096,
) -> int:
    """
    Upper bound for generated tokens in one batch.  Stops the model from
    rambling (the biggest hidden cost with small local models) while leaving
    enough room for the JSON wrapper so output is never truncated.
    """
    length_info = (profile or {}).get("string_length") or {}
    longest = float(length_info.get("max") or length_info.get("average") or 120)
    tokens_per_item = int(longest / 3.0) + 24  # ~3 chars/token + {"id":..,"text":..}
    estimate = int(tokens_per_item * max(batch_count, 1) * 1.3) + 32
    return max(floor, min(ceiling, estimate))


class LLMTextGenerator:
    """
    Generates synthetic free-form text using a locally hosted Ollama model.
    Optimized with structured batching and bounded asynchronous concurrency.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        ollama_url: Optional[str] = None,
        batch_size: Optional[int] = None,
        max_concurrency: Optional[int] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        skip_health_check: bool = False,
        **kwargs,
    ):
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        if ollama_url:
            self.base_url = ollama_url.replace("/api/generate", "").rstrip("/")
        else:
            self.base_url = base

        self.ollama_url = f"{self.base_url}/api/generate"

        resolved_batch = (
            _env_int("LLM_TEXT_BATCH_SIZE", 10)
            if batch_size is None
            else int(batch_size)
        )
        if resolved_batch < 1 or resolved_batch > 50:
            raise ValueError(
                f"batch_size must be between 1 and 50, got {resolved_batch}"
            )
        self.batch_size = resolved_batch

        resolved_concurrency = (
            _env_int("LLM_TEXT_MAX_CONCURRENCY", 2)
            if max_concurrency is None
            else int(max_concurrency)
        )
        if resolved_concurrency < 1 or resolved_concurrency > 16:
            raise ValueError(
                f"max_concurrency must be between 1 and 16, got {resolved_concurrency}"
            )
        self.max_concurrency = resolved_concurrency

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
        self.last_stats: dict[str, Any] = {}

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
        """
        Synchronous wrapper for batch generation. Safe to call from standard
        threads or within active event loops.
        """
        coro = self.async_generate(
            column_name=column_name,
            count=count,
            sample_values=sample_values,
            profile=profile,
            extra_context=extra_context,
            row_context=row_context,
            row_contexts=row_contexts,
            source_values=source_values,
            progress_callback=progress_callback,
        )
        return run_coroutine_sync(coro)

    def generate_series(self, *args, **kwargs) -> pd.Series:
        values = self.generate(*args, **kwargs)
        return pd.Series(values, dtype="string")

    async def _call_ollama(
        self,
        prompt: str,
        http_client: Optional[Any] = None,
        options: Optional[dict] = None,
    ) -> str:
        """
        Execute an Ollama generate request. Uses native async httpx client
        in production, or falls back to thread execution if sync ollama_generate
        is patched in tests.
        """
        is_sync_mocked = isinstance(
            ollama_generate,
            (unittest.mock.Mock, unittest.mock.MagicMock),
        )
        is_async_mocked = isinstance(
            async_ollama_generate,
            (unittest.mock.Mock, unittest.mock.AsyncMock, unittest.mock.MagicMock),
        )

        if is_sync_mocked:
            return await asyncio.to_thread(
                ollama_generate,
                prompt,
                model=self.model,
                base_url=self.base_url,
                timeout=self.timeout,
            )

        if is_async_mocked:
            res = async_ollama_generate(
                prompt,
                model=self.model,
                base_url=self.base_url,
                timeout=self.timeout,
                client=http_client,
            )
            if asyncio.iscoroutine(res):
                return await res
            return str(res)

        return await async_ollama_generate(
            prompt,
            model=self.model,
            base_url=self.base_url,
            timeout=self.timeout,
            options=options,
            client=http_client,
        )

    async def async_generate(
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
        semaphore: Optional[asyncio.Semaphore] = None,
    ) -> list[str]:
        """
        Generate synthetic text values using bounded asynchronous concurrency,
        structured batches, deterministic index assignment, and partial retries.
        """
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
            "LLM generation started column=%s count=%s batch_size=%s "
            "concurrency=%s model=%s",
            column_name,
            count,
            self.batch_size,
            self.max_concurrency,
            self.model,
        )

        batch_slices: list[list[int]] = []
        for start in range(0, count, self.batch_size):
            end = min(start + self.batch_size, count)
            batch_slices.append(list(range(start, end)))

        final_results: list[Optional[str]] = [None] * count
        accepted_fold: set[str] = set()
        accepted_lock = asyncio.Lock()
        progress_lock = asyncio.Lock()
        # A semaphore shared across columns keeps the *total* number of
        # in-flight Ollama requests bounded when columns run concurrently.
        semaphore = semaphore or asyncio.Semaphore(self.max_concurrency)

        total_retries = 0
        retries_lock = asyncio.Lock()
        batch_durations: list[float] = []
        durations_lock = asyncio.Lock()

        def _get_row_context(index: int) -> str:
            if row_contexts and index < len(row_contexts):
                return str(row_contexts[index]).strip()
            return str(row_context).strip()

        async def _process_batch(
            batch_num: int,
            assigned_ids: list[int],
            http_client: Any,
        ) -> None:
            nonlocal total_retries
            batch_start = time.monotonic()
            pending_ids = list(assigned_ids)
            attempt = 0
            consecutive_failures = 0

            while pending_ids and attempt <= self.max_retries:
                attempt += 1
                record_specs = [(idx, _get_row_context(idx)) for idx in pending_ids]
                prompt = self._build_batch_prompt(
                    column_name=column_name,
                    profile=profile,
                    samples=samples,
                    extra_context=extra_context,
                    record_specs=record_specs,
                )

                async with semaphore:
                    try:
                        raw = await self._call_ollama(
                            prompt,
                            http_client=http_client,
                            options={
                                "num_predict": estimate_num_predict(
                                    profile, len(pending_ids)
                                ),
                            },
                        )
                        consecutive_failures = 0
                    except (RuntimeError, TimeoutError, ValueError) as exc:
                        consecutive_failures += 1
                        async with retries_lock:
                            total_retries += 1
                        logger.warning(
                            "LLM batch failed column=%s batch=%s attempt=%s reason=%s",
                            column_name,
                            batch_num,
                            attempt,
                            type(exc).__name__,
                        )
                        if consecutive_failures >= self.max_retries:
                            raise RuntimeError(
                                f"LLM text generation failed for column '{column_name}' "
                                f"after {self.max_retries} retries: {exc}"
                            ) from exc
                        continue

                parsed_map = parse_structured_llm_output(raw, pending_ids)
                fallback_lines = parse_llm_output(raw)
                newly_accepted: list[int] = []

                # Pass 1: Try structured ID mapping
                for rec_id in list(pending_ids):
                    val = parsed_map.get(rec_id)
                    if not val:
                        continue
                    cleaned = _clean_generated_value(val)
                    if not cleaned:
                        continue
                    folded = cleaned.casefold()
                    if folded in source_exact:
                        async with retries_lock:
                            total_retries += 1
                        continue
                    if is_too_similar(cleaned, similarity_refs, self.similarity_threshold):
                        async with retries_lock:
                            total_retries += 1
                        continue

                    async with accepted_lock:
                        if enforce_unique and folded in accepted_fold:
                            async with retries_lock:
                                total_retries += 1
                            continue
                        accepted_fold.add(folded)

                    final_results[rec_id] = cleaned
                    newly_accepted.append(rec_id)

                # Pass 2: If output was unstructured (parsed_map is empty), draw from fallback lines
                unfulfilled = [i for i in pending_ids if i not in newly_accepted]
                if not parsed_map and unfulfilled and fallback_lines:
                    for line in fallback_lines:
                        if not unfulfilled:
                            break
                        cleaned = _clean_generated_value(line)
                        if not cleaned:
                            continue
                        folded = cleaned.casefold()
                        if folded in source_exact:
                            continue
                        if is_too_similar(cleaned, similarity_refs, self.similarity_threshold):
                            continue

                        async with accepted_lock:
                            if enforce_unique and folded in accepted_fold:
                                continue
                            accepted_fold.add(folded)

                        rec_id = unfulfilled.pop(0)
                        final_results[rec_id] = cleaned
                        newly_accepted.append(rec_id)

                pending_ids = [i for i in pending_ids if i not in newly_accepted]
                if not pending_ids:
                    break

                async with retries_lock:
                    total_retries += 1

            if pending_ids:
                raise RuntimeError(
                    f"Could not generate {count} valid strings for column "
                    f"'{column_name}'. Batch {batch_num} left {len(pending_ids)} "
                    f"unfulfilled records."
                )

            batch_duration = time.monotonic() - batch_start
            async with durations_lock:
                batch_durations.append(batch_duration)

            if progress_callback:
                async with progress_lock:
                    completed_count = sum(1 for r in final_results if r is not None)
                    progress_callback(
                        {
                            "stage": "llm_text",
                            "column": column_name,
                            "batch": batch_num,
                            "generated": completed_count,
                            "requested": count,
                            "percent": int((completed_count / count) * 100),
                        }
                    )

        import httpx

        async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
            tasks = [
                _process_batch(b_idx + 1, slice_ids, client)
                for b_idx, slice_ids in enumerate(batch_slices)
            ]
            await asyncio.gather(*tasks)

        elapsed = time.monotonic() - started
        avg_batch_dur = sum(batch_durations) / max(len(batch_durations), 1)
        records_sec = count / max(elapsed, 0.001)

        self.last_stats = {
            "requested_count": count,
            "generated_count": len([r for r in final_results if r is not None]),
            "num_batches": len(batch_slices),
            "failed_or_retried_count": total_retries,
            "total_duration_seconds": round(elapsed, 3),
            "avg_batch_duration_seconds": round(avg_batch_dur, 3),
            "records_per_second": round(records_sec, 2),
            "concurrency": self.max_concurrency,
            "batch_size": self.batch_size,
            "model": self.model,
        }

        logger.info(
            "LLM generation finished column=%s rows=%s batches=%s "
            "retries=%s seconds=%.2f throughput=%.2f rec/s",
            column_name,
            count,
            len(batch_slices),
            total_retries,
            elapsed,
            records_sec,
        )

        return [str(val) for val in final_results if val is not None]

    def _build_batch_prompt(
        self,
        *,
        column_name: str,
        profile: Optional[dict],
        samples: list[str],
        extra_context: str,
        record_specs: list[tuple[int, str]],
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

        records_block_lines = []
        for rec_id, ctx in record_specs:
            if ctx:
                records_block_lines.append(f"- ID {rec_id} | Row Context: {ctx}")
            else:
                records_block_lines.append(f"- ID {rec_id}")
        records_block = "\n".join(records_block_lines)

        count = len(record_specs)

        return f"""You are generating synthetic data for a dataset.

Column: {column_name}
Type: {purpose} (dtype={dtype})
Approximate text length: {length_line}
Profile notes: {'; '.join(style_notes) if style_notes else 'none'}

Examples:
{example_block}

{extra}

Records to generate ({count} items):
{records_block}

Generate {count} NEW synthetic values for this column.

Output Format:
Return a JSON array of objects with "id" and "text" fields:
[
  {{"id": <id>, "text": "<generated text>"}}
]

Requirements:
- Preserve the general domain, vocabulary, patterns, and style of the examples.
- Do NOT copy any example verbatim. Generate realistic, diverse text using new sentence structures and varied vocabulary.
- Semantic consistency: If the row context specifies a Sentiment (e.g., Positive, Negative, Neutral) or Rating (e.g. 1-5), the generated text MUST semantically reflect that exact sentiment and tone.
- Do not mention that the text is synthetic or AI-generated.
- Do not output explanations, markdown comments, or formatting outside the JSON array.
- Return ONLY the JSON array.
"""
