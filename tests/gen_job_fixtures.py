"""
Fixtures for the generation job-control tests ONLY.

They are imported explicitly by test_generation_job_control.py and
test_generation_api.py, so they never affect any other test in this folder.

Database used (first match wins):
  1. TEST_DATABASE_URL env var  -> e.g. your local Postgres. Tests run inside a
     throw-away schema (dx_test_xxxx) and never touch your real tables.
  2. the `pgserver` package     -> pip install pgserver (starts a temp Postgres)
  3. otherwise the DB tests are skipped (not failed).
"""
from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://unused:unused@localhost/unused")

import psycopg2  # noqa: E402

__all__ = ["pg_uri", "pg_schema", "db", "make_job"]

_BASE_SCHEMA = """
CREATE TABLE users (user_id SERIAL PRIMARY KEY);
CREATE TABLE datasets (dataset_id SERIAL PRIMARY KEY, user_id INTEGER);
CREATE TABLE generated_results (result_id SERIAL PRIMARY KEY);
"""


@pytest.fixture(scope="session")
def pg_uri(tmp_path_factory):
    url = os.environ.get("postgresql://postgres.becyjbyjxgwmyitfmiqo:Palak2611Grover@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres")
    if url:
        yield url
        return
    try:
        import pgserver
    except ImportError:
        pytest.skip("Set TEST_DATABASE_URL or `pip install pgserver` to run DB tests")
    server = pgserver.get_server(tmp_path_factory.mktemp("pgdata"))
    yield server.get_uri()
    server.cleanup()


@pytest.fixture(scope="session")
def pg_schema(pg_uri):
    """A private schema; search_path is limited to it so real tables are untouchable."""
    name = f"dx_test_{uuid.uuid4().hex[:8]}"
    conn = psycopg2.connect(pg_uri)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f"CREATE SCHEMA {name}")
    cur.execute(f"SET search_path TO {name}")
    cur.execute(_BASE_SCHEMA)
    conn.close()
    yield name
    conn = psycopg2.connect(pg_uri)
    conn.autocommit = True
    conn.cursor().execute(f"DROP SCHEMA {name} CASCADE")
    conn.close()


@pytest.fixture(autouse=True)
def db(pg_uri, pg_schema, monkeypatch, tmp_path):
    """Fresh generation_jobs table + 2 users + 1 dataset each, per test (in the test schema)."""
    from backend.repositories import generation_job_repository as repo
    from backend.services import generation_checkpoint_service as ckpt

    def connect():
        return psycopg2.connect(pg_uri, options=f"-c search_path={pg_schema}")

    monkeypatch.setattr(repo, "get_db_connection", connect)
    monkeypatch.setattr(repo, "_TABLE_READY", False)
    monkeypatch.chdir(tmp_path)  # checkpoints go to tmp_path/data/checkpoints
    ckpt._JOB_CONTROLS.clear()

    conn = connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f"DROP TABLE IF EXISTS {pg_schema}.generation_jobs")
    cur.execute("TRUNCATE users, datasets, generated_results RESTART IDENTITY CASCADE")
    cur.execute("INSERT INTO users DEFAULT VALUES")  # user 1
    cur.execute("INSERT INTO users DEFAULT VALUES")  # user 2
    cur.execute("INSERT INTO datasets (user_id) VALUES (1)")  # dataset 1 -> user 1
    cur.execute("INSERT INTO datasets (user_id) VALUES (2)")  # dataset 2 -> user 2
    conn.close()

    repo.ensure_generation_jobs_table()
    yield repo


@pytest.fixture
def make_job(db):
    def _make(job_id="job-1", user_id=1, dataset_id=1, status="running", total_rows=1000):
        db.create_generation_job(
            job_id=job_id, user_id=user_id, dataset_id=dataset_id,
            file_name="orders.csv", model_name="gaussian_copula",
            total_rows=total_rows, parameters={"num_rows": total_rows},
        )
        db.update_generation_job_status(job_id=job_id, status=status)
        return db.get_generation_job(job_id)

    return _make
