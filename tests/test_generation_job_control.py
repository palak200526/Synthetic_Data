"""Repository + control-flag tests: pause/cancel across processes, atomic resume."""
try:  # works whether or not tests/ is a package
    from .gen_job_fixtures import *  # noqa: F401,F403
except ImportError:
    from gen_job_fixtures import *  # noqa: F401,F403

import threading

import pytest

from backend.services import generation_checkpoint_service as ckpt


# ---------- cross-process pause / cancel (the Celery-worker case) ----------

def test_pause_is_visible_to_a_different_process(db, make_job):
    make_job(status="running")
    ckpt.request_job_pause("job-1")

    # Simulate the worker being another process: it has NO in-memory flag.
    ckpt._JOB_CONTROLS.clear()
    assert ckpt.check_job_control("job-1") == "pause"


def test_clear_control_removes_db_flag_too(db, make_job):
    make_job(status="running")
    ckpt.request_job_pause("job-1")
    ckpt.clear_job_control("job-1")
    ckpt._JOB_CONTROLS.clear()
    assert ckpt.check_job_control("job-1") is None


def test_cancel_request_is_visible_to_other_process(db, make_job):
    make_job(status="running")
    ckpt.request_job_cancel("job-1")
    ckpt._JOB_CONTROLS.clear()
    assert ckpt.check_job_control("job-1") == "cancel"


def test_pause_request_ignored_for_non_running_job(db, make_job):
    make_job(status="paused")
    assert db.set_job_control_request("job-1", "pause") is False
    assert ckpt.check_job_control("job-1") is None


def test_set_control_respects_owner(db, make_job):
    make_job(status="running", user_id=1)
    assert db.set_job_control_request("job-1", "pause", user_id=2) is False
    assert db.set_job_control_request("job-1", "pause", user_id=1) is True


def test_discarded_job_row_means_worker_must_stop(db, make_job):
    make_job(status="running")
    db.delete_generation_job("job-1", 1)
    ckpt._JOB_CONTROLS.clear()
    assert ckpt.check_job_control("job-1") == "cancel"


def test_early_pause_survives_fresh_job_startup(db, make_job):
    """Pause clicked while the job is still queued must not be wiped at start."""
    make_job(status="pending")
    ckpt.request_job_pause("job-1")
    ckpt.clear_local_job_control("job-1")  # what a fresh start now does
    ckpt._JOB_CONTROLS.clear()
    assert ckpt.check_job_control("job-1") == "pause"


def test_invalid_control_request_rejected(db, make_job):
    make_job()
    with pytest.raises(ValueError):
        db.set_job_control_request("job-1", "explode")


# ---------- atomic resume / restart ----------

@pytest.mark.parametrize("status", ["paused", "interrupted", "failed"])
def test_resume_claim_allowed_states(db, make_job, status):
    make_job(status=status)
    assert db.claim_job_for_resume("job-1", 1) is True
    job = db.get_generation_job("job-1")
    assert job["status"] == "running"
    assert job["error_message"] is None


@pytest.mark.parametrize("status", ["running", "pending", "completed", "cancelled"])
def test_resume_claim_rejected_states(db, make_job, status):
    make_job(status=status)
    assert db.claim_job_for_resume("job-1", 1) is False
    assert db.get_generation_job("job-1")["status"] == status


def test_resume_claim_rejected_for_other_user(db, make_job):
    make_job(status="paused", user_id=1)
    assert db.claim_job_for_resume("job-1", 2) is False
    assert db.get_generation_job("job-1")["status"] == "paused"


def test_concurrent_resume_has_exactly_one_winner(db, make_job):
    make_job(status="paused")
    results, barrier = [], threading.Barrier(8)

    def worker():
        barrier.wait()
        results.append(db.claim_job_for_resume("job-1", 1))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert results.count(True) == 1
    assert results.count(False) == 7


def test_resume_claim_clears_pending_pause(db, make_job):
    make_job(status="paused")
    # a stale pause request left behind in the DB
    import psycopg2  # noqa: F401
    conn = db.get_db_connection()
    conn.cursor().execute("UPDATE generation_jobs SET control_request='pause'")
    conn.commit(); conn.close()

    assert db.claim_job_for_resume("job-1", 1) is True
    ckpt._JOB_CONTROLS.clear()
    assert ckpt.check_job_control("job-1") is None


def test_restart_claim_resets_progress(db, make_job):
    make_job(status="paused", total_rows=1000)
    db.update_generation_job_progress(
        job_id="job-1", generated_rows=400, current_batch=4, total_batches=10,
        progress_percent=40, stage="sample", stage_message="x", checkpoint_path="p",
    )
    assert db.claim_job_for_restart("job-1", 1) is True
    job = db.get_generation_job("job-1")
    assert (job["status"], job["generated_rows"], job["progress_percent"]) == ("running", 0, 0)
    assert job["remaining_rows"] == 1000


@pytest.mark.parametrize("status", ["running", "pending"])
def test_restart_claim_rejected_while_active(db, make_job, status):
    make_job(status=status)
    assert db.claim_job_for_restart("job-1", 1) is False


# ---------- recovery after backend restart ----------

def test_recovery_marks_active_jobs_interrupted_but_keeps_paused(db, make_job):
    make_job("a", status="running")
    make_job("b", status="pending")
    make_job("c", status="paused")
    make_job("d", status="completed")
    db.set_job_control_request("a", "pause")

    assert db.recover_interrupted_jobs() == 2

    states = {j: db.get_generation_job(j)["status"] for j in "abcd"}
    assert states == {"a": "interrupted", "b": "interrupted", "c": "paused", "d": "completed"}
    ckpt._JOB_CONTROLS.clear()
    assert ckpt.check_job_control("a") is None  # stale pause request dropped


def test_progress_fields_and_remaining_rows(db, make_job):
    make_job(status="running", total_rows=500)
    db.update_generation_job_progress(
        job_id="job-1", generated_rows=125, current_batch=1, total_batches=4,
        progress_percent=25, stage="sample", stage_message="b1",
    )
    job = db.get_generation_job("job-1")
    assert job["generated_rows"] == 125 and job["remaining_rows"] == 375
    assert job["last_checkpoint_at"] is not None
