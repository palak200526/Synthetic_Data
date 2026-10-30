# Datrixa


![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/Frontend-React-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-4169E1?logo=postgresql&logoColor=white)

## Intelligent Data Transformation and Assessment Platform

Generate realistic synthetic tabular data, evaluate data utility and
privacy-related risk indicators, improve quality, and compare synthesis
approaches in one workflow.

**Live application:** <http://15.206.127.155/>

**Technology:** React · Vite · FastAPI · Python · PostgreSQL · CTGAN ·
TVAE · Gaussian Copula · Optional Ollama

------------------------------------------------------------------------

## Overview

**Datrixa** is a full-stack web application for preparing, generating,
and evaluating synthetic tabular data. The React frontend provides the
user interface, while a FastAPI backend handles dataset operations,
synthesis, evaluation, authentication, and reporting. PostgreSQL is used
for application data.

Datrixa supports **CTGAN, TVAE, and Gaussian Copula** generation
methods, along with local LLM-assisted column analysis and text
generation through Ollama. Users can review dataset profiles, configure
actions for columns, preprocess data, run generation jobs, compare
quality metrics, apply quality-improvement steps, and export supported
outputs. Evaluation metrics are intended to support review and
comparison.

## Key Features

-   **Dataset upload and management** --- upload datasets and view saved
    datasets and their columns.
-   **Dataset profiling** --- inspect column types, missing values,
    uniqueness, sample values, and available statistical summaries.
-   **Column configuration** --- choose supported actions such as keep,
    remove, generate an ID, generalize, or derive a column.
-   **LLM-assisted column analysis** --- analyze column profile
    information through the configured local Ollama model and review
    supported recommendations.
-   **Preprocessing** --- prepare datasets for the generation workflow,
    including supported missing-value and data-preparation operations.
-   **Synthetic data generation** --- use CTGAN, TVAE, or Gaussian
    Copula.
-   **Text generation** --- use the LLM text-generation workflow for
    supported text columns.
-   **Generation job controls** --- view job status and history, and
    pause, resume, restart, or cancel supported jobs.
    Checkpoint/recovery behavior is implemented by the backend.
-   **Quality evaluation** --- inspect statistical similarity, feature
    relationships/correlation, machine-learning utility where
    configured, privacy-related indicators, and applicable validation
    results.
-   **Quality improvement** --- apply supported enhancements and
    reassess the generated dataset.
-   **Feedback loop** --- submit feedback on quality-improvement
    outcomes; feedback is stored with the related user, dataset, and
    generation-result references.
-   **Before-and-after comparison** --- review metric changes after
    quality improvement, including improved, regressed, and unchanged
    results.
-   **Algorithm comparison and tuning** --- inspect algorithm statistics
    and use the supported auto-tuning workflow.
-   **Relational and multi-table workflows** --- organize datasets into
    groups, configure relationships, and use supported multi-table
    generation and integrity checks.
-   **Dashboard and reports** --- review summary data and
    generate/download supported reports and datasets.
-   **Authentication and account pages** --- sign up, sign in, verify
    login OTP, view/edit supported profile information, change password,
    and review account activity.
-   **Frontend experience** --- React-based pages for upload, datasets,
    column analysis, preprocessing, generation, evaluation, quality
    improvement, comparisons, relationships, reports, profile, settings,
    and generation history.

Feature availability and results depend on the dataset, selected method,
column configuration, model, and supporting services.

## Workflow

``` text
Sign in
  |
  v
Upload and Profile Dataset
  |
  v
Analyze Columns and Configure Actions
  |
  v
Preprocess Dataset
  |
  v
Generate Synthetic Data
  |  CTGAN | TVAE | Gaussian Copula
  |  LLM text generation
  v
Evaluate Utility, Relationships, and Privacy Indicators
  |
  v
Improve Quality and Re-evaluate
  |
  v
Compare Results
  |
  v
Submit Feedback on Improvement
  |
  v
Dashboard, Report, and Download
```

For related datasets, the application also provides dataset groups,
relationship configuration, and a supported multi-table generation
workflow.

## Architecture

``` text
+----------------------------------+
|          React Frontend          |
| React Router | Axios | Recharts  |
+----------------+-----------------+
                 |
              HTTP / API
                 |
+----------------v-----------------+
|          FastAPI Backend         |
| Authentication and Account       |
| Upload, Profiling, Preprocessing  |
| Column Configuration and LLM     |
| Generation, Jobs, and Checkpoints |
| Evaluation, Quality Improvement  |
| Feedback, Relationships, Reports |
+---------+----------------+-------+
          |                |
          v                v
+----------------+  +----------------------+
|  PostgreSQL    |  | Generation / Analysis|
| Application    |  | CTGAN, TVAE, Copula  |
| Data + Feedback|  | Ollama LLM           |
+----------------+  +----------------------+
                            |
                     Optional services
                       Redis / Celery
```

-   **Frontend:** React 18, Vite, React Router, Axios, Recharts, Lucide
    React, and Tailwind CSS.
-   **Backend:** Python and FastAPI, organized into controllers,
    services, repositories, schemas, generation modules, and worker
    tasks.
-   **Database:** PostgreSQL, accessed using `psycopg2`.
-   **Local LLM:** Ollama is used for LLM-assisted workflows. The
    backend configuration defaults to `qwen2.5:1.5b`; configure this to
    match the model installed locally.
-   **Background processing:** Redis/Celery components are present for
    supported background workflows. Configure and run them when the
    workflow you use depends on them.

## Generation Methods

  -----------------------------------------------------------------------
  Method                              Description
  ----------------------------------- -----------------------------------
  **CTGAN**                           A GAN-based method designed for
                                      tabular data, including mixed data
                                      types.

  **TVAE**                            A variational-autoencoder approach
                                      for learning tabular data patterns.

  **Gaussian Copula**                 A statistical approach that models
                                      feature distributions and
                                      dependencies.

  **LLM text generation**             An optional workflow for supported
                                      text columns; separate from the
                                      three tabular synthesis methods.
  -----------------------------------------------------------------------

No single method is best for every dataset. Compare generated outputs
using the evaluation results and the requirements of your intended use
case.

## Evaluation and Quality Improvement

Datrixa contains evaluation services for multiple aspects of synthetic
data quality. Depending on the selected workflow and available data,
these include:

-   **Statistical similarity** between real and synthetic data.
-   **Correlation and feature-relationship analysis.**
-   **Machine-learning utility** where a suitable target and evaluation
    configuration are available.
-   **Data and business-rule validation** for configured rules.
-   **Privacy-related indicators**, including implemented
    duplicate/exact-match and distance-based checks.
-   **Quality enhancement and re-evaluation**, including supported
    feature handling, cyclical date/time encoding, categorical-frequency
    adjustments, correlation checks, and duplicate-related checks.

Metrics should be interpreted individually and in context. A low
duplicate rate or distance-based score is not proof of anonymity, and
these checks should not be described as a formal privacy guarantee
unless a corresponding threat-model evaluation has actually been
performed.

## Feedback Loop and Continuous Quality Improvement

Datrixa includes a feedback step for users to rate the outcome of the
**Improve Quality** workflow. The feedback loop makes the improvement
process more transparent and captures the user's assessment of whether
the changes were useful.

The current workflow is:

1.  Generate synthetic data and evaluate its quality.
2.  Identify metrics or quality areas that may need attention.
3.  Run the Improve Quality workflow.
4.  Evaluate the improved result again.
5.  Compare the before-and-after metrics and identify improvements,
    regressions, or unchanged values.
6.  Display the comparison so users can review the effect of the
    improvement.
7.  Allow the user to submit feedback, such as **Helpful**, **Partially
    Helpful**, or **Not Helpful**, with an optional focus area/comment
    where available.
8.  Store the feedback in PostgreSQL with references to the user,
    dataset, original result, and improved result.

This provides a record of user feedback linked to the relevant
quality-improvement run. **Automatic learning from historical feedback
to change future generation strategies is not claimed as part of the
current implementation**; it can be considered as a future enhancement.

## Technology Stack

  Layer                  Technologies
  ---------------------- ----------------------------------------------
  Frontend               React 18, Vite, React Router
  Styling and UI         Tailwind CSS, Lucide React
  HTTP client            Axios
  Charts                 Recharts
  Backend API            Python, FastAPI
  Data processing        Pandas, NumPy
  Synthetic generation   CTGAN, TVAE, Gaussian Copula
  ML evaluation          Scikit-learn and project evaluation services
  Database               PostgreSQL, psycopg2
  LLM integration        Ollama (optional, local model)
  Background jobs        Redis, Celery (where configured)
  PDF reports            ReportLab

## Project Structure

``` text
.
├── backend/
│   ├── config/          # Database and environment settings
│   ├── controllers/     # FastAPI route handlers
│   ├── generation/      # CTGAN, TVAE, Gaussian Copula, LLM text generation
│   ├── models/          # Data models
│   ├── repositories/    # Database access
│   ├── schemas/         # Request and response schemas
│   ├── services/        # Profiling, preprocessing, generation, evaluation, etc.
│   ├── utils/           # Shared helpers and security utilities
│   ├── worker/          # Background task and Celery modules
│   └── main.py          # FastAPI application entry point
├── database/
│   └── schema.sql       # PostgreSQL database schema
└── frontend/
    ├── src/
    │   ├── api/         # API client modules
    │   ├── components/  # Shared UI and evaluation components
    │   ├── context/     # Authentication and generation tracking state
    │   ├── layouts/     # App and authentication layouts
    │   ├── pages/       # Application pages
    │   ├── routes/      # Route configuration and route protection
    │   └── utils/       # Frontend helpers
    ├── .env.example
    ├── package.json
    └── vite.config.js
```

Adjust this tree to match the directories and files present in the
repository you publish.

## Getting Started

### Prerequisites

-   Python 3.10 or another Python version compatible with the project's
    installed dependencies.
-   Node.js and npm.
-   A running PostgreSQL database.
-   Ollama and a local model if you want to use LLM-assisted features.
-   Redis and a configured Celery worker for workflows that require
    background processing.

> The supplied backend archive did not include a `requirements.txt`.
> Install the Python dependencies used by the backend in your
> environment, or add a pinned dependency file for reproducible setup
> before sharing/deploying the project.

### 1. Prepare the project

Extract the backend and frontend folders into your project directory so
that `backend/` and `frontend/` are at the repository root.

Create and activate a Python virtual environment from the repository
root:

**Windows PowerShell**

``` powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux / macOS**

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the backend's Python dependencies into the activated
environment. The backend uses FastAPI/Uvicorn, PostgreSQL via
`psycopg2`, environment-variable loading, data-processing and synthesis
libraries, authentication/security packages, and report-generation
libraries. Use versions compatible with the code in your checkout.

### 2. Configure the database

Create or select a PostgreSQL database. Review `database/schema.sql` and
execute the schema against that database using your PostgreSQL client or
database provider's SQL editor.

Set `DATABASE_URL` to the connection string for that database. Keep
database credentials private and do not commit them to the repository.

### 3. Configure environment variables

The backend settings load environment variables with `python-dotenv` and
require `DATABASE_URL`. Create a `.env` file in the directory from which
you start the backend (normally the repository root).

Example:

``` env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
JWT_SECRET_KEY=replace-with-a-long-random-secret
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Optional local LLM configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b
LLM_TEXT_BATCH_SIZE=20
LLM_TEXT_TIMEOUT=300
LLM_TEXT_MAX_RETRIES=3
LLM_TEXT_SIMILARITY_THRESHOLD=0.92

# Optional background processing
REDIS_BROKER_URL=redis://localhost:6379/0

# Optional: only set if a code path in your environment uses it
OPENAI_API_KEY=
```

Replace the database placeholders with your actual PostgreSQL connection
details. Keep credentials and secrets private; do not commit `.env`
files. The backend has a development fallback for `JWT_SECRET_KEY`, but
you should set a strong, unique secret.

### 4. Start the backend

From the repository root, with the virtual environment activated:

``` bash
uvicorn backend.main:app --reload
```

The API is expected at `http://127.0.0.1:8000`.

Check that it is running:

``` bash
curl http://127.0.0.1:8000/health
```

Expected response:

``` json
{"status":"healthy"}
```

Open the interactive API documentation at `http://127.0.0.1:8000/docs`
to inspect the routes and schemas registered by the current backend.

### 5. Start the frontend

Open a second terminal:

``` bash
cd frontend
npm install
```

Create `frontend/.env` from `frontend/.env.example` if needed. The
example setting is:

``` env
VITE_API_BASE_URL=/api
```

The Vite development server is configured to run at
`http://127.0.0.1:5173` and proxy `/api` requests to
`http://127.0.0.1:8000`, removing the `/api` prefix before forwarding
requests.

Start the frontend:

``` bash
npm run dev
```

Open `http://127.0.0.1:5173` in your browser. If the terminal prints a
different address, use that address.

### 6. Optional services

**Ollama**

Start Ollama and download the model configured in your backend `.env`.
For the default model:

``` bash
ollama pull qwen2.5:1.5b
```

If you use a different model, update `OLLAMA_MODEL` to match the model
name available to Ollama.

**Redis / Celery**

Start Redis and the worker using the configuration and task entry points
in your checkout when using workflows that require background
processing. The exact worker command depends on how the worker is
launched in your environment.

## Deployment on AWS

**Live application:** <http://15.206.127.155/>

Datrixa is deployed on **Amazon EC2** and is accessible through the
instance's public IP address. **Amazon S3** was used to store the
compressed project package and transfer it for deployment; S3 is not
described here as the host serving the live application.

The deployment workflow used was:

1.  Package the project into a ZIP archive.
2.  Upload the ZIP archive to an Amazon S3 bucket.
3.  Configure an Amazon EC2 instance for the application.
4.  Retrieve the project archive from S3 onto the EC2 instance.
5.  Configure the application environment and required dependencies on
    the instance.
6.  Start the backend and frontend application services.
7.  Access the deployed application through the EC2 public IP address.

**Deployment notes:**

-   The application URL currently uses HTTP and an EC2 public IP
    address.
-   A public IP can change if it is not reserved. An Elastic IP and a
    domain name can be configured for a more stable address.
-   Configure HTTPS, production CORS settings, secure environment
    variables, and appropriate network/security-group rules before using
    the deployment for broader production access.
-   Do not include `.env` files, database passwords, JWT secrets, or API
    keys in the ZIP archive or public repository.

## Main API Areas

The FastAPI application registers routes for:

-   System health
-   Authentication and account/profile management
-   Dataset upload, listing, and column access
-   Dataset profiling and preprocessing
-   Column configuration and LLM-assisted column analysis
-   Generation, algorithm statistics, auto-tuning, quality improvement,
    and generation-job controls
-   ID generation
-   Evaluation and dashboard data
-   Dataset groups and relationships
-   Multi-table generation and downloads
-   Validation rules
-   Reports
-   Quality-improvement feedback

Use `http://127.0.0.1:8000/docs` as the source of truth for exact paths,
HTTP methods, request bodies, and response schemas. Routes can change as
the project evolves.

## Development and Testing

### Frontend production build

``` bash
cd frontend
npm run build
```

Preview the built frontend locally:

``` bash
npm run preview
```

### Backend tests

Run the tests present in your checkout using the configured Python
environment. For a pytest-based test suite:

``` bash
python -m pytest
```

Only tests that are discovered and executed are covered by that run.
Keep tests aligned with generation algorithms, preprocessing,
evaluation, quality improvement, API behavior, feedback persistence, and
error handling.

## Security and Privacy

-   Never commit database credentials, JWT secrets, or other private
    environment values.
-   Set a strong `JWT_SECRET_KEY` before deployment.
-   Configure CORS for the actual frontend origins in `backend/main.py`
    before deploying beyond local development.
-   Restrict access to uploaded datasets, generated outputs, and
    reports.
-   Use local Ollama configuration for the local LLM workflows; review
    the actual network behavior of any additional service you configure.
-   Review generated data before sharing it. Synthetic data can still
    leak information about source records.
-   Treat quality and privacy metrics as indicators for review, not as a
    guarantee of anonymity, regulatory compliance, or fitness for every
    use case.

**Datrixa --- Generate thoughtfully. Evaluate carefully.**

## License

Datrixa's original code is proposed to be licensed under the Apache
License 2.0. See the [LICENSE](LICENSE) file for details.

Third-party libraries, models, datasets, and other assets may be subject
to separate licenses and terms. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the third-party
license inventory. This inventory is being reviewed and should not be
treated as a completed compliance statement.
