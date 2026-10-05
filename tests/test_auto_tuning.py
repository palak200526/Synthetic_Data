from unittest.mock import MagicMock, patch
import pytest

from backend.services.auto_tuning_service import (
    auto_tune_generation,
    identify_weak_metrics,
    tune_generation_parameters,
)


def test_us022_identify_weak_metrics():
    eval_payload = {
        "overall_score": 65.0,
        "statistical_similarity": {
            "overall_score": 65.0,
            "columns": {
                "col_a": {"column_type": "numerical", "score": 45.0},
                "col_b": {"column_type": "categorical", "score": 85.0},
            },
        },
        "correlation_covariance": {"overall_score": 55.0},
        "ml_utility": {"overall_score": 60.0},
    }

    weak = identify_weak_metrics(eval_payload)

    assert weak["low_statistical"] is True
    assert weak["low_correlation"] is True
    assert weak["low_ml_utility"] is True
    assert len(weak["weak_columns"]) == 1
    assert weak["weak_columns"][0]["column"] == "col_a"


def test_us022_parameter_tuning_only_tunes_supported():
    eval_payload = {
        "overall_score": 60.0,
        "statistical_similarity": {"overall_score": 60.0, "columns": {}},
        "correlation_covariance": {"overall_score": 50.0},
    }

    # 1. Gaussian Copula only tunes random_state
    gc_tuned = tune_generation_parameters(
        model_name="gaussian_copula",
        current_params={"random_state": 42},
        evaluation=eval_payload,
        attempt=1,
    )
    assert "random_state" in gc_tuned
    assert gc_tuned["random_state"] != 42
    assert "epochs" not in gc_tuned
    assert "latent_dim" not in gc_tuned

    # 2. CTGAN tunes supported: epochs, lr, batch_size, random_state
    ctgan_tuned = tune_generation_parameters(
        model_name="ctgan",
        current_params={"epochs": 100, "learning_rate": 0.0002, "batch_size": 32},
        evaluation=eval_payload,
        attempt=1,
    )
    assert ctgan_tuned["epochs"] > 100
    assert ctgan_tuned["learning_rate"] < 0.0002
    assert "latent_dim" not in ctgan_tuned

    # 3. TVAE tunes supported: latent_dim, epochs, lr, batch_size, random_state
    tvae_tuned = tune_generation_parameters(
        model_name="tvae",
        current_params={"latent_dim": 16, "epochs": 100, "learning_rate": 0.001},
        evaluation=eval_payload,
        attempt=1,
    )
    assert tvae_tuned["latent_dim"] == 32
    assert tvae_tuned["epochs"] > 100


def test_us022_stopping_by_score_threshold():
    # Mock generation and evaluation to return scores 70.0 on attempt 1, 85.0 on attempt 2
    mock_gen = MagicMock(side_effect=[
        {"result_id": 101, "run_id": 201},
        {"result_id": 102, "run_id": 202},
    ])
    mock_eval = MagicMock(side_effect=[
        {"overall_score": 70.0, "evaluation": {"overall_score": 70.0}},
        {"overall_score": 85.0, "evaluation": {"overall_score": 85.0}},
    ])

    with patch("backend.services.auto_tuning_service.generate_synthetic_dataset", mock_gen), \
         patch("backend.services.auto_tuning_service.evaluate_generation", mock_eval):

        result = auto_tune_generation(
            dataset_id=1,
            model_name="gaussian_copula",
            user_id=1,
            max_attempts=5,
            min_score=80.0,
            improvement_threshold=1.0,
        )

        assert result["status"] == "success"
        assert result["total_attempts"] == 2
        assert result["best_score"] == 85.0
        assert result["best_result_id"] == 102
        assert "Target score satisfied" in result["stop_reason"]


def test_us022_stopping_by_max_attempts():
    mock_gen = MagicMock(return_value={"result_id": 101, "run_id": 201})
    mock_eval = MagicMock(side_effect=[
        {"overall_score": 60.0, "evaluation": {"overall_score": 60.0}},
        {"overall_score": 63.0, "evaluation": {"overall_score": 63.0}},
        {"overall_score": 65.0, "evaluation": {"overall_score": 65.0}},
    ])

    with patch("backend.services.auto_tuning_service.generate_synthetic_dataset", mock_gen), \
         patch("backend.services.auto_tuning_service.evaluate_generation", mock_eval):

        result = auto_tune_generation(
            dataset_id=1,
            model_name="gaussian_copula",
            user_id=1,
            max_attempts=3,
            min_score=85.0,
            improvement_threshold=1.0,
        )

        assert result["total_attempts"] == 3
        assert result["best_score"] == 65.0
        assert "Maximum attempts reached" in result["stop_reason"]


def test_us022_stopping_by_improvement_threshold():
    mock_gen = MagicMock(return_value={"result_id": 101, "run_id": 201})
    # Attempt 1: 65.0, Attempt 2: 65.2 (improvement 0.2 < threshold 1.0)
    mock_eval = MagicMock(side_effect=[
        {"overall_score": 65.0, "evaluation": {"overall_score": 65.0}},
        {"overall_score": 65.2, "evaluation": {"overall_score": 65.2}},
    ])

    with patch("backend.services.auto_tuning_service.generate_synthetic_dataset", mock_gen), \
         patch("backend.services.auto_tuning_service.evaluate_generation", mock_eval):

        result = auto_tune_generation(
            dataset_id=1,
            model_name="gaussian_copula",
            user_id=1,
            max_attempts=5,
            min_score=85.0,
            improvement_threshold=1.0,
        )

        assert result["total_attempts"] == 2
        assert "Improvement below threshold" in result["stop_reason"]
        assert result["best_score"] == 65.2
