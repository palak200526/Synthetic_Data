"""API tests: ownership, 409 guards, double-resume, Celery arg passing."""
try:  # works whether or not tests/ is a package
    from .gen_job_fixtures import *  # noqa: F401,F403
except ImportError:
    from gen_job_fixtures import *  # noqa: F401,F403

import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient

from backend.controllers import generation_controller as ctl
from backend.utils.auth_dependency import get_current_user


@pytest.fixture
def enqueued(monkeypatch):
    calls = []
    monkeypatch.setattr(ctl, "_enqueue_generation", lambda **kw: calls.append(kw) or kw["job_id"])
    return calls


@pytest.fixture
def client(db, enqueued):
    app = FastAPI()
    app.include_router(ctl.router)
    # test auth: "X-Test-User: <id>" header instead of a real JWT
    def fake_user(x_test_user: int = Header(...)):
        return x_test_user
    app.dependency_overrides[get_current_user] = fake_user
    return TestClient(app)


def as_user(uid):
    return {"X-Test-User": str(uid)}


# ---------------- ownership (item 9) ----------------

JOB_ROUTES = [
    ("get", "/generation/jobs/job-1"),
    ("get", "/generation/status/job-1"),
    ("post", "/generation/jobs/job-1/pause"),
    ("post", "/generation/jobs/job-1/resume"),
    ("post", "/generation/jobs/job-1/restart"),
    ("post", "/generation/jobs/job-1/cancel"),
    ("delete", "/generation/jobs/job-1"),
]


@pytest.mark.parametrize("method,url", JOB_ROUTES)
def test_other_users_cannot_touch_my_job(client, make_job, method, url):
    make_job(status="paused", user_id=1)
    resp = getattr(client, method)(url, headers=as_user(2))
    assert resp.status_code == 404
    # and the job is untouched
    assert client.get("/generation/jobs/job-1", headers=as_user(1)).json()["job"]["status"] == "paused"


@pytest.mark.parametrize("method,url", JOB_ROUTES)
def test_unauthenticated_requests_are_rejected(client, make_job, method, url):
    make_job(status="paused")
    assert getattr(client, method)(url).status_code in (401, 403, 422)


def test_job_list_only_shows_my_jobs(client, make_job):
    make_job("mine", user_id=1, dataset_id=1)
    make_job("theirs", user_id=2, dataset_id=2)
    ids = [j["job_id"] for j in client.get("/generation/jobs", headers=as_user(1)).json()["jobs"]]
    assert ids == ["mine"]


# ---------------- pause ----------------

def test_pause_running_job_ok(client, make_job):
    make_job(status="running")
    assert client.post("/generation/jobs/job-1/pause", headers=as_user(1)).status_code == 200


@pytest.mark.parametrize("status", ["paused", "completed", "interrupted", "failed"])
def test_pause_non_running_job_is_409(client, make_job, status):
    make_job(status=status)
    assert client.post("/generation/jobs/job-1/pause", headers=as_user(1)).status_code == 409


# ---------------- resume ----------------

def test_resume_paused_job_enqueues_once_with_resume_flag(client, make_job, enqueued):
    make_job(status="paused")
    resp = client.post("/generation/jobs/job-1/resume", headers=as_user(1))
    assert resp.status_code == 200
    assert len(enqueued) == 1 and enqueued[0]["resume"] is True and enqueued[0]["job_id"] == "job-1"
    assert client.get("/generation/jobs/job-1", headers=as_user(1)).json()["job"]["status"] == "running"


def test_double_click_resume_second_call_is_409_and_enqueues_once(client, make_job, enqueued):
    make_job(status="interrupted")
    first = client.post("/generation/jobs/job-1/resume", headers=as_user(1))
    second = client.post("/generation/jobs/job-1/resume", headers=as_user(1))
    assert (first.status_code, second.status_code) == (200, 409)
    assert len(enqueued) == 1


def test_resume_completed_job_is_400(client, make_job, enqueued):
    make_job(status="completed")
    assert client.post("/generation/jobs/job-1/resume", headers=as_user(1)).status_code == 400
    assert enqueued == []


def test_failed_enqueue_puts_job_back_to_interrupted(client, make_job, monkeypatch):
    make_job(status="paused")
    def boom(**kw): raise RuntimeError("redis down")
    monkeypatch.setattr(ctl, "_enqueue_generation", boom)
    assert client.post("/generation/jobs/job-1/resume", headers=as_user(1)).status_code == 500
    # not stuck as 'running' forever -> user can click Resume again
    assert client.get("/generation/jobs/job-1", headers=as_user(1)).json()["job"]["status"] == "interrupted"


# ---------------- restart / cancel / discard ----------------

def test_restart_resets_and_enqueues_fresh_run(client, make_job, enqueued, db):
    make_job(status="paused")
    db.update_generation_job_progress(job_id="job-1", generated_rows=600, current_batch=6,
        total_batches=10, progress_percent=60, stage="sample", stage_message="x")
    assert client.post("/generation/jobs/job-1/restart", headers=as_user(1)).status_code == 200
    job = client.get("/generation/jobs/job-1", headers=as_user(1)).json()["job"]
    assert job["generated_rows"] == 0 and enqueued[0]["resume"] is False


def test_restart_running_job_is_409(client, make_job, enqueued):
    make_job(status="running")
    assert client.post("/generation/jobs/job-1/restart", headers=as_user(1)).status_code == 409
    assert enqueued == []


def test_cancel_completed_is_409_cancel_paused_ok(client, make_job):
    make_job("done", status="completed")
    make_job("pz", status="paused")
    assert client.post("/generation/jobs/done/cancel", headers=as_user(1)).status_code == 409
    assert client.post("/generation/jobs/pz/cancel", headers=as_user(1)).status_code == 200
    assert client.get("/generation/jobs/pz", headers=as_user(1)).json()["job"]["status"] == "cancelled"


def test_discard_removes_job_and_checkpoint(client, make_job, tmp_path):
    make_job(status="paused")
    ck = tmp_path / "data" / "checkpoints" / "job-1"
    ck.mkdir(parents=True); (ck / "checkpoint.csv").write_text("a\n1\n")
    assert client.delete("/generation/jobs/job-1", headers=as_user(1)).status_code == 200
    assert not ck.exists()
    assert client.get("/generation/jobs/job-1", headers=as_user(1)).status_code == 404


# ---------------- starting a generation ----------------

@pytest.fixture
def start_deps(monkeypatch):
    import pandas as pd
    # dataset 1 belongs to user 1, dataset 2 to user 2 (same as the conftest seed data)
    monkeypatch.setattr(ctl, "get_dataset_user_id", lambda dataset_id: {1: 1, 2: 2}[dataset_id])
    monkeypatch.setattr(ctl, "prepare_dataset_for_generation",
        lambda dataset_id: {"filename": "orders.csv", "dataframe": pd.DataFrame({"a": range(50)}), "configurations": []})


def test_start_generation_registers_job_before_enqueue(client, db, enqueued, start_deps):
    resp = client.post("/generation", headers=as_user(1),
        json={"dataset_id": 1, "model_name": "gaussian_copula", "parameters": {"num_rows": 120}})
    assert resp.status_code == 200
    job = db.get_generation_job(resp.json()["job_id"])
    assert job["total_rows"] == 120 and job["status"] == "pending" and job["file_name"] == "orders.csv"
    assert len(enqueued) == 1


def test_cannot_start_generation_on_someone_elses_dataset(client, db, enqueued, start_deps):
    resp = client.post("/generation", headers=as_user(1),
        json={"dataset_id": 2, "model_name": "gaussian_copula", "parameters": {}})
    assert resp.status_code == 403
    assert db.list_generation_jobs_for_user(1) == [] and db.list_generation_jobs_for_user(2) == []
    assert enqueued == []


def test_job_registration_failure_is_not_silent(client, db, enqueued, start_deps, monkeypatch):
    def boom(**kw): raise RuntimeError("db write failed")
    monkeypatch.setattr(ctl, "create_generation_job", boom)
    resp = client.post("/generation", headers=as_user(1),
        json={"dataset_id": 1, "model_name": "gaussian_copula", "parameters": {}})
    assert resp.status_code == 500
    assert enqueued == []  # no untracked generation was started


# ---------------- Celery path gets job_id + resume ----------------

def test_enqueue_passes_job_id_and_resume_to_celery(monkeypatch):
    sent = {}
    class FakeTask:
        def apply_async(self, args=None, task_id=None):
            sent.update(args=args, task_id=task_id)
    monkeypatch.setattr(ctl, "redis_is_available", lambda url: True)
    monkeypatch.setattr(ctl, "generate_dataset_task", FakeTask())
    ctl._enqueue_generation(dataset_id=1, model_name="ctgan", user_id=7,
        parameters={"num_rows": 10}, job_id="job-9", resume=True)
    assert sent["args"] == [1, "ctgan", 7, {"num_rows": 10}, "job-9", True]
    assert sent["task_id"] == "job-9"


def test_celery_task_forwards_job_id_and_resume(monkeypatch):
    from backend.worker import tasks
    seen = {}
    monkeypatch.setattr(tasks, "run_generation", lambda **kw: seen.update(kw) or {"status": "paused"})
    result = tasks.generate_dataset_task.apply(args=[1, "ctgan", 7, {"num_rows": 10}, "job-9", True])
    assert result.get() == {"status": "paused"}
    assert seen["job_id"] == "job-9" and seen["resume"] is True and seen["user_id"] == 7
