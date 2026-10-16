import os
import shutil
import uuid
from pathlib import Path
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.repositories.generation_job_repository import (
    create_generation_job,
    delete_generation_job,
    ensure_generation_jobs_table,
    get_generation_job,
    get_generation_job_for_user,
    list_generation_jobs_for_user,
    list_incomplete_jobs_for_user,
    recover_interrupted_jobs,
    update_generation_job_progress,
    update_generation_job_status,
)
from backend.services.generation_checkpoint_service import (
    check_job_control,
    clear_job_control,
    delete_checkpoint,
    get_checkpoint_dir,
    get_checkpoint_file,
    load_checkpoint_rows,
    request_job_cancel,
    request_job_pause,
    save_checkpoint_rows,
)
from backend.services.generation_service import (
    _compute_checkpoint_batch_size,
    generate_synthetic_dataset,
)
from backend.utils.auth_dependency import get_current_user


@pytest.fixture(autouse=True)
def setup_tables():
    ensure_generation_jobs_table()


def test_compute_checkpoint_batch_size():
    assert _compute_checkpoint_batch_size(15) == 7
    assert _compute_checkpoint_batch_size(50) == 25
    assert _compute_checkpoint_batch_size(300) == 100
    assert _compute_checkpoint_batch_size(2000) == 200
    assert _compute_checkpoint_batch_size(500, param_batch=50) == 50


def test_checkpoint_disk_operations():
    test_jid = f"test-cp-{uuid.uuid4()}"
    try:
        # Initial should be empty
        assert load_checkpoint_rows(test_jid) is None

        # Save checkpoint
        df = pd.DataFrame({"col_a": [1, 2, 3], "col_b": ["x", "y", "z"]})
        path = save_checkpoint_rows(test_jid, df)
        assert os.path.exists(path)

        # Load back
        loaded = load_checkpoint_rows(test_jid)
        assert loaded is not None
        assert len(loaded) == 3
        assert list(loaded.columns) == ["col_a", "col_b"]
        assert loaded["col_a"].tolist() == [1, 2, 3]

        # Overwrite with more rows
        df2 = pd.DataFrame({"col_a": [1, 2, 3, 4, 5], "col_b": ["x", "y", "z", "w", "v"]})
        save_checkpoint_rows(test_jid, df2)
        loaded2 = load_checkpoint_rows(test_jid)
        assert len(loaded2) == 5

        # Delete
        delete_checkpoint(test_jid)
        assert load_checkpoint_rows(test_jid) is None
    finally:
        delete_checkpoint(test_jid)


@pytest.mark.skip(reason="Control flags moved to the DB; covered by test_generation_job_control.py")
def test_job_control_signals():
    test_jid = f"test-ctrl-{uuid.uuid4()}"
    try:
        clear_job_control(test_jid)
        assert check_job_control(test_jid) is None

        request_job_pause(test_jid)
        assert check_job_control(test_jid) == "pause"

        request_job_cancel(test_jid)
        assert check_job_control(test_jid) == "cancel"

        clear_job_control(test_jid)
        assert check_job_control(test_jid) is None
    finally:
        clear_job_control(test_jid)


def test_generation_job_crud_and_status():
    # Use existing user_id=1 and dataset_id=367 from test DB
    test_jid = f"test-job-{uuid.uuid4()}"
    user_id = 1
    dataset_id = 367

    try:
        job = create_generation_job(
            job_id=test_jid,
            user_id=user_id,
            dataset_id=dataset_id,
            file_name="test_data.csv",
            model_name="gaussian_copula",
            total_rows=100,
            parameters={"random_state": 42},
            column_configurations=[{"column_name": "id", "action": "keep"}],
            llm_model=None,
        )

        assert job["job_id"] == test_jid
        assert job["user_id"] == user_id
        assert job["dataset_id"] == dataset_id
        assert job["status"] == "pending"
        assert job["total_rows"] == 100
        assert job["generated_rows"] == 0
        assert job["remaining_rows"] == 100
        assert job["progress_percent"] == 0

        # Retrieve
        fetched = get_generation_job_for_user(test_jid, user_id)
        assert fetched is not None
        assert fetched["job_id"] == test_jid

        # Wrong user returns None
        assert get_generation_job_for_user(test_jid, 999999) is None

        # Update progress
        update_generation_job_progress(
            job_id=test_jid,
            generated_rows=50,
            current_batch=2,
            total_batches=4,
            progress_percent=50,
            stage="sample",
            stage_message="Batch 2/4 completed",
            checkpoint_path="data/checkpoints/test.csv",
        )
        updated = get_generation_job(test_jid)
        assert updated["generated_rows"] == 50
        assert updated["remaining_rows"] == 50
        assert updated["current_batch"] == 2
        assert updated["progress_percent"] == 50

        # Update status to paused
        update_generation_job_status(
            job_id=test_jid,
            status="paused",
            stage_message="Paused by user",
        )
        paused = get_generation_job(test_jid)
        assert paused["status"] == "paused"

        # Check incomplete jobs list
        incomplete = list_incomplete_jobs_for_user(user_id)
        assert any(j["job_id"] == test_jid for j in incomplete)

        # Update status to completed
        update_generation_job_status(
            job_id=test_jid,
            status="completed",
            stage_message="Completed successfully",
        )
        completed = get_generation_job(test_jid)
        assert completed["status"] == "completed"

        # No longer in incomplete jobs
        incomplete_now = list_incomplete_jobs_for_user(user_id)
        assert not any(j["job_id"] == test_jid for j in incomplete_now)

        # Delete job
        assert delete_generation_job(test_jid, user_id) is True
        assert get_generation_job(test_jid) is None
    finally:
        try:
            delete_generation_job(test_jid, user_id)
        except Exception:
            pass


def test_startup_recovery_interrupted_jobs():
    test_running = f"test-rec-run-{uuid.uuid4()}"
    test_pending = f"test-rec-pen-{uuid.uuid4()}"
    test_paused = f"test-rec-pau-{uuid.uuid4()}"
    user_id = 1
    dataset_id = 367

    try:
        # Create three jobs
        create_generation_job(
            job_id=test_running,
            user_id=user_id,
            dataset_id=dataset_id,
            file_name="running.csv",
            model_name="gaussian_copula",
            total_rows=100,
        )
        update_generation_job_status(job_id=test_running, status="running")

        create_generation_job(
            job_id=test_pending,
            user_id=user_id,
            dataset_id=dataset_id,
            file_name="pending.csv",
            model_name="ctgan",
            total_rows=100,
        )

        create_generation_job(
            job_id=test_paused,
            user_id=user_id,
            dataset_id=dataset_id,
            file_name="paused.csv",
            model_name="tvae",
            total_rows=100,
        )
        update_generation_job_status(job_id=test_paused, status="paused")

        # Run recovery
        recovered_count = recover_interrupted_jobs()
        assert recovered_count >= 2

        # Check results: running and pending are now interrupted
        assert get_generation_job(test_running)["status"] == "interrupted"
        assert get_generation_job(test_pending)["status"] == "interrupted"

        # Explicitly paused job remains paused
        assert get_generation_job(test_paused)["status"] == "paused"

    finally:
        delete_generation_job(test_running, user_id)
        delete_generation_job(test_pending, user_id)
        delete_generation_job(test_paused, user_id)


def test_generation_api_job_endpoints():
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: 1

    test_jid = f"test-api-{uuid.uuid4()}"
    try:
        create_generation_job(
            job_id=test_jid,
            user_id=1,
            dataset_id=367,
            file_name="api_test.csv",
            model_name="gaussian_copula",
            total_rows=80,
        )

        # GET /generation/jobs
        res = client.get("/generation/jobs")
        assert res.status_code == 200
        jobs = res.json().get("jobs", [])
        assert any(j["job_id"] == test_jid for j in jobs)

        # GET /generation/jobs/active
        res_active = client.get("/generation/jobs/active")
        assert res_active.status_code == 200
        active_jobs = res_active.json().get("jobs", [])
        assert any(j["job_id"] == test_jid for j in active_jobs)

        # GET /generation/jobs/{job_id}
        res_detail = client.get(f"/generation/jobs/{test_jid}")
        assert res_detail.status_code == 200
        assert res_detail.json()["job"]["job_id"] == test_jid

        # POST /generation/jobs/{job_id}/pause
        res_pause = client.post(f"/generation/jobs/{test_jid}/pause")
        assert res_pause.status_code == 200
        assert check_job_control(test_jid) == "pause"

        # POST /generation/jobs/{job_id}/cancel
        res_cancel = client.post(f"/generation/jobs/{test_jid}/cancel")
        assert res_cancel.status_code == 200
        assert check_job_control(test_jid) == "cancel"

        # DELETE /generation/jobs/{job_id}
        res_del = client.delete(f"/generation/jobs/{test_jid}")
        assert res_del.status_code == 200
        assert get_generation_job(test_jid) is None

    finally:
        delete_checkpoint(test_jid)
        clear_job_control(test_jid)
        app.dependency_overrides.pop(get_current_user, None)