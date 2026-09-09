# Privacy Aware Data Synthesis
## Overview

The **Privacy Aware Data Synthesis Platform** is a web-based platform designed to generate synthetic tabular data from real-world datasets while evaluating the **utility and privacy risks** of the generated data.

The platform allows users to upload real-world tabular datasets, profile and preprocess the data, generate synthetic datasets using multiple generation approaches, evaluate the generated data, compare the results, and identify the best-performing synthetic dataset based on the **utility–privacy trade-off**.

---

## Problem Statement

Real-world datasets may contain personal or sensitive information. Sharing such datasets with developers, data scientists, testing teams, or researchers can create privacy and security risks.

The platform aims to generate synthetic data that preserves important statistical characteristics and relationships of the original dataset without directly exposing the original records.

---

## Objectives

* Upload real-world tabular datasets
* Profile and understand the uploaded dataset
* Preprocess the dataset before generation
* Generate synthetic data using multiple approaches
* Preserve important statistical characteristics and feature relationships
* Evaluate the utility of generated synthetic data
* Evaluate privacy and related risks
* Compare different synthetic data generation approaches
* Calculate an overall risk–utility score
* Recommend the best-performing generated dataset
* Provide dashboards and evaluation results
* Generate downloadable reports and synthetic datasets

---


## Project Workflow

```text 
 Upload Dataset
      ↓
 Data Profiling
      ↓
 Data Preprocessing
      ↓
 Select / Run Generation Models
      ↓
 Synthetic Data Generation
      ↓
 Utility Evaluation
      ↓
 Privacy / Risk Evaluation
      ↓
 Comparison & Scoring
      ↓
 Best Model Recommendation
      ↓
 Dashboard & Report
      ↓
 Download Synthetic Data
```

---

## Synthetic Data Generation

The platform is designed to compare multiple synthetic data generation approaches:

* **CTGAN**
* **TVAE**
* **Gaussian Copula**

Each approach generates a synthetic dataset that is evaluated against the original dataset.

The results are then compared to identify the approach that provides a better balance between **data utility, privacy, risk, and performance**.

---

## Data Profiling and Preprocessing

The platform will analyze the uploaded dataset for:

* Number of rows and columns
* Data types
* Numerical columns
* Categorical columns
* Missing values
* Basic statistics
* Potential identifiers
* Potential sensitive columns
* Outliers
* Feature relationships

Preprocessing will prepare the dataset for synthetic data generation and subsequent evaluation.

---

## Utility Evaluation

The generated synthetic data will be evaluated at multiple levels.

### Statistical Similarity

The system will compare characteristics such as:

* Mean
* Median
* Standard deviation
* Min / Max
* Quantiles
* Distributions
* Category frequencies
* Category proportions

### Relationship Similarity

The system will evaluate:

* Correlation similarity
* Covariance similarity
* Feature relationships
* Distribution similarity

### Machine Learning Utility

The platform will evaluate whether synthetic data retains patterns that are useful for machine-learning tasks.

Depending on the use case, evaluation metrics may include:

* Accuracy
* Precision
* Recall
* F1-score
* ROC-AUC

---

## Privacy and Risk Evaluation

The platform will evaluate privacy-related risks in the generated synthetic data.

The evaluation may include:

* Exact duplicate detection
* Near-duplicate detection
* Record similarity
* Membership inference risk
* Attribute disclosure risk

The objective is to identify whether synthetic records are too similar to the original data or whether sensitive information could potentially be inferred.

---

## Risk–Utility Scoring

The results from utility and privacy evaluation will be combined to calculate an overall **risk–utility score**.

The scoring engine will compare the results of different generation approaches and support selection of the recommended model for the given dataset.

The scoring process will consider:

* Utility performance
* Privacy risk
* Statistical similarity
* Relationship similarity
* Machine-learning utility
* Overall generation performance

The final score will be used to rank the available generation approaches and recommend the most suitable approach for the dataset.

---

## Dashboard and Reporting

The platform will provide a dashboard containing:

* Dataset information
* Generation results
* Statistical comparisons
* Distribution comparisons
* Correlation comparisons
* Machine-learning performance
* Utility score
* Privacy score
* Privacy-risk indicators
* Model comparison
* Overall risk–utility score
* Recommended model

A final report will contain the:

* Dataset summary
* Preprocessing information
* Generation details
* Evaluation results
* Utility analysis
* Privacy and risk analysis
* Model comparison
* Risk–utility scores
* Recommended model

The platform will also allow users to download:

* Generated synthetic datasets
* Evaluation results
* Final reports

---

## Technology Stack

### Frontend

* **Streamlit**

### Backend

* **Python**
* **FastAPI**

### Background Processing

* **Celery**
* **Redis**

### Database

* **PostgreSQL**

### Data Processing and Machine Learning

* **Pandas**
* **NumPy**
* **Scikit-learn**

### Visualization

* **Plotly**

### Reporting

* **ReportLab**

---
