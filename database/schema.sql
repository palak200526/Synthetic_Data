CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100),
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE processing_sessions (
    session_id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

CREATE TABLE datasets (
    dataset_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id),
    session_id BIGINT REFERENCES processing_sessions(session_id),
    dataset_name VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(20),
    row_count INTEGER,
    column_count INTEGER,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dataset_profiles (
    profile_id SERIAL PRIMARY KEY,
    dataset_id INTEGER NOT NULL REFERENCES datasets(dataset_id) ON DELETE CASCADE,
    profile_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE column_configurations (
    configuration_id SERIAL PRIMARY KEY,
    dataset_id INTEGER NOT NULL REFERENCES datasets(dataset_id) ON DELETE CASCADE,
    column_name VARCHAR(255) NOT NULL,
    column_type VARCHAR(50),
    is_sensitive BOOLEAN DEFAULT FALSE,
    is_identifier BOOLEAN DEFAULT FALSE,
    action VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (dataset_id, column_name)
);

CREATE TABLE generation_runs (
    run_id SERIAL PRIMARY KEY,
    dataset_id INTEGER NOT NULL REFERENCES datasets(dataset_id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE model_configurations (
    configuration_id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES generation_runs(run_id) ON DELETE CASCADE,
    model_name VARCHAR(100) NOT NULL,
    parameters JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE generated_results (
    result_id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES generation_runs(run_id) ON DELETE CASCADE,
    file_name VARCHAR(255),
    file_path TEXT,
    row_count INTEGER,
    column_count INTEGER,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE evaluation_results (
    evaluation_id SERIAL PRIMARY KEY,
    result_id INTEGER NOT NULL REFERENCES generated_results(result_id) ON DELETE CASCADE,
    utility_metrics JSONB,
    privacy_metrics JSONB,
    overall_score DECIMAL(5,2),
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE reports (
    report_id SERIAL PRIMARY KEY,
    result_id INTEGER NOT NULL REFERENCES generated_results(result_id) ON DELETE CASCADE,
    report_name VARCHAR(255),
    report_path TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

