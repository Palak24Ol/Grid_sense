# 🚦 GridSense: Event-Driven Congestion Intelligence System

![GridSense Banner](https://img.shields.io/badge/Status-Active-success) ![License](https://img.shields.io/badge/License-MIT-blue) ![Python](https://img.shields.io/badge/Python-3.13-yellow) ![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688) ![React](https://img.shields.io/badge/React-Frontend-61dafb)

**GridSense** is a production-grade machine learning platform built for city traffic authorities to predict, triage, and manage event-driven traffic congestion before it paralyses the city.

---

## 🛑 The Problem
Political rallies, festivals, sports events, vehicle breakdowns, and unseasonal weather create highly localized, unpredictable traffic congestion. Traffic police are often reactive—deploying manpower and diversions *after* the gridlock occurs.

## 💡 The Solution
GridSense shifts traffic management from **reactive** to **predictive**. By analyzing historical incident data (causes, vehicle types, day/time cyclicality, and corridor adjacency), the system automatically triages incoming incidents to predict priority, likelihood of road closure, and expected clearance duration.

---

## ✨ Key Features

* **🧠 AI Triage Engine:** Uses XGBoost Ensembles to instantly classify incoming traffic incidents. It calculates priority confidence, road closure probability, and predicts clearance duration in minutes.
* **🔍 SHAP Explainability:** AI shouldn't be a black box. GridSense integrates SHAP (SHapley Additive exPlanations) to provide human-readable logic for *why* a prediction was made (e.g., "+ Heavy Truck Involved", "- Non-Rush Hour").
* **🛡️ Statistical Fallback Nets:** Real-world ML isn't perfect. If the AI detects low-confidence data, it seamlessly falls back to heavily tested statistical medians (e.g., historical group-by averages) ensuring the system never crashes or returns hallucinated values.
* **🌐 Command Center Map:** A beautiful, dark-mode React dashboard allowing traffic controllers to visualize live incidents and AI predictions dynamically mapped across the city.
* **🛑 Leakage-Free Architecture:** The ML training pipeline is built with strict time-based splits (temporal validation) to ensure honest, mathematically sound accuracy metrics free from data leakage.

---

## 🧠 Honest ML on Constrained Real-World Data

Before reading the metrics, this context is important. GridSense operates on a dataset of **8,173 real incidents** collected from Bengaluru's ASTRAM system over roughly 22 weeks. Unlike toy datasets designed for ML benchmarks, this data carries all the messiness of real-world operational data: extreme class imbalance (only **8.2% of incidents cause road closures**), a large proportion of off-corridor (`Non-corridor`) incidents with sparse labels, and a hard temporal constraint that prevents any form of data leakage.

Most hackathon ML projects report 90–95%+ accuracy by using random train/test splits on time-series data — this is a form of data leakage where the model effectively "sees the future" during training. GridSense deliberately prevents this using strict **temporal splitting**: the model is trained exclusively on past data and evaluated on future data it has never seen, exactly as it would work in production.

As a result, our metrics are lower than leaky models but reflect **true predictive signal**. Outperforming even a well-tuned rule-based heuristic by any margin on a constrained, imbalanced, temporally-split dataset is a meaningful result. Where the ML model does not outperform the statistical baseline, GridSense transparently uses the better baseline in production — this is how real ML systems are built.

---

## 📊 Model Evaluation & Honest Metrics

A core philosophy of GridSense is **mathematical honesty**. Most hackathon ML projects suffer from severe data leakage (e.g., using random train/test splits on time-series data), which artificially inflates accuracy to 95%+. 

GridSense prevents this by using strict **temporal splitting** (training on past data, testing on future data) and strictly benchmarking against simple statistical heuristics. The results below represent the *true* signal in the historical traffic data:

### 1. Severity / Priority Classification Model (XGBoost)
Predicts the composite severity of an incident to assign a priority tier.
* **XGBoost F1-Score:** `0.4500`
* **Rule-based Baseline F1:** `0.4454`
* *Verdict:* The ML model successfully learned complex interactions (like cyclical time + corridor density) to outperform a hardcoded human heuristic by +1.0%.

### 2. Road Closure Risk Model (XGBoost)
Predicts the likelihood of an incident requiring full lane closures.
* **XGBoost F1-Score:** `0.3909`
* **Rule-based Baseline F1:** `0.3983`
* *Verdict:* Performs comparably to human heuristics. The extreme class imbalance (only 8.2% of incidents cause closures) required heavy `scale_pos_weight` tuning.

### 3. Clearance Duration Model (XGBoost Regressor)
Predicts the exact minutes required to resolve an incident.
* **XGBoost Median Absolute Error (MedAE):** `45.2 minutes`
* **Statistical Lookup Baseline MedAE:** `38.4 minutes`
* *Verdict:* The basic "group-by-median" fallback actually outperforms the XGBoost regression due to high variance in real-world clearance times. GridSense automatically detects this and utilizes the statistical lookup table as a primary safety net.

### 4. Hourly Corridor Forecasting (Prophet)
Predicts traffic volume across major junctions.
* **Prophet Mean Absolute Error (MAE):** `0.182`
* **Naive Hourly Mean MAE:** `0.175`
* *Verdict:* Prophet struggles to beat a naive historical average on this specific dataset, proving the need for live traffic integrations in V2.

---

## 🏗️ System Architecture

GridSense is built using a modern, decoupled stack:

### 1. The Machine Learning Pipeline (`/ml`)
* **Data Processing:** `pandas`, `numpy` (includes automatic event deduplication).
* **Feature Engineering:** Cyclical time encodings (`sin`/`cos`), rolling geographical incident counts, and composite severity targeting.
* **Models:** `XGBoost` (Classification & Regression), `Prophet` (Corridor Forecasting).
* **Explainability:** `SHAP` tree-explainers.

### 2. The Backend (`/backend`)
* **Framework:** `FastAPI` (Asynchronous API).
* **Database:** `PostgreSQL` via `SQLAlchemy`.
* **Model Serving:** In-memory `.pkl` loading via an abstract Artifact Loader module.

### 3. The Frontend (`/frontend`)
* **Framework:** `React` (Vite).
* **Styling:** `Tailwind CSS`.
* **Mapping:** Leaflet/Mapbox integrations.

---

## 🚀 How to Run Locally

### Prerequisites
* Python 3.10+
* Node.js & npm
* PostgreSQL (Running on port 5433)

### 1. Install Backend Dependencies
Navigate to the root directory and install the Python requirements:
```powershell
py -m pip install -r requirements.txt
```

### 2. Database Setup & Seeding
Set up your environment variables and run the migrations to create the database schema, then seed it:
```powershell
cp .env.example .env
alembic upgrade head
py scripts/seed_db.py
```

### 3. Start the FastAPI Backend
Start the backend server on `localhost:8000`:
```powershell
py -m uvicorn backend.main:app --reload --port 8000
```

### 4. Start the React Frontend
Open a **second terminal**, navigate to the frontend folder, and start the Vite dev server:
```powershell
cd frontend
$env:VITE_USE_MOCK="false"  # Windows
# export VITE_USE_MOCK="false" # Mac/Linux
npm run dev
```
Navigate to `http://localhost:5173` in your browser.

---

## 🧪 Running the ML Pipeline

To completely retrain the AI models from scratch using the raw data, run the pipeline scripts in sequential order:

```powershell
py ml/pipeline/01_ingest.py
py ml/pipeline/02_feature_engineer.py
py ml/pipeline/03_train_closure.py
py ml/pipeline/04_train_priority.py
py ml/pipeline/05_train_duration.py
py ml/pipeline/06_train_forecast.py
py ml/pipeline/07_export_artifacts.py
```
*(Tests can be run via `py test_predict.py` to verify API endpoint responses).*

---

## 🔮 Future Scope
While the current architecture is fully operational on historical datasets, the immediate next steps for production deployment include:
1. **Live Traffic APIs:** Integrating the Google Maps or TomTom Traffic API to feed real-time velocity data into the XGBoost models.
2. **Weather Multipliers:** Connecting the OpenWeatherMap API to dynamically alter severity/duration predictions based on sudden rainfall or storms.
