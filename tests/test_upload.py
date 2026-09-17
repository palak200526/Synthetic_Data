import io

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_health_check():

    response = client.get("/health")

    assert response.status_code == 200

    assert response.json()["status"] == "healthy"


def test_upload_csv():

    csv_content = """customer_id,age,gender
1,25,Male
2,30,Female
3,28,Male
"""

    response = client.post(
        "/upload",
        files={
            "file": (
                "test.csv",
                io.BytesIO(
                    csv_content.encode("utf-8")
                ),
                "text/csv"
            )
        }
    )

    assert response.status_code == 200

    result = response.json()

    assert result["status"] == "success"

    assert result["data"]["rows"] == 3

    assert result["data"]["columns"] == 3


def test_unsupported_file():

    response = client.post(
        "/upload",
        files={
            "file": (
                "test.txt",
                io.BytesIO(
                    b"hello world"
                ),
                "text/plain"
            )
        }
    )

    assert response.status_code == 400

    assert "Unsupported file type" in response.json()["message"]


def test_dataset_profile():

    csv_content = """customer_id,age,gender,income
1,25,Male,45000
2,30,Female,52000
3,28,Male,48000
"""

    upload_response = client.post(
        "/upload",
        files={
            "file": (
                "profile_test.csv",
                io.BytesIO(
                    csv_content.encode("utf-8")
                ),
                "text/csv"
            )
        }
    )

    assert upload_response.status_code == 200

    profile_response = client.get(
        "/profile/profile_test.csv"
    )

    assert profile_response.status_code == 200

    result = profile_response.json()

    profile = result["data"]

    assert profile["basic"]["row_count"] == 3

    assert profile["basic"]["column_count"] == 4

    assert "age" in (
        profile["column_types"]
        ["numerical_columns"]
    )

    assert "gender" in (
        profile["column_types"]
        ["categorical_columns"]
    )