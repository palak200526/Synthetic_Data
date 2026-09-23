CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100),
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dataset_groups (
    group_id SERIAL PRIMARY KEY,
    group_name VARCHAR(255) NOT NULL,
    domain_type VARCHAR(100),
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
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
    group_id INTEGER REFERENCES dataset_groups(group_id) ON DELETE SET NULL,
    dataset_name VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(20),
    domain_type VARCHAR(100),
    row_count INTEGER,
    column_count INTEGER,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dataset_relationships (
    relationship_id SERIAL PRIMARY KEY,

    group_id INTEGER NOT NULL
        REFERENCES dataset_groups(group_id)
        ON DELETE CASCADE,

    parent_dataset_id INTEGER NOT NULL
        REFERENCES datasets(dataset_id)
        ON DELETE CASCADE,

    parent_column VARCHAR(255) NOT NULL,

    child_dataset_id INTEGER NOT NULL
        REFERENCES datasets(dataset_id)
        ON DELETE CASCADE,

    child_column VARCHAR(255) NOT NULL,

    relationship_type VARCHAR(50) DEFAULT 'foreign_key',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dataset_profiles (
    profile_id SERIAL PRIMARY KEY,
    dataset_id INTEGER NOT NULL REFERENCES datasets(dataset_id) ON DELETE CASCADE,
    profile_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE domain_column_presets (
    preset_id SERIAL PRIMARY KEY,
    domain_type VARCHAR(100) NOT NULL,
    column_pattern VARCHAR(100) NOT NULL,
    suggested_type VARCHAR(50),
    is_sensitive BOOLEAN DEFAULT FALSE,
    is_identifier BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO domain_column_presets
    (domain_type, column_pattern, suggested_type, is_sensitive, is_identifier)
VALUES
    ('supply_chain', 'supplier_id', 'identifier', FALSE, TRUE),
    ('supply_chain', 'supplier_name', 'string', FALSE, FALSE),
    ('supply_chain', 'product_id', 'identifier', FALSE, TRUE),
    ('supply_chain', 'raw_material_id', 'identifier', FALSE, TRUE),
    ('supply_chain', 'po_id', 'identifier', FALSE, TRUE),
    ('supply_chain', 'order_id', 'identifier', FALSE, TRUE),
    ('supply_chain', 'unit_price', 'numeric', FALSE, FALSE),
    ('supply_chain', 'unit_cost', 'numeric', FALSE, FALSE),
    ('supply_chain', 'order_quantity', 'numeric', FALSE, FALSE),
    ('supply_chain', 'quantity', 'numeric', FALSE, FALSE),
    ('supply_chain', 'order_date', 'date', FALSE, FALSE),
    ('supply_chain', 'delivery_date', 'date', FALSE, FALSE),
    ('supply_chain', 'delivery_date_planned', 'date', FALSE, FALSE),
    ('supply_chain', 'delivery_date_actual', 'date', FALSE, FALSE),
    ('supply_chain', 'country', 'categorical', FALSE, FALSE),
    ('supply_chain', 'city', 'categorical', FALSE, FALSE),
    ('supply_chain', 'category', 'categorical', FALSE, FALSE),
    ('supply_chain', 'status', 'categorical', FALSE, FALSE);

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



