"""Contract tests for the Improve Quality API handler.

These tests isolate the controller from database/model work and verify that the
endpoint forwards request parameters and maps expected errors to HTTP statuses.
"""

import pytest
from fastapi import HTTPException

from backend.schemas.api_schema import ImproveQualityRequest
from backend.controllers import generation_controller


def test_improve_quality_endpoint_returns_improvement_payload(monkeypatch):
    expected = {
        "status": "success",
        "baseline_result_id": 10,
        "improved_result_id": 11,
        "selected_candidate": "enhanced_candidate",
        "candidate_comparison": [{"candidate": "baseline", "score": 70.0}],
        "metrics_comparison": [{"metric": "completeness", "baseline": 95.0, "improved": 100.0}],
    }
    captured = {}

    def fake_improve_generation_result(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(
        generation_controller, "improve_generation_result", fake_improve_generation_result
    )

    request = ImproveQualityRequest(
        result_id=10,
        parameters={"enable_cyclical_encoding": True},
        max_attempts=4,
        improvement_threshold=0.5,
        target_column="target",
    )

    response = generation_controller.improve_quality_endpoint(request, user_id=7)

    assert response == expected
    assert captured == {
        "result_id": 10,
        "user_id": 7,
        "parameters": {"enable_cyclical_encoding": True},
        "max_attempts": 4,
        "improvement_threshold": 0.5,
        "target_column": "target",
    }


def test_improve_quality_endpoint_maps_permission_error(monkeypatch):
    def fail_permission(**kwargs):
        raise PermissionError("Access denied.")

    monkeypatch.setattr(generation_controller, "improve_generation_result", fail_permission)

    with pytest.raises(HTTPException) as exc:
        generation_controller.improve_quality_endpoint(
            ImproveQualityRequest(result_id=10), user_id=7
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Access denied."


@pytest.mark.parametrize(
    "error",
    [ValueError("Invalid result."), FileNotFoundError("Dataset file not found.")],
)
def test_improve_quality_endpoint_maps_input_errors(monkeypatch, error):
    def fail_input(**kwargs):
        raise error

    monkeypatch.setattr(generation_controller, "improve_generation_result", fail_input)

    with pytest.raises(HTTPException) as exc:
        generation_controller.improve_quality_endpoint(
            ImproveQualityRequest(result_id=10), user_id=7
        )

    assert exc.value.status_code == 400
    assert str(error) == exc.value.detail
