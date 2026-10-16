import psycopg2
import pytest

_BASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (user_id SERIAL PRIMARY KEY);
CREATE TABLE IF NOT EXISTS datasets (dataset_id SERIAL PRIMARY KEY, user_id INTEGER);
CREATE TABLE IF NOT EXISTS generated_results (result_id SERIAL PRIMARY KEY);
"""

TEST_SCHEMA = "pytest_tmp_schema"


@pytest.fixture(scope="session")
def pg_uri(tmp_path_factory):
    import os

    uri = os.environ.get("postgresql://postgres.becyjbyjxgwmyitfmiqo:Palak2611Grover@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres")
    server = None
    real_connect = psycopg2.connect

    if uri:
        # Isolated schema: tests asli public tables ko kabhi nahi chhuenge
        conn = real_connect(uri)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")
        cur.execute(f"CREATE SCHEMA {TEST_SCHEMA}")
        cur.close()
        conn.close()

        def scoped_connect(*args, **kwargs):
            c = real_connect(*args, **kwargs)
            cur = c.cursor()
            cur.execute(f"SET search_path TO {TEST_SCHEMA}")
            cur.execute("SELECT current_schema()")
            # Safety: agar schema set nahi hua to test rok do
            assert cur.fetchone()[0] == TEST_SCHEMA
            cur.close()
            c.commit()
            return c

        psycopg2.connect = scoped_connect
    else:
        import pgserver

        server = pgserver.get_server(tmp_path_factory.mktemp("pgdata"))
        uri = server.get_uri()

    conn = psycopg2.connect(uri)
    conn.autocommit = True
    conn.cursor().execute(_BASE_SCHEMA)
    conn.close()

    yield uri

    if server is not None:
        server.cleanup()
    else:
        psycopg2.connect = real_connect
        conn = real_connect(uri)
        conn.autocommit = True
        conn.cursor().execute(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")
        conn.close()