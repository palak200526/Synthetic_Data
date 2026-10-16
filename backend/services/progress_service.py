"""
Stage-based progress reporting for long-running generation jobs.

The generation pipeline is split into "floors" (stages). The reporter
turns what the pipeline is doing into one small dict that the job layer
(Celery ``update_state`` or the in-process job store) hands to
``GET /generation/status/{job_id}``:

    {
      "stage": "train",                 # machine key of the current floor
      "stage_label": "Training CTGAN",  # human label
      "stage_index": 3,                 # 1-based position in the plan
      "stage_total": 7,
      "stages": [{"key": "prepare", "label": "Preparing data"}, ...],
      "percent": 42,                    # overall, never goes backwards
      "stage_percent": 55,              # progress inside the current floor
      "message": "Epoch 55/100",
      "attempt": 1, "max_attempts": 1,
      "started_at": 1760000000.0, "updated_at": 1760000042.5,
      ... extra keys (epoch, column, generated, requested ...)
    }

The reporter never raises. If no callback is supplied every method is a
no-op, so synchronous / test callers are unaffected.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

STAGE_LABELS = {
    "prepare": "Preparing data",
    "rules": "Detecting business rules",
    "train": "Training model",
    "sample": "Generating rows",
    "llm_text": "Writing text columns",
    "validate": "Validating rows",
    "save": "Saving dataset",
}

_MODEL_NAMES = {
    "gaussian_copula": "Gaussian Copula",
    "ctgan": "CTGAN",
    "tvae": "TVAE",
}

# Relative time each floor is expected to take. Only the ratios matter.
_BASE_WEIGHTS = {
    "prepare": 4,
    "rules": 3,
    "sample": 6,
    "llm_text": 25,
    "validate": 4,
    "save": 4,
}
_TRAIN_WEIGHTS = {
    "gaussian_copula": 10,
    "ctgan": 60,
    "tvae": 55,
}

_ORDER = ["prepare", "rules", "train", "sample", "llm_text", "validate", "save"]

# Do not flood Redis / the job store with one write per epoch.
_MIN_EMIT_INTERVAL = 0.4


class ProgressReporter:
    def __init__(
        self,
        callback: Optional[Callable[[dict], None]] = None,
        model_name: Optional[str] = None,
    ):
        self._callback = callback
        self._model = (model_name or "").lower().strip()
        self._plan: list[str] = [
            k for k in _ORDER if k not in ("llm_text", "validate")
        ]
        self._current: Optional[str] = None
        self._fraction = 0.0
        self._message: Optional[str] = None
        self._attempt = 1
        self._max_attempts = 1
        self._max_percent = 0
        self._started_at = time.time()
        self._last_emit = 0.0
        self._extra: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Plan
    # ------------------------------------------------------------------

    def configure(self, has_llm: bool = False, has_validation: bool = False):
        """Decide which floors exist for this run (call once data is loaded)."""
        plan = []
        for key in _ORDER:
            if key == "llm_text" and not has_llm:
                continue
            if key == "validate" and not has_validation:
                continue
            plan.append(key)
        self._plan = plan
        self._emit(force=True)

    def set_attempt(self, attempt: int, max_attempts: int):
        self._attempt = attempt
        self._max_attempts = max_attempts

    # ------------------------------------------------------------------
    # Stage control
    # ------------------------------------------------------------------

    def start(self, key: str, message: Optional[str] = None, **extra):
        if key not in self._plan:
            return
        self._current = key
        self._fraction = 0.0
        self._message = message
        self._extra = extra
        self._emit(force=True)

    def update(
        self,
        key: str,
        fraction: float,
        message: Optional[str] = None,
        **extra,
    ):
        if key not in self._plan:
            return
        if self._current != key:
            self._current = key
        self._fraction = max(0.0, min(1.0, float(fraction)))
        if message is not None:
            self._message = message
        self._extra = extra
        self._emit(force=self._fraction >= 1.0)

    def complete(self, key: str):
        if key not in self._plan or self._current != key:
            return
        self._fraction = 1.0
        self._emit(force=True)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _weight(self, key: str) -> float:
        if key == "train":
            return _TRAIN_WEIGHTS.get(self._model, 30)
        return _BASE_WEIGHTS.get(key, 5)

    def _label(self, key: str) -> str:
        if key == "train":
            name = _MODEL_NAMES.get(self._model)
            return f"Training {name}" if name else STAGE_LABELS["train"]
        return STAGE_LABELS[key]

    def _percent(self) -> int:
        if not self._current or self._current not in self._plan:
            return self._max_percent

        total = sum(self._weight(k) for k in self._plan) or 1
        index = self._plan.index(self._current)
        done = sum(self._weight(k) for k in self._plan[:index])
        done += self._weight(self._current) * self._fraction

        percent = int(done / total * 100)
        # The job is only 100% once it has actually finished and saved.
        percent = min(percent, 99)
        # Retries re-enter earlier floors; the overall bar must not go back.
        self._max_percent = max(self._max_percent, percent)
        return self._max_percent

    def _emit(self, force: bool = False):
        if self._callback is None or not self._current:
            return

        now = time.time()
        if not force and now - self._last_emit < _MIN_EMIT_INTERVAL:
            return
        self._last_emit = now

        meta: dict[str, Any] = {
            "stage": self._current,
            "stage_label": self._label(self._current),
            "stage_index": self._plan.index(self._current) + 1,
            "stage_total": len(self._plan),
            "stages": [
                {"key": k, "label": self._label(k)} for k in self._plan
            ],
            "percent": self._percent(),
            "stage_percent": int(self._fraction * 100),
            "message": self._message,
            "attempt": self._attempt,
            "max_attempts": self._max_attempts,
            "started_at": self._started_at,
            "updated_at": now,
        }
        meta.update(self._extra)

        try:
            self._callback(meta)
        except Exception:  # progress must never break generation
            logger.debug("Progress callback failed", exc_info=True)