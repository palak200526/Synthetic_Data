# Datrixa

<div align="center">

![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/Frontend-React-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-4169E1?logo=postgresql&logoColor=white)

</div>


## Intelligent Data Transformation and Assessment Platform

Generate synthetic tabular data, evaluate data utility and privacy-related risk indicators, improve quality, and compare synthesis approaches in one workflow.

**Technology:** React · Vite · FastAPI · Python · PostgreSQL · CTGAN · TVAE · Gaussian Copula · Optional Ollama

---

## Overview

**Datrixa** is a full-stack web application for preparing, generating, and evaluating synthetic tabular data. The React frontend provides the user interface, while a FastAPI backend handles dataset operations, synthesis, evaluation, authentication, and reporting. PostgreSQL is used for application data.

Datrixa supports **CTGAN, TVAE, and Gaussian Copula** generation methods, along with local LLM-assisted column analysis and text generation through Ollama. Users can review dataset profiles, configure actions for columns, preprocess data, run generation jobs, compare quality metrics, apply quality-improvement steps, and export supported outputs. Evaluation metrics are intended to support review and comparison.

## Key Features

- **Dataset upload and management** — upload datasets and view saved datasets and their columns.
- **Dataset profiling** — inspect column types, missing values, uniqueness, sample values, and available statistical summaries.
- **Column configuration** — choose supported actions such as keep, remove, generate an ID, generalize, or derive a column.
- **LLM-assisted column analysis** — analyze column profile information through the configured local Ollama model and review supported recommendations.
- **Preprocessing** — prepare datasets for the generation workflow, including supported missing-value and data-preparation operations.
- **Synthetic data generation** — use CTGAN, TVAE, or Gaussian Copula.
- **Text generation** — use the LLM text-generation workflow for supported text columns.
- **Generation job controls** — view job status and history, and pause, resume, restart, or cancel supported jobs. Checkpoint/recovery behavior is implemented by the backend.
- **Quality evaluation** — inspect statistical similarity, feature relationships/correlation, machine-learning utility where configured, and applicable validation results.
- **Quality improvement** — apply supported enhancements and reassess the generated dataset.
- **Algorithm comparison and tuning** — inspect algorithm statistics and use the supported auto-tuning workflow.
- **Relational and multi-table workflows** — organize datasets into groups, configure relationships, and use supported multi-table generation and integrity checks.
- **Dashboard and reports** — review summary data and generate/download supported reports and datasets.
- **Authentication and account pages** — sign up, sign in, verify login OTP, view/edit supported profile information, change password, and review account activity.
- **Frontend experience** — React-based pages for upload, datasets, column analysis, preprocessing, generation, evaluation, quality improvement, comparisons, relationships, reports, profile, settings, and generation history.

Feature availability and results depend on the dataset, selected method, column configuration, model, and supporting services.

## Workflow

```text
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
Dashboard, Report, and Download
```

For related datasets, the application also provides dataset groups, relationship configuration, and a supported multi-table generation workflow.

## Architecture

```text
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
| Evaluation, Quality Improvement   |
| Relationships, Reports, Downloads|
+---------+----------------+-------+
          |                |
          v                v
+----------------+  +----------------------+
|  PostgreSQL    |  | Generation / Analysis|
| Application    |  | CTGAN, TVAE, Copula  |
| Data           |  | Ollama LLM           |
+----------------+  +----------------------+
                            |
                     Optional services
                       Redis / Celery
```

- **Frontend:** React 18, Vite, React Router, Axios, Recharts, Lucide React, and Tailwind CSS.
- **Backend:** Python and FastAPI, organized into controllers, services, repositories, schemas, generation modules, and worker tasks.
- **Database:** PostgreSQL, accessed using `psycopg2`.
- **Local LLM:** Ollama is used for LLM-assisted workflows. The backend configuration defaults to `qwen2.5:1.5b`; configure this to match the model installed locally.
- **Background processing:** Redis/Celery components are present for supported background workflows. Configure and run them when the workflow you use depends on them.

## Generation Methods

| Method | Description |
|---|---|
| **CTGAN** | A GAN-based method designed for tabular data, including mixed data types. |
| **TVAE** | A variational-autoencoder approach for learning tabular data patterns. |
| **Gaussian Copula** | A statistical approach that models feature distributions and dependencies. |
| **LLM text generation** | An optional workflow for supported text columns; separate from the three tabular synthesis methods. |

No single method is best for every dataset. Compare generated outputs using the evaluation results and the requirements of your intended use case.

## Evaluation and Quality Improvement

Datrixa contains evaluation services for multiple aspects of synthetic data quality. Depending on the selected workflow and available data, these include:

- **Statistical similarity** between real and synthetic data.
- **Correlation and feature-relationship analysis.**
- **Machine-learning utility** where a suitable target and evaluation configuration are available.
- **Data and business-rule validation** for configured rules.
- **Privacy-related indicators**, including implemented duplicate/exact-match and distance-based checks.
- **Quality enhancement and re-evaluation**, including supported feature handling, cyclical date/time encoding, categorical-frequency adjustments, correlation checks, and duplicate-related checks.

Metrics should be interpreted individually and in context. A low duplicate rate or distance-based score is not proof of anonymity, and these checks should not be described as a formal privacy guarantee unless a corresponding threat-model evaluation has actually been performed.

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React 18, Vite, React Router |
| Styling and UI | Tailwind CSS, Lucide React |
| HTTP client | Axios |
| Charts | Recharts |
| Backend API | Python, FastAPI |
| Data processing | Pandas, NumPy |
| Synthetic generation | CTGAN, TVAE, Gaussian Copula |
| ML evaluation | Scikit-learn and project evaluation services |
| Database | PostgreSQL, psycopg2 |
| LLM integration | Ollama (optional, local model) |
| Background jobs | Redis, Celery (where configured) |
| PDF reports | ReportLab |

## Project Structure

```text
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

## Getting Started

### Prerequisites

- Python 3.10 or another Python version compatible with the project's installed dependencies.
- Node.js and npm.
- A running PostgreSQL database.
- Ollama and a local model if you want to use LLM-assisted features.
- Redis and a configured Celery worker for workflows that require background processing.

> The supplied backend archive does not include a `requirements.txt`. Install the Python dependencies used by the backend in your environment, or add a pinned dependency file for reproducible setup before sharing/deploying the project.

### 1. Prepare the project

Extract the backend and frontend folders into your project directory so that `backend/` and `frontend/` are at the repository root.

Create and activate a Python virtual environment from the repository root:

**Windows PowerShell**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux / macOS**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the backend's Python dependencies into the activated environment. The backend uses FastAPI/Uvicorn, PostgreSQL via `psycopg2`, environment-variable loading, data-processing and synthesis libraries, authentication/security packages, and report-generation libraries. Use versions compatible with the code in your checkout.

### 2. Configure environment variables

The backend settings load environment variables with `python-dotenv` and require `DATABASE_URL`. Create a `.env` file in the directory from which you start the backend (normally the repository root).

Example:

```env
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

Replace the database placeholders with your actual PostgreSQL connection details. Keep credentials and secrets private; do not commit `.env` files. The backend has a development fallback for `JWT_SECRET_KEY`, but you should set a strong, unique secret.

### 3. Start the backend

From the repository root, with the virtual environment activated:

```bash
uvicorn backend.main:app --reload
```

The API is expected at `http://127.0.0.1:8000`.

Check that it is running:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"healthy"}
```

Open the interactive API documentation at `http://127.0.0.1:8000/docs` to inspect the routes and schemas registered by the current backend.

### 4. Start the frontend

Open a second terminal:

```bash
cd frontend
npm install
```

Create `frontend/.env` from `frontend/.env.example` if needed. The example setting is:

```env
VITE_API_BASE_URL=/api
```

The Vite development server is configured to run at `http://127.0.0.1:5173` and proxy `/api` requests to `http://127.0.0.1:8000`, removing the `/api` prefix before forwarding requests.

Start the frontend:

```bash
npm run dev
```

Open `http://127.0.0.1:5173` in your browser. If the terminal prints a different address, use that address.

### 5. Optional services

**Ollama**

Start Ollama and download the model configured in your backend `.env`. For the default model:

```bash
ollama pull qwen2.5:1.5b
```

If you use a different model, update `OLLAMA_MODEL` to match the model name available to Ollama.

**Redis / Celery**

Start Redis and the worker using the configuration and task entry points in your checkout when using workflows that require background processing. The exact worker command depends on how the worker is launched in your environment.

## Main API Areas

The FastAPI application registers routes for:

- System health
- Authentication and account/profile management
- Dataset upload, listing, and column access
- Dataset profiling and preprocessing
- Column configuration and LLM-assisted column analysis
- Generation, algorithm statistics, auto-tuning, quality improvement, and generation-job controls
- ID generation
- Evaluation and dashboard data
- Dataset groups and relationships
- Multi-table generation and downloads
- Validation rules
- Reports

Use `http://127.0.0.1:8000/docs` as the source of truth for exact paths, HTTP methods, request bodies, and response schemas. Routes can change as the project evolves.

## Development and Testing

### Frontend production build

```bash
cd frontend
npm run build
```

Preview the built frontend locally:

```bash
npm run preview
```

### Backend tests

Run the tests present in your checkout using the configured Python environment. For a pytest-based test suite:

```bash
python -m pytest
```

Only tests that are discovered and executed are covered by that run. Keep tests aligned with generation algorithms, preprocessing, evaluation, quality improvement, API behavior, and error handling.

## Security and Privacy

- Never commit database credentials, JWT secrets, or other private environment values.
- Set a strong `JWT_SECRET_KEY` before deployment.
- Configure CORS for the actual frontend origins in `backend/main.py` before deploying beyond local development.
- Restrict access to uploaded datasets, generated outputs, and reports.
- Use local Ollama configuration for the local LLM workflows; review the actual network behavior of any additional service you configure.
- Review generated data before sharing it. Synthetic data can still leak information about source records.
- Treat quality and privacy metrics as indicators for review, not as a guarantee of anonymity, regulatory compliance, or fitness for every use case.

**Datrixa — Generate thoughtfully. Evaluate carefully.**

## License

Datrixa's original code is proposed to be licensed under the
Apache License 2.0. See the [LICENSE](LICENSE) file for details.

Third-party libraries, models, datasets, and other assets may be
subject to separate licenses and terms. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the
third-party license inventory. This inventory is being reviewed
and should not be treated as a completed compliance statement.

**Datrixa — Generate thoughtfully. Evaluate carefully.**