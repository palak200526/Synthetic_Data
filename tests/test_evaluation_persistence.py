import pytest

from backend.repositories.evaluation_repository import (
    get_dashboard_summary,
    get_evaluation_by_result_id,
    get_evaluation_by_run_id,
    get_evaluations_by_dataset_id,
    save_evaluation_result,
)


def test_us026_save_and_retrieve_evaluation():
    # Result ID 61 is an existing result in the test DB
    test_result_id = 61

    payload = {
        "dataset_id": 367,
        "run_id": 78,
        "result_id": test_result_id,
        "status": "completed",
        "overall_score": 75.5,
        "statistical_similarity": {"overall_score": 75.5, "metric": "statistical_similarity"},
        "correlation_covariance": {"status": "not_applicable"},
        "ml_utility": {"overall_score": 70.0, "status": "evaluated"},
        "relationship_integrity": {"status": "not_applicable"},
    }

    # Save
    save_res = save_evaluation_result(
        result_id=test_result_id,
        utility_metrics=payload,
        privacy_metrics={"privacy_score": 90.0},
        overall_score=75.5,
    )

    assert save_res["evaluation_id"] is not None
    assert save_res["result_id"] == test_result_id
    assert save_res["overall_score"] == 75.5

    # Retrieve by result_id
    retrieved = get_evaluation_by_result_id(test_result_id)
    assert retrieved is not None
    assert retrieved["result_id"] == test_result_id
    assert retrieved["dataset_id"] == 367
    assert retrieved["run_id"] == 78
    assert retrieved["model_name"] is not None
    assert retrieved["overall_score"] == 75.5
    assert retrieved["utility_metrics"]["status"] == "completed"

    # Retrieve by run_id
    retrieved_by_run = get_evaluation_by_run_id(78)
    assert retrieved_by_run is not None
    assert retrieved_by_run["run_id"] == 78
    assert retrieved_by_run["result_id"] == test_result_id

    # Retrieve by dataset_id
    dataset_evals = get_evaluations_by_dataset_id(367)
    assert len(dataset_evals) >= 1
    assert any(e["result_id"] == test_result_id for e in dataset_evals)


def test_us026_dashboard_summary():
    # User ID 2 is the test user owning dataset 367
    summary = get_dashboard_summary(2)

    assert "total_datasets" in summary
    assert "total_generations" in summary
    assert "total_evaluations" in summary
    assert "average_score" in summary
    assert "recent_datasets" in summary
    assert "recent_generations" in summary
    assert "recent_evaluations" in summary

    assert summary["total_datasets"] >= 1
    assert summary["total_evaluations"] >= 1
    assert len(summary["recent_evaluations"]) >= 1
