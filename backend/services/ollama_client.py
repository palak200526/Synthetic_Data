"""
Shared local Ollama HTTP client.

All LLM traffic stays on the configured host (default localhost).
Do not add cloud inference providers here.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

OLLAMA_UNAVAILABLE_MESSAGE = (
    "Local Ollama service is unavailable. Please start Ollama and "
    "ensure the configured model is running."
)

MODEL_MISSING_MESSAGE = (
    "Configured Ollama model is not installed. Pull it with "
    "`ollama pull {model}` and retry."
)


def _env_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def _env_model() -> str:
    return os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


_SESSION = _session()


def check_ollama_available(
    base_url: Optional[str] = None,
    timeout: float = 2.0,
) -> bool:
    """Return True when the Ollama HTTP server responds."""
    url = f"{(base_url or _env_base_url()).rstrip('/')}/api/tags"
    try:
        response = _SESSION.get(url, timeout=timeout)
        return response.status_code == 200
    except requests.RequestException:
        return False


def list_ollama_models(
    base_url: Optional[str] = None,
    timeout: float = 5.0,
) -> list[str]:
    url = f"{(base_url or _env_base_url()).rstrip('/')}/api/tags"
    try:
        response = _SESSION.get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.json() or {}
    except requests.RequestException:
        return []

    names = []
    for item in payload.get("models") or []:
        name = item.get("name") or item.get("model")
        if name:
            names.append(str(name))
    return names


def check_ollama_model(
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 5.0,
) -> bool:
    """Return True when the configured model is present on the local server."""
    target = (model or _env_model()).strip()
    if not target:
        return False

    names = list_ollama_models(base_url=base_url, timeout=timeout)
    if not names:
        return False

    for name in names:
        if name == target or name.startswith(f"{target}") or target.startswith(name):
            return True
        # qwen2.5:1.5b vs qwen2.5:1.5b-xxxx tags
        if name.split(":")[0] == target.split(":")[0] and target in name:
            return True
    return False


def ensure_ollama_ready(
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> None:
    """
    Raise a clear error if Ollama or the configured model is unavailable.
    """
    resolved_model = model or _env_model()
    resolved_base = base_url or _env_base_url()

    if not check_ollama_available(base_url=resolved_base):
        logger.error("Ollama health check failed at %s", resolved_base)
        raise RuntimeError(OLLAMA_UNAVAILABLE_MESSAGE)

    if not check_ollama_model(model=resolved_model, base_url=resolved_base):
        logger.error(
            "Ollama model missing: %s at %s",
            resolved_model,
            resolved_base,
        )
        raise RuntimeError(MODEL_MISSING_MESSAGE.format(model=resolved_model))


def ollama_generate(
    prompt: str,
    *,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: int = 300,
    format: Optional[str] = None,
    options: Optional[dict[str, Any]] = None,
) -> str:
    """
    Call POST /api/generate on the local Ollama server.
    Returns the raw response text.
    """
    resolved_model = model or _env_model()
    url = f"{(base_url or _env_base_url()).rstrip('/')}/api/generate"

    payload: dict[str, Any] = {
        "model": resolved_model,
        "prompt": prompt,
        "stream": False,
    }
    if format:
        payload["format"] = format
    if options:
        payload["options"] = options

    try:
        response = _SESSION.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.Timeout as exc:
        logger.error("Ollama generate timed out model=%s", resolved_model)
        raise TimeoutError(
            f"Ollama request timed out after {timeout}s for model '{resolved_model}'."
        ) from exc
    except requests.ConnectionError as exc:
        logger.error("Ollama connection error")
        raise RuntimeError(OLLAMA_UNAVAILABLE_MESSAGE) from exc
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        logger.error("Ollama HTTP error status=%s", status)
        raise RuntimeError(
            f"Ollama returned HTTP {status}. {OLLAMA_UNAVAILABLE_MESSAGE}"
        ) from exc

    body = response.json() if response.content else {}
    text = body.get("response")
    if text is None:
        raise ValueError("Ollama response did not include a 'response' field.")
    return str(text)
