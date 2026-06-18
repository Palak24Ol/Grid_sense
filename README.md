# 🚦 GridSense

![GridSense Banner](https://img.shields.io/badge/GridSense-Traffic%20Intelligence-0f172a?style=for-the-badge&logo=react)
![Python FastAPI](https://img.shields.io/badge/Backend-FastAPI_&_Python-009688?style=for-the-badge&logo=fastapi)
![Machine Learning](https://img.shields.io/badge/ML-XGBoost_&_Prophet-f59e0b?style=for-the-badge&logo=scikit-learn)

GridSense is an AI-powered traffic intelligence and incident management platform designed for the city of Bengaluru. By leveraging historical incident data, machine learning classification, and time-series forecasting, GridSense enables proactive resource deployment, automated incident triage, and optimized logistics routing.

---

## ✨ Core Features

1. **🚨 Triage & Predict:** Real-time ML classification of incoming traffic incidents. Automatically predicts if an incident is **High Priority** (needs immediate dispatch) and whether it will require a physical **Road Closure**.
2. **📈 72-Hour Corridor Forecast:** Dynamic time-series forecasting predicting hourly incident volumes across 12 major city corridors, allowing authorities to anticipate morning and evening surge windows.
3. **📍 Blackspots Analysis:** Historical heatmapping and risk-scoring of the city's most dangerous junctions and corridors based on incident density.
4. **🚓 Automated Deployment:** Intelligent allocation of emergency responders and traffic police to critical corridors based on predicted 24-hour risk scores.
5. **🚚 LCV Logistics:** Route optimization and dispatch window recommendations for Light Commercial Vehicles to avoid predicted peak incident hours.

---

## 🧠 Machine Learning Architecture

GridSense utilizes a multi-model ML pipeline to power its predictive capabilities:

*   **Incident Priority Classifier (XGBoost)**
    *   **Task:** Multi-class prediction of incident priority to optimize emergency responder dispatch.
    *   **Performance:** 92% Accuracy, 0.95 ROC-AUC, 0.93 F1-Score.
*   **Road Closure Prediction (XGBoost)**
    *   **Task:** Binary classification to predict if an incident will escalate to require a road closure (a severe 8.3% minority class).
    *   **Performance:** 94% Accuracy, 0.93 ROC-AUC, 0.69 F1-Score.
*   **Traffic Forecasting Models (Facebook Prophet)**
    *   **Task:** 12 independent Additive Seasonality models predicting 72-hour incident volumes for major corridors.
    *   **Performance:** Averages ~0.18 MAE, effectively isolating strong daily and weekly patterns to detect distinct morning/evening peaks.

---

## 🛠️ Tech Stack

*   **Frontend:** React (Vite), TailwindCSS, Lucide Icons
*   **Backend:** Python, FastAPI, Uvicorn
*   **Machine Learning:** XGBoost, Facebook Prophet, Pandas, Scikit-Learn
*   **Mapping:** Leaflet (React-Leaflet)

---

## 📂 Repository Structure

```text
GridSense/
├── backend/                  # FastAPI Application
│   ├── api/routes/           # API Endpoints (Forecast, Triage, Blackspots)
│   ├── services/             # Core business logic and ML model loading
│   └── schemas/              # Pydantic data validation models
├── frontend/                 # React Vite Application
│   ├── src/components/       # UI Components (ForecastScreen, TriageScreen, etc.)
│   └── public/               # Static assets
├── ml/                       # Machine Learning Pipeline
│   ├── pipeline/             # Numbered Python scripts (01 to 06) for training
│   └── artifacts/            # Output directory for encoders and .pkl models
└── data/                     # Raw and Processed dataset directory
```

---

## 🚀 Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/GridSense.git
cd GridSense
```

### 2. Machine Learning & Backend Setup (Python)
Ensure you have Python 3.10+ installed.

```bash
# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate  # On Windows

# Install dependencies
pip install fastapi uvicorn pandas scikit-learn xgboost prophet

# (Optional) Retrain the ML Models
python ml/pipeline/01_ingest.py
python ml/pipeline/02_feature_engineering.py
python ml/pipeline/03_train_priority.py
python ml/pipeline/04_train_closure.py
python ml/pipeline/05_score_blackspots.py
python ml/pipeline/06_train_forecast.py

# Start the FastAPI Server
uvicorn backend.main:app --reload --port 8000
```

### 3. Frontend Setup (Node.js)
Ensure you have Node.js installed. Open a **new terminal window**.

```bash
cd frontend
npm install
npm run dev
```

The application will now be running at `http://localhost:5173`.

---

## 👨‍💻 Authors & Acknowledgments

Built for optimized urban traffic management and intelligent predictive logistics.
