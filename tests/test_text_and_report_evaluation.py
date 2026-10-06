import json
import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.generation.llm_validator import validate_sentiment_consistency
from backend.services.text_evaluation_service import evaluate_text_quality
from backend.services.report_service import (
    generate_report,
    get_report_for_result,
    REPORTS_DIR,
)


def test_sentiment_consistency_validation():
    # Positive sentiment with positive wording
    pos_text = "I absolutely love this product! The quality is amazing and brilliant."
    assert validate_sentiment_consistency(pos_text, "Positive") is True

    # Negative sentiment with negative wording
    neg_text = "Terrible experience, completely broken, awful customer service and useless."
    assert validate_sentiment_consistency(neg_text, "Negative") is True

    # Negative sentiment with overwhelmingly positive words -> contradiction
    contradictory_neg = "This is brilliant, wonderful, fantastic, perfect, excellent!"
    assert validate_sentiment_consistency(contradictory_neg, "Negative") is False

    # Positive sentiment with overwhelmingly negative words -> contradiction
    contradictory_pos = "Terrible, horrible, awful, worst product ever, disgusting."
    assert validate_sentiment_consistency(contradictory_pos, "Positive") is False


def test_text_evaluation_metrics():
    real_df = pd.DataFrame({
        "Text": [
            "Great customer service and fast delivery.",
            "The package arrived broken and damaged.",
            "Excellent quality, highly recommended to everyone.",
            "Worst purchase ever, completely useless.",
        ],
        "Sentiment": ["Positive", "Negative", "Positive", "Negative"],
    })

    synthetic_df = pd.DataFrame({
        "Text": [
            "Outstanding service and very fast delivery time.",
            "Items were damaged upon arrival, disappointing.",
            "Superb build quality, would definitely buy again.",
            "Total waste of money, utterly useless item.",
        ],
        "Sentiment": ["Positive", "Negative", "Positive", "Negative"],
    })

    configs = [
        {"column_name": "Text", "data_type": "string", "generation_method": "llm_text"},
        {"column_name": "Sentiment", "data_type": "categorical"},
    ]

    res = evaluate_text_quality(
        real_dataframe=real_df,
        synthetic_dataframe=synthetic_df,
        column_configurations=configs,
    )

    assert res["status"] in ["evaluated", "completed"]
    assert "Text" in res["columns"]
    assert res["overall_score"] is not None
    assert res["overall_score"] > 60.0

    text_metrics = res["columns"]["Text"]["metrics"]
    assert "near_duplicate_rate" in text_metrics
    assert "originality_rate" in text_metrics
    assert "length_similarity" in text_metrics
    assert "vocabulary_similarity" in text_metrics
    assert "semantic_consistency" in text_metrics

    # Check originality (non-verbatim copying)
    assert text_metrics["originality_rate"] == 1.0  # None of sentences were copied verbatim!
    # Check near-duplicate rate is low
    assert text_metrics["near_duplicate_rate"] < 0.5


def test_text_evaluation_no_text_columns():
    real_df = pd.DataFrame({"id": [1, 2, 3], "value": [10.5, 20.0, 30.2]})
    synthetic_df = pd.DataFrame({"id": [1, 2, 3], "value": [11.0, 21.0, 29.5]})

    res = evaluate_text_quality(
        real_dataframe=real_df,
        synthetic_dataframe=synthetic_df,
    )

    assert res["status"] == "not_applicable"
    assert res["overall_score"] is None
    assert "reason" in res


@patch("backend.services.report_service.get_generated_result_by_id")
@patch("backend.services.report_service.get_dataset_user_id")
@patch("backend.services.report_service.get_dataset_by_id")
@patch("backend.services.report_service.get_evaluation_by_result_id")
@patch("backend.services.report_service.save_report")
def test_report_generation_end_to_end(
    mock_save_report,
    mock_get_eval,
    mock_get_ds_by_id,
    mock_get_user_id,
    mock_get_gen_res,
    tmp_path,
):
    result_id = 999
    user_id = 42
    dataset_id = 123

    mock_get_gen_res.return_value = {
        "result_id": result_id,
        "run_id": 55,
        "dataset_id": dataset_id,
        "model_name": "llm_text",
        "row_count": 100,
        "column_count": 4,
    }
    mock_get_user_id.return_value = user_id
    mock_get_ds_by_id.return_value = {
        "dataset_id": dataset_id,
        "name": "Customer Feedback Dataset",
    }
    mock_get_eval.return_value = {
        "evaluation_id": 88,
        "result_id": result_id,
        "overall_score": 82.5,
        "utility_metrics": {
            "statistical_similarity": {
                "overall_score": 85.0,
                "evaluated_columns": 3,
                "excluded_columns": 1,
                "total_common_columns": 4,
                "columns": {
                    "Sentiment": {
                        "column_type": "categorical",
                        "status": "evaluated",
                        "score": 90.0,
                    },
                    "Score": {
                        "column_type": "numerical",
                        "status": "evaluated",
                        "score": 80.0,
                    },
                    "Feedback": {
                        "column_type": "text",
                        "status": "excluded",
                        "reason": "free_form_text",
                        "score": None,
                    },
                },
            },
            "correlation_covariance": {
                "status": "completed",
                "overall_score": 78.0,
                "numerical_columns": ["Score"],
            },
            "ml_utility": {
                "status": "completed",
                "overall_score": 84.0,
                "task_type": "Classification",
                "target_column": "Sentiment",
            },
            "relationship_integrity": {
                "status": "not_applicable",
                "overall_score": None,
                "message": "Single table dataset",
            },
            "text_evaluation": {
                "status": "completed",
                "overall_score": 88.0,
                "columns": {
                    "Feedback": {
                        "score": 88.0,
                        "metrics": {
                            "near_duplicate_rate": 0.05,
                            "originality_rate": 0.98,
                            "length_similarity": {"char_length_similarity": 0.92},
                            "semantic_consistency": {"consistency_rate": 0.95},
                        },
                    },
                },
            },
        },
    }
    mock_save_report.return_value = {
        "report_id": 77,
        "result_id": result_id,
        "report_name": "Synthetic Data Report - Customer Feedback Dataset",
        "report_path": "reports/report_dataset_123_result_999.html",
        "generated_at": "2026-10-03T18:00:00",
    }

    report = generate_report(result_id=result_id, user_id=user_id, format="json")

    assert report["report_id"] == 77
    assert report["metadata"]["dataset_id"] == dataset_id
    assert report["executive_summary"]["rating"] in ["EXCELLENT", "GOOD"]
    assert report["executive_summary"]["overall_quality_score"] == 82.5

    # Check that all 6 sections exist
    assert "statistical_similarity" in report
    assert "correlation_covariance" in report
    assert "ml_utility" in report
    assert "relationship_integrity" in report
    assert "text_evaluation" in report
    assert "privacy" in report

    # Check generated artifacts on disk
    json_path = Path(report["artifacts"]["json"])
    html_path = Path(report["artifacts"]["html"])
    csv_path = Path(report["artifacts"]["csv"])

    assert json_path.exists()
    assert html_path.exists()
    assert csv_path.exists()

    # Verify JSON content
    with open(json_path, "r", encoding="utf-8") as f:
        loaded_json = json.load(f)
        assert loaded_json["report_name"] == report["report_name"]

    # Verify HTML contains key elements
    with open(html_path, "r", encoding="utf-8") as f:
        html_text = f.read()
        assert "Customer Feedback Dataset" in html_text
        assert "Executive Summary" in html_text
        assert "Statistical Similarity (US-023)" in html_text
        assert "Free-Form Text Quality &amp; Conditioning" in html_text or "Free-Form Text Quality" in html_text
        assert "Excluded (free_form_text)" in html_text

    # Verify CSV summary contains rows
    with open(csv_path, "r", encoding="utf-8") as f:
        csv_text = f.read()
        assert "Statistical Similarity" in csv_text
        assert "Text Evaluation" in csv_text
        assert "Feedback" in csv_text


def test_report_and_download_api_endpoints():
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.utils.auth_dependency import get_current_user

    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: 42

    with patch("backend.controllers.report_controller.get_report_for_result") as mock_get_report:
        mock_get_report.return_value = {
            "report_name": "Test Report",
            "metadata": {"result_id": 999, "dataset_id": 123},
            "executive_summary": {"overall_quality_score": 85.0},
        }

        # Test GET /report with result_id
        res = client.get("/report?result_id=999")
        assert res.status_code == 200
        assert res.json()["status"] == "success"
        assert res.json()["data"]["report_name"] == "Test Report"

    with patch("backend.controllers.report_controller.generate_report") as mock_gen_report:
        mock_gen_report.return_value = {
            "report_name": "Generated Test Report",
            "metadata": {"result_id": 999, "dataset_id": 123},
        }

        # Test POST /report
        res = client.post("/report", json={"result_id": 999, "format": "json"})
        assert res.status_code == 200
        assert res.json()["status"] == "success"

    # Test GET /download for report
    with patch("backend.controllers.download_controller.get_generated_result_by_id") as mock_get_res, \
         patch("backend.controllers.download_controller.get_dataset_user_id") as mock_user_id, \
         patch("backend.controllers.download_controller.generate_report") as mock_gen:

        mock_get_res.return_value = {"result_id": 999, "dataset_id": 123}
        mock_user_id.return_value = 42

        # Create dummy artifacts in reports dir for download test
        test_reports_dir = REPORTS_DIR
        test_reports_dir.mkdir(parents=True, exist_ok=True)
        (test_reports_dir / "report_dataset_123_result_999.html").write_text("<html>Report</html>", encoding="utf-8")
        (test_reports_dir / "report_dataset_123_result_999.json").write_text('{"report": "ok"}', encoding="utf-8")
        (test_reports_dir / "report_dataset_123_result_999_summary.csv").write_text("col,score\nA,90", encoding="utf-8")

        # HTML download
        res_html = client.get("/download?type=report&result_id=999&format=html")
        assert res_html.status_code == 200
        assert "text/html" in res_html.headers.get("content-type", "")
        assert "<html>Report</html>" in res_html.text

        # JSON download
        res_json = client.get("/download?type=report&result_id=999&format=json")
        assert res_json.status_code == 200
        assert "application/json" in res_json.headers.get("content-type", "")

        # CSV download
        res_csv = client.get("/download?type=report&result_id=999&format=csv")
        assert res_csv.status_code == 200
        assert "text/csv" in res_csv.headers.get("content-type", "")

    app.dependency_overrides.clear()

