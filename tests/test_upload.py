import io

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.utils.auth_dependency import get_current_user


client = TestClient(app)

# The upload/profile routes require a logged-in user. Instead of creating a
# real token, we tell FastAPI to treat every request in this file as coming
# from this user. This ID must exist in the `users` table of your test DB
# (sessions/datasets have a foreign key to it). Change it if needed.
TEST_USER_ID = 1


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _csv_file(name: str, content: str):
    return (
        "files",
        (
            name,
            io.BytesIO(content.encode("utf-8")),
            "text/csv",
        ),
    )


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
        files=[_csv_file("test.csv", csv_content)],
    )

    assert response.status_code == 200

    result = response.json()

    assert result["status"] == "success"
    assert "datasets" in result
    assert len(result["datasets"]) == 1

    dataset = result["datasets"][0]["data"]

    assert dataset["filename"] == "test.csv"
    assert dataset["rows"] == 3
    assert dataset["columns"] == 3
    assert dataset["column_names"] == [
        "customer_id",
        "age",
        "gender",
    ]


def test_unsupported_file():
    response = client.post(
        "/upload",
        files=[
            (
                "files",
                (
                    "test.txt",
                    io.BytesIO(b"hello world"),
                    "text/plain",
                ),
            )
        ],
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
        files=[_csv_file("profile_test.csv", csv_content)],
    )

    assert upload_response.status_code == 200

    # The profile route is now /profile/{dataset_id} (an integer), not the
    # filename, so take the ID from the upload response.
    dataset_id = upload_response.json()["datasets"][0]["dataset_id"]

    profile_response = client.get(f"/profile/{dataset_id}")

    assert profile_response.status_code == 200

    profile = profile_response.json()["data"]

    assert profile["basic"]["row_count"] == 3
    assert profile["basic"]["column_count"] == 4
    assert "age" in profile["column_types"]["numerical_columns"]
    assert "gender" in profile["column_types"]["categorical_columns"]