"""
Default ML-utility target selection.

The local LLM (Ollama) proposes a target column, accepted only if it is one
of the candidate columns. Predictability is NOT checked here: it is checked
once, for the column that is actually evaluated. If the LLM is unavailable or
answers badly, no target is suggested and evaluate_ml_utility() falls back to
its own automatic selection.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.services.ollama_client import check_ollama_available, ollama_generate

logger = logging.getLogger(__name__)

_CACHE: dict[tuple, dict[str, Any]] = {}
LLM_TIMEOUT_SECONDS = 25


def _heuristic(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if not candidates:
        return {"target": None, "source": "none", "reason": "No column can be used as an ML target."}
    # target=None -> evaluate_ml_utility() picks a predictable target itself
    return {
        "target": None,
        "source": "auto",
        "reason": "Picked automatically: the first column that can be predicted from the others.",
    }


def _build_prompt(dataset_name: str | None, candidates: list[dict[str, Any]]) -> str:
    lines = []
    for c in candidates:
        lines.append(
            f"- {c['column']} | {c['task_type']} | {c['unique_values']} distinct values"
        )
    return (
        "You choose the best TARGET column for a machine-learning utility test "
        "of a synthetic tabular dataset. Prefer the outcome / label / final result "
        "column a data scientist would want to predict (e.g. final grade, churn, "
        "status, price, score). Avoid demographic or descriptive attributes "
        "(e.g. gender, country) unless nothing else fits.\n\n"
        f"Dataset: {dataset_name or 'unknown'}\n"
        "Candidate columns:\n" + "\n".join(lines) + "\n\n"
        'Answer ONLY with JSON: {"target_column": "<one candidate name>", '
        '"reason": "<one short sentence>"}'
    )


def suggest_default_target(
    dataset_id: int | None,
    dataset_name: str | None,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return {target, source: 'llm'|'auto'|'none', reason}."""
    if not candidates:
        return _heuristic(candidates)

    key = (dataset_id, tuple((c["column"], c["task_type"]) for c in candidates))
    if key in _CACHE:
        return _CACHE[key]

    result = _heuristic(candidates)
    try:
        if check_ollama_available():
            raw = ollama_generate(
                _build_prompt(dataset_name, candidates),
                format="json",
                timeout=LLM_TIMEOUT_SECONDS,
                options={"temperature": 0},
            )
            parsed = json.loads(raw)
            choice = str(parsed.get("target_column", "")).strip()
            by_name = {c["column"]: c for c in candidates}
            if choice in by_name:
                result = {
                    "target": choice,
                    "source": "llm",
                    "reason": str(parsed.get("reason") or "Suggested by the local LLM.")[:240],
                }
            else:
                logger.info("LLM returned unknown target %r; using heuristic", choice)
    except Exception as exc:
        logger.info("LLM target suggestion unavailable (%s); using heuristic", exc)

    _CACHE[key] = result
    return result