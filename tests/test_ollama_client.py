from unittest.mock import MagicMock, patch

import pytest
import requests

from backend.services.ollama_client import (
    MODEL_MISSING_MESSAGE,
    OLLAMA_UNAVAILABLE_MESSAGE,
    check_ollama_available,
    ensure_ollama_ready,
    ollama_generate,
)


@patch("backend.services.ollama_client._SESSION")
def test_check_ollama_available_true(mock_session):
    response = MagicMock()
    response.status_code = 200
    mock_session.get.return_value = response
    assert check_ollama_available(base_url="http://localhost:11434") is True
    mock_session.get.assert_called_once()
    assert "/api/tags" in mock_session.get.call_args.args[0]


@patch("backend.services.ollama_client._SESSION")
def test_check_ollama_available_false_on_connection_error(mock_session):
    mock_session.get.side_effect = requests.ConnectionError("down")
    assert check_ollama_available() is False


@patch("backend.services.ollama_client.check_ollama_model", return_value=True)
@patch("backend.services.ollama_client.check_ollama_available", return_value=True)
def test_ensure_ollama_ready_ok(mock_available, mock_model):
    ensure_ollama_ready(model="qwen2.5:1.5b", base_url="http://localhost:11434")
    mock_available.assert_called_once()
    mock_model.assert_called_once()


@patch("backend.services.ollama_client.check_ollama_available", return_value=False)
def test_ensure_ollama_ready_raises_when_server_down(mock_available):
    with pytest.raises(RuntimeError, match="Local Ollama service is unavailable"):
        ensure_ollama_ready()
    assert OLLAMA_UNAVAILABLE_MESSAGE


@patch("backend.services.ollama_client.check_ollama_model", return_value=False)
@patch("backend.services.ollama_client.check_ollama_available", return_value=True)
def test_ensure_ollama_ready_raises_when_model_missing(mock_available, mock_model):
    with pytest.raises(RuntimeError, match="not installed"):
        ensure_ollama_ready(model="missing:tag")
    assert "missing:tag" in MODEL_MISSING_MESSAGE.format(model="missing:tag")


@patch("backend.services.ollama_client._SESSION")
def test_ollama_generate_posts_to_local_api(mock_session):
    response = MagicMock()
    response.content = b'{"response":"hello"}'
    response.json.return_value = {"response": "hello"}
    response.raise_for_status.return_value = None
    mock_session.post.return_value = response

    text = ollama_generate(
        "Write one sentence",
        model="qwen2.5:1.5b",
        base_url="http://localhost:11434",
        timeout=10,
    )

    assert text == "hello"
    url = mock_session.post.call_args.args[0]
    payload = mock_session.post.call_args.kwargs["json"]
    assert url == "http://localhost:11434/api/generate"
    assert payload["model"] == "qwen2.5:1.5b"
    assert payload["prompt"] == "Write one sentence"
    assert payload["stream"] is False


@patch("backend.services.ollama_client._SESSION")
def test_ollama_generate_timeout(mock_session):
    mock_session.post.side_effect = requests.Timeout("slow")
    with pytest.raises(TimeoutError, match="timed out"):
        ollama_generate("prompt", timeout=1)
