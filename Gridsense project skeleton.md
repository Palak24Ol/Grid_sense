# GridSense — Project Skeleton & Build Reference

> Version: 1.0 — BUILD MODE  
> Architecture: FROZEN  
> Purpose: Development scaffold for 4-member team  
> Companion to: GridSense_Implementation_Plan.md + GridSense_Implementation_Readiness_Review.md

---

## Table of Contents

1. [Repository Root Tree](#1-repository-root-tree)
2. [Backend Tree](#2-backend-tree)
3. [Frontend Tree](#3-frontend-tree)
4. [Database Structure](#4-database-structure)
5. [ML Structure](#5-ml-structure)
6. [API File Mapping](#6-api-file-mapping)
7. [Zustand Store Mapping](#7-zustand-store-mapping)
8. [Component Ownership Matrix](#8-component-ownership-matrix)
9. [Development Order](#9-development-order)

---

## 1. Repository Root Tree

```
gridsense/
├── README.md
├── .env.example                        # Root env template — DATABASE_URL, CORS_ORIGINS, ENV
├── .gitignore                          # Ignores: data/raw/, data/processed/, ml/artifacts/, .env
├── docker-compose.yml                  # PostgreSQL (db) + backend container with healthcheck
│
├── backend/                            # FastAPI application — see Section 2
├── frontend/                           # React + Vite application — see Section 3
├── ml/                                 # Training pipeline + inference layer — see Section 5
│
├── data/
│   ├── raw/
│   │   └── astram_events.csv           # GITIGNORED — original ASTRAM dataset
│   ├── processed/
│   │   ├── events_clean.csv            # GITIGNORED — output of 01_ingest.py
│   │   ├── feature_matrix.csv          # GITIGNORED — output of 02_feature_engineer.py
│   │   └── lcv_incidents.csv           # GITIGNORED — LCV-filtered subset for Flipkart panel
│   └── reference/
│       ├── corridor_junctions.json     # Static junction → corridor mapping
│       ├── planned_events_lookup.csv   # 122 planned event records
│       └── corridor_boundaries.geojson # Corridor polygon overlays for Leaflet map
│
└── scripts/
    ├── run_pipeline.sh                 # End-to-end: 01_ingest → 07_export_artifacts
    └── health_check.py                 # Verifies all model artifacts exist and load without error
```

---

## 2. Backend Tree

### Folder Structure

```
backend/
├── Dockerfile
├── requirements.txt
├── alembic.ini                         # Alembic config — points to db/migrations/, reads DATABASE_URL
│
├── main.py                             # FastAPI app factory, router registration, lifespan
├── config.py                           # Pydantic BaseSettings — DATABASE_URL, CORS_ORIGINS, ARTIFACT_DIR, ENV
│
├── api/
│   ├── __init__.py
│   ├── dependencies.py                 # Shared Depends: get_db(), get_prediction_service(), get_deployment_service(), get_forecast_service()
│   └── routes/
│       ├── __init__.py
│       ├── health.py                   # GET /health
│       ├── incidents.py                # GET /incidents, GET /incidents/summary, GET /incidents/junctions
│       ├── corridors.py                # GET /corridors/risk, GET /corridors/{corridor}/junctions
│       ├── predict.py                  # POST /predict/triage, POST /predict/planned-event-lookup
│       ├── forecast.py                 # GET /forecast/junction/{junction}, GET /forecast/corridors
│       ├── deploy.py                   # POST /deploy/recommend
│       └── flipkart.py                 # GET /lcv/risk
│
├── schemas/
│   ├── __init__.py
│   ├── common.py                       # DateRange, ErrorResponse, HealthResponse, PaginationMeta
│   ├── incident.py                     # IncidentOut, IncidentListResponse, SummaryResponse, JunctionOut, JunctionListResponse
│   ├── corridor.py                     # CorridorRiskOut, CorridorRiskListResponse, CorridorJunctionOut, CorridorJunctionListResponse
│   ├── prediction.py                   # TriageRequest, TriageResponse, PlannedEventLookupRequest, AnalogOut, PlannedEventLookupResponse
│   ├── forecast.py                     # ForecastPoint, PeakWindow, JunctionForecastResponse, CorridorForecastOut, CorridorForecastListResponse
│   ├── deployment.py                   # DeployRequest, DeployResponse
│   └── flipkart.py                     # LCVRiskResponse, LCVByCorridorOut, LCVByHourOut
│
├── db/
│   ├── __init__.py
│   ├── connection.py                   # create_engine(), SessionLocal, get_db() generator
│   ├── base.py                         # Base = declarative_base() — single source of truth for Alembic
│   ├── models/
│   │   ├── __init__.py                 # Re-exports all ORM models so Alembic autodiscovery works
│   │   ├── incident.py                 # Incident ORM model
│   │   ├── corridor.py                 # CorridorRiskIndex + CorridorStationMap ORM models
│   │   ├── station.py                  # StationConcurrency + DurationLookup ORM models
│   │   ├── triage_log.py               # TriageLog ORM model
│   │   └── planned_event.py            # PlannedEvent ORM model
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── incident_repository.py      # get_incidents(), get_summary(), get_junctions(), get_planned_events()
│   │   ├── corridor_repository.py      # get_corridor_risk_all(), get_corridor_junctions()
│   │   ├── station_repository.py       # get_concurrency(), get_duration_lookup()
│   │   └── triage_log_repository.py    # insert_triage_log() — insert-only, never reads
│   └── migrations/
│       ├── env.py                      # Alembic env — imports Base.metadata from db/models/__init__.py
│       ├── script.py.mako
│       └── versions/
│           └── 0001_initial_schema.py  # Creates all 7 tables in dependency order
│
├── services/
│   ├── __init__.py
│   ├── staleness_filter.py             # Staleness correction — flags is_stale_active at ingest + query time
│   ├── prediction_service.py           # Loads pkl artifacts at startup, encodes input, runs predict_proba — supports MOCK_MODE
│   ├── deployment_service.py           # Rule-based engine — reads station JSON artifacts, applies escalation tier logic
│   └── forecast_service.py             # Loads Prophet pkl per junction, calls model.predict(), returns structured forecast
│
└── core/
    ├── __init__.py
    ├── logging.py                      # Structured JSON logging, logger factory, uvicorn log config
    └── middleware.py                   # CORS middleware, request ID header injection, response time logging
```

### File Purpose & Ownership Reference

| File | Purpose | Owner |
|---|---|---|
| `main.py` | App factory, router mounting, lifespan (loads all artifacts on startup) | M2 |
| `config.py` | `DATABASE_URL`, `CORS_ORIGINS`, `ARTIFACT_DIR`, `ENV` from env | M2 |
| `api/dependencies.py` | `get_db()`, `get_prediction_service()`, `get_deployment_service()`, `get_forecast_service()` | M2 |
| `api/routes/health.py` | `GET /health` — returns artifact readiness flags per service | M2 |
| `api/routes/incidents.py` | Three incident endpoints — DB reads only, no ML | M2 |
| `api/routes/corridors.py` | Corridor risk leaderboard + junction breakdown — JSON artifact or DB reads | M2 |
| `api/routes/predict.py` | Triage inference + planned event analog lookup | M2 + M1 |
| `api/routes/forecast.py` | Prophet forecast per junction and corridor summary | M2 + M1 |
| `api/routes/deploy.py` | Deployment recommendation — delegates entirely to deployment_service | M2 |
| `api/routes/flipkart.py` | LCV risk by corridor and hour — pre-computed reads from DB | M2 |
| `schemas/common.py` | Shared schema primitives used across all routes | M2 |
| `schemas/incident.py` | All incident and junction response shapes | M2 |
| `schemas/corridor.py` | All corridor risk response shapes | M2 |
| `schemas/prediction.py` | Triage request/response + planned event shapes | M2 |
| `schemas/forecast.py` | Forecast time series and summary response shapes | M2 |
| `schemas/deployment.py` | Deployment request and response shapes | M2 |
| `schemas/flipkart.py` | LCV risk response shapes | M2 |
| `db/connection.py` | Engine creation, session factory, `get_db` generator | M2 |
| `db/base.py` | `Base = declarative_base()` — imported by every ORM model | M2 |
| `db/models/incident.py` | `Incident` ORM table definition with all indexes | M2 |
| `db/models/corridor.py` | `CorridorRiskIndex`, `CorridorStationMap` ORM definitions | M2 |
| `db/models/station.py` | `StationConcurrency`, `DurationLookup` ORM definitions | M2 |
| `db/models/triage_log.py` | `TriageLog` ORM definition — UUID PK, gen_random_uuid() default | M2 |
| `db/models/planned_event.py` | `PlannedEvent` ORM definition | M2 |
| `db/repositories/incident_repository.py` | All incident and planned event queries | M2 |
| `db/repositories/corridor_repository.py` | Corridor risk and junction queries | M2 |
| `db/repositories/station_repository.py` | Concurrency and duration lookup reads | M2 |
| `db/repositories/triage_log_repository.py` | Insert-only triage log writer | M2 |
| `db/migrations/versions/0001_initial_schema.py` | Creates all 7 tables in dependency order | M2 |
| `services/staleness_filter.py` | Identifies stale-active records, sets `is_stale_active` | M1 + M2 |
| `services/prediction_service.py` | Loads pkl artifacts, encodes inputs, runs inference — MOCK_MODE if artifacts missing | M1 |
| `services/deployment_service.py` | Station map lookups, officer count formula, escalation tier logic | M2 |
| `services/forecast_service.py` | Loads Prophet pkl per junction, returns structured 72h forecast | M1 |
| `core/logging.py` | JSON log formatter, `get_logger(name)` factory | M2 |
| `core/middleware.py` | CORS, `X-Request-ID` header, response time logging | M2 |

---

## 3. Frontend Tree

### Folder Structure

```
frontend/
├── package.json
├── vite.config.js                      # Vite base URL, env prefix VITE_, proxy for /api in dev
├── tailwind.config.js
├── index.html
├── .env.example                        # VITE_API_BASE_URL, VITE_USE_MOCK
│
└── src/
    ├── main.jsx                        # ReactDOM.createRoot, BrowserRouter wrapper
    ├── App.jsx                         # React Router <Routes> definitions, AppShell wrapper
    │
    ├── api/
    │   ├── client.js                   # Axios instance, base URL, USE_MOCK flag, request + error interceptors
    │   ├── incidents.js                # fetchIncidents(filters), fetchSummary(), fetchJunctions()
    │   ├── corridors.js                # fetchCorridorRisk(), fetchCorridorJunctions(corridor)
    │   ├── predict.js                  # submitTriage(form), submitPlannedEventLookup(form)
    │   ├── forecast.js                 # fetchJunctionForecast(junction, hoursAhead), fetchCorridorForecast()
    │   ├── deploy.js                   # submitDeployRecommend(form)
    │   ├── flipkart.js                 # fetchLCVRisk()
    │   └── mocks/
    │       ├── summary.json            # Matches GET /incidents/summary response shape exactly
    │       ├── incidents.json          # 50 representative records across all corridors + priorities
    │       ├── junctions.json          # Top 20 junctions with coordinates and incident counts
    │       ├── corridorRisk.json       # All corridors with composite_risk_score and station data
    │       ├── triageResultA.json      # Standard High priority prediction — disagreement_flag: false
    │       ├── triageResultB.json      # Non-corridor High priority — disagreement_flag: true, reason populated
    │       ├── deployResult.json       # Elevated tier — Yeshwanthpura primary, 5 officers
    │       ├── forecast.json           # MekhriCircle 24h forecast with 4–6am and 7–10pm peaks marked
    │       └── lcvRisk.json            # LCV by corridor (avoid/caution/prefer) + hourly profile
    │
    ├── store/
    │   ├── useIncidentStore.js         # incidents[], summaryStats, corridorRisk[], junctions[], loading, error
    │   ├── useTriageStore.js           # formValues, predictionResult, deploymentResult, loading, error
    │   └── useMapStore.js              # selectedCorridor, selectedCause, selectedPriority, selectedEventType, mapBounds
    │
    ├── components/
    │   │
    │   ├── layout/
    │   │   ├── AppShell.jsx            # Root layout shell — Sidebar + TopBar + page outlet
    │   │   ├── Sidebar.jsx             # NavItems for all 5 screens, collapse on mobile
    │   │   └── TopBar.jsx              # GridSense logo + SummaryStatBar (reads useIncidentStore.summaryStats)
    │   │
    │   ├── map/
    │   │   ├── CommandCenterMap.jsx    # Leaflet MapContainer host — composes IncidentLayer, JunctionMarker, CorridorOverlay, MapFilterPanel
    │   │   ├── IncidentLayer.jsx       # CircleMarker per incident — coloured by priority, filtered via useMapStore
    │   │   ├── JunctionMarker.jsx      # Custom Leaflet marker per top junction — size proportional to incident_count
    │   │   ├── CorridorOverlay.jsx     # GeoJSON polygon layer from data/reference/corridor_boundaries.geojson
    │   │   └── MapFilterPanel.jsx      # Dropdowns + radios for corridor/cause/priority/event_type — writes to useMapStore
    │   │
    │   ├── triage/
    │   │   ├── TriageScreen.jsx        # Composes TriageForm + PredictionResultCard, handles submit → useTriageStore
    │   │   ├── TriageForm.jsx          # Controlled inputs: corridor, event_cause, vehicle_type, hour_of_day, day_of_week
    │   │   ├── PredictionResultCard.jsx # Closure probability gauge + PriorityChip + duration p25/p75 bar + QuickDeployButton
    │   │   └── DisagreementFlag.jsx    # Conditional — renders only when predictionResult.disagreement_flag = true
    │   │
    │   ├── forecast/
    │   │   ├── ForecastScreen.jsx      # Junction dropdown selector + JunctionForecastChart host
    │   │   ├── JunctionForecastChart.jsx # Recharts LineChart — yhat line + yhat_lower/upper confidence band + peak highlights
    │   │   └── PeakHourBadge.jsx       # Pill badge for peak window labels (early morning / evening)
    │   │
    │   ├── deployment/
    │   │   ├── DeploymentScreen.jsx    # Composes deployment form + DeploymentResultCard; accepts pre-fill via router state from QuickDeployButton
    │   │   ├── DeploymentResultCard.jsx # EscalationTierBadge + primary + secondary StationBadge + junction list + rationale text
    │   │   ├── StationBadge.jsx        # Station name + officer count + incident history card
    │   │   └── EscalationTierBadge.jsx # Prop-driven chip: Critical (red) / Elevated (amber) / Routine (green)
    │   │
    │   ├── flipkart/
    │   │   ├── FlipkartPanel.jsx       # 4 LCV StatCards + LCVRiskChart + CorridorRiskTable + FlipkartInsightBox
    │   │   ├── LCVRiskChart.jsx        # Recharts HorizontalBarChart — LCV incidents per corridor
    │   │   └── CorridorRiskTable.jsx   # Table rows: corridor name + lcv_incidents + avoid/caution/prefer tag + peak_hour
    │   │
    │   └── shared/
    │       ├── StatCard.jsx            # Reusable stat tile — label, value, optional delta and icon
    │       ├── CorridorBadge.jsx       # Corridor name pill — colour-coded by composite_risk_score band
    │       ├── PriorityChip.jsx        # High/Low chip with probability percentage label
    │       ├── LoadingSpinner.jsx      # Spinner for all async loading states
    │       └── ErrorBoundary.jsx       # React error boundary — wraps each screen page
    │
    └── pages/
        ├── Map.jsx             # Screen A — CommandCenterMap + CorridorRiskSidebar
        ├── Triage.jsx          # Screen C/D — TriageScreen
        ├── Forecast.jsx        # Screen E — ForecastScreen
        ├── Deployment.jsx      # Screen F — DeploymentScreen
        └── Flipkart.jsx        # Screen G — FlipkartPanel
```

### File Purpose & Ownership Reference

| File | Purpose | Owner |
|---|---|---|
| `main.jsx` | `ReactDOM.createRoot`, `BrowserRouter` wrap | M3 |
| `App.jsx` | `<Routes>` definitions mapping paths to page components | M3 |
| `api/client.js` | Axios base URL, `USE_MOCK` flag from `VITE_USE_MOCK`, request + error interceptors | M4 |
| `api/incidents.js` | `fetchIncidents()`, `fetchSummary()`, `fetchJunctions()` | M4 |
| `api/corridors.js` | `fetchCorridorRisk()`, `fetchCorridorJunctions()` | M4 |
| `api/predict.js` | `submitTriage()`, `submitPlannedEventLookup()` | M4 |
| `api/forecast.js` | `fetchJunctionForecast()`, `fetchCorridorForecast()` | M4 |
| `api/deploy.js` | `submitDeployRecommend()` | M4 |
| `api/flipkart.js` | `fetchLCVRisk()` | M4 |
| `api/mocks/*.json` | Static mock responses matching real API shapes — returned by client.js when USE_MOCK=true | M4 |
| `store/useIncidentStore.js` | Incident list, summary stats, corridor risk, junction data + async actions | M4 |
| `store/useTriageStore.js` | Triage form state, prediction result, deployment result + async actions | M4 |
| `store/useMapStore.js` | Map filter selections and Leaflet viewport bounds — local UI state only | M3 |
| `components/layout/AppShell.jsx` | Root layout composition | M3 |
| `components/layout/Sidebar.jsx` | Navigation, collapse behaviour | M3 |
| `components/layout/TopBar.jsx` | Logo + stat bar | M3 |
| `components/map/CommandCenterMap.jsx` | Leaflet `MapContainer` host | M3 |
| `components/map/IncidentLayer.jsx` | Incident → CircleMarker mapping with filter application | M3 |
| `components/map/JunctionMarker.jsx` | Custom Leaflet marker for top junctions | M3 |
| `components/map/CorridorOverlay.jsx` | Static GeoJSON polygon layer | M3 |
| `components/map/MapFilterPanel.jsx` | Filter UI writing to `useMapStore` | M3 |
| `components/triage/TriageScreen.jsx` | Submit flow orchestration | M4 |
| `components/triage/TriageForm.jsx` | Controlled form inputs | M4 |
| `components/triage/PredictionResultCard.jsx` | Prediction result display + QuickDeployButton | M4 |
| `components/triage/DisagreementFlag.jsx` | Conditional off-corridor alert | M4 |
| `components/forecast/ForecastScreen.jsx` | Junction selector + chart host | M3 |
| `components/forecast/JunctionForecastChart.jsx` | Recharts 72h time series with confidence band | M4 |
| `components/forecast/PeakHourBadge.jsx` | Peak window label pill | M4 |
| `components/deployment/DeploymentScreen.jsx` | Pre-fill from router state + form + result card | M4 |
| `components/deployment/DeploymentResultCard.jsx` | Full deployment recommendation display | M4 |
| `components/deployment/StationBadge.jsx` | Station name + officer count card | M4 |
| `components/deployment/EscalationTierBadge.jsx` | Colour-coded escalation tier chip | M4 |
| `components/flipkart/FlipkartPanel.jsx` | Full LCV panel composition | M3 |
| `components/flipkart/LCVRiskChart.jsx` | Recharts horizontal bar chart | M4 |
| `components/flipkart/CorridorRiskTable.jsx` | Table with risk tags | M4 |
| `components/shared/StatCard.jsx` | Generic stat tile | M4 |
| `components/shared/CorridorBadge.jsx` | Colour-coded corridor pill | M4 |
| `components/shared/PriorityChip.jsx` | Priority chip with probability | M4 |
| `components/shared/LoadingSpinner.jsx` | Async loading indicator | M3 |
| `components/shared/ErrorBoundary.jsx` | React error boundary | M3 |
| `pages/Map.jsx` | Screen A page — wraps CommandCenterMap | M3 |
| `pages/Triage.jsx` | Screen C/D page — wraps TriageScreen | M4 |
| `pages/Forecast.jsx` | Screen E page — wraps ForecastScreen | M3 |
| `pages/Deployment.jsx` | Screen F page — wraps DeploymentScreen | M4 |
| `pages/Flipkart.jsx` | Screen G page — wraps FlipkartPanel | M3 |

---

## 4. Database Structure

### Table Ownership

| Table | ORM Model File | Repository File | Seeded By | Written at Runtime |
|---|---|---|---|---|
| `incidents` | `db/models/incident.py` | `incident_repository.py` | `seed_db.py` | Never |
| `corridor_risk_index` | `db/models/corridor.py` | `corridor_repository.py` | `seed_db.py` | Never |
| `corridor_station_map` | `db/models/corridor.py` | `corridor_repository.py` | `seed_db.py` | Never |
| `station_concurrency` | `db/models/station.py` | `station_repository.py` | `seed_db.py` | Never |
| `duration_lookup` | `db/models/station.py` | `station_repository.py` | `seed_db.py` | Never |
| `triage_log` | `db/models/triage_log.py` | `triage_log_repository.py` | Never | Every `POST /predict/triage` call |
| `planned_events` | `db/models/planned_event.py` | `incident_repository.py` | `seed_db.py` | Never |

### Migration Strategy

| File | Purpose |
|---|---|
| `alembic.ini` | Points `script_location` to `db/migrations/`, reads `DATABASE_URL` from env |
| `db/migrations/env.py` | Imports `Base.metadata` from `db/models/__init__.py`, connects using `config.py` `DATABASE_URL` |
| `db/migrations/versions/0001_initial_schema.py` | Creates all 7 tables in a single migration |

**Table creation order inside `0001_initial_schema.py`** (respects FK dependencies):

1. `incidents`
2. `planned_events`
3. `duration_lookup`
4. `corridor_risk_index`
5. `corridor_station_map` → FK on `corridor_risk_index.corridor`
6. `station_concurrency`
7. `triage_log`

### Repository Method Reference

| Repository | Methods | Called By |
|---|---|---|
| `incident_repository.py` | `get_incidents(db, filters)` | `routes/incidents.py` |
| | `get_summary(db)` | `routes/incidents.py` |
| | `get_junctions(db)` | `routes/incidents.py` |
| | `get_planned_events(db, filters)` | `routes/predict.py` |
| | `get_lcv_risk(db)` | `routes/flipkart.py` |
| `corridor_repository.py` | `get_corridor_risk_all(db)` | `routes/corridors.py` |
| | `get_corridor_junctions(db, corridor)` | `routes/corridors.py` |
| `station_repository.py` | `get_concurrency(db, station, hour, dow)` | `services/deployment_service.py` |
| | `get_duration_lookup(db, event_cause)` | `services/prediction_service.py` |
| `triage_log_repository.py` | `insert_triage_log(db, log_data)` | `routes/predict.py` (post-inference) |

### Index Reference

| Table | Index Name | Columns | Type |
|---|---|---|---|
| `incidents` | `idx_incidents_corridor` | `corridor` | Standard |
| `incidents` | `idx_incidents_junction` | `junction` | Standard |
| `incidents` | `idx_incidents_start_datetime` | `start_datetime` | Standard |
| `incidents` | `idx_incidents_status` | `status` | Standard |
| `incidents` | `idx_incidents_priority` | `priority` | Standard |
| `incidents` | `idx_incidents_police_station` | `police_station` | Standard |
| `incidents` | `idx_incidents_geo` | `(latitude, longitude)` | Standard |
| `incidents` | `idx_incidents_non_stale_corridor` | `corridor WHERE is_stale_active = FALSE` | Partial |
| `station_concurrency` | unique constraint | `(police_station, hour_of_day, day_of_week)` | Unique |
| `corridor_station_map` | unique constraint | `(corridor, rank)` | Unique |

---

## 5. ML Structure

### Folder Structure

```
ml/
├── requirements.txt                    # scikit-learn, xgboost, prophet, pandas, joblib, numpy
│
├── pipeline/
│   ├── 01_ingest.py                    # Load raw CSV → staleness filter → compute derived fields → write events_clean.csv + lcv_incidents.csv
│   ├── 02_feature_engineer.py          # Build feature matrix → fit LabelEncoders → write feature_matrix.csv + encoders.pkl
│   ├── 03_train_closure.py             # Train XGBoost (scale_pos_weight for imbalance) → evaluate → write closure_model.pkl
│   ├── 04_train_priority.py            # Train Random Forest (class_weight=balanced) → evaluate overall + Non-corridor subset → write priority_model.pkl
│   ├── 05_train_duration.py            # Group by event_cause → compute median/p25/p75 → write duration_lookup.json
│   ├── 06_train_forecast.py            # Train Prophet per junction (>= 15 incidents) → compute MAE → write prophet_models/*.pkl
│   └── 07_export_artifacts.py          # Build corridor_risk_index.json, station_map.json, station_concurrency.json → verify all artifacts loadable
│
├── features/
│   ├── __init__.py
│   ├── encoders.py                     # load_encoders(), encode_input() — maps unseen labels to -1
│   ├── time_features.py                # extract_time_features() — hour_sin = sin(2π×hour/24), hour_cos
│   ├── corridor_features.py            # get_corridor_flags() — is_high_priority_corridor, is_non_corridor
│   └── historical_features.py          # get_station_recommendation(), get_station_concurrency(), get_corridor_risk() — reads from JSON artifacts
│
├── artifacts/                          # GITIGNORED — generated by pipeline, must be present for backend to start
│   ├── closure_model.pkl               # XGBoost closure predictor (Model 1)
│   ├── priority_model.pkl              # Random Forest priority classifier (Model 3)
│   ├── duration_lookup.json            # Median + p25/p75 per event_cause
│   ├── corridor_risk_index.json        # composite_risk_score + top station per corridor
│   ├── station_map.json                # Corridor → ranked top-3 police stations
│   ├── station_concurrency.json        # Station × hour × dow → avg_concurrent + max_concurrent
│   ├── encoders.pkl                    # Fitted LabelEncoders for corridor, event_cause, vehicle_type
│   └── prophet_models/
│       ├── MekhriCircle.pkl
│       ├── SilkBoardJunc.pkl
│       ├── JalahalliCross.pkl
│       └── ...                         # One .pkl per junction with >= 15 incidents (~20–30 total)
│
├── evaluation/
│   ├── evaluate_closure.py             # AUC-ROC, precision, recall, F1 at threshold=0.35, confusion matrix
│   ├── evaluate_priority.py            # Overall accuracy, Non-corridor subset accuracy, top-10 feature importance
│   └── evaluate_forecast.py            # MAE per junction on held-out last 14 days
│
└── notebooks/
    ├── 01_eda.ipynb                    # Dataset distributions, null rates, corridor breakdown, planned vs unplanned split
    ├── 02_feature_analysis.ipynb       # Feature importance, correlation, cyclical encoding validation
    └── 03_model_selection.ipynb        # Baseline comparison — LogReg vs RF vs XGBoost for closure and priority
```

### Pipeline Script Ownership & Dependencies

| Script | Owner | Input | Output | Blocks |
|---|---|---|---|---|
| `01_ingest.py` | M1 | `data/raw/astram_events.csv` | `events_clean.csv`, `lcv_incidents.csv` | Everything |
| `02_feature_engineer.py` | M1 | `events_clean.csv` | `feature_matrix.csv`, `encoders.pkl` | Models 1, 3 |
| `03_train_closure.py` | M1 | `feature_matrix.csv` | `closure_model.pkl` | `POST /predict/triage` |
| `04_train_priority.py` | M1 | `feature_matrix.csv` | `priority_model.pkl` | `POST /predict/triage` |
| `05_train_duration.py` | M1 | `events_clean.csv` | `duration_lookup.json` | `POST /predict/triage` |
| `06_train_forecast.py` | M1 | `events_clean.csv` | `prophet_models/*.pkl` | `GET /forecast/junction/{junction}` |
| `07_export_artifacts.py` | M1 | `events_clean.csv` | `corridor_risk_index.json`, `station_map.json`, `station_concurrency.json` | `POST /deploy/recommend`, `GET /corridors/risk` |

**Note:** `07_export_artifacts.py` JSON section (non-model artifacts) can run immediately after `01_ingest.py` on Day 2, without waiting for model training. Split the script or run it twice: once for JSON artifacts (Day 2), once for full artifact verification (Day 5).

### Artifact Loading Architecture

All artifacts loaded **once** in `main.py` `lifespan` context. Injected into services via `api/dependencies.py`.

| Artifact | Loaded In | Injected Via | Used By Route |
|---|---|---|---|
| `closure_model.pkl` | `lifespan` | `get_prediction_service()` | `POST /predict/triage` |
| `priority_model.pkl` | `lifespan` | `get_prediction_service()` | `POST /predict/triage` |
| `encoders.pkl` | `lifespan` | `get_prediction_service()` | `POST /predict/triage` |
| `duration_lookup.json` | `lifespan` | `get_prediction_service()` | `POST /predict/triage` |
| `station_map.json` | `lifespan` | `get_deployment_service()` | `POST /deploy/recommend` |
| `station_concurrency.json` | `lifespan` | `get_deployment_service()` | `POST /deploy/recommend` |
| `corridor_risk_index.json` | `lifespan` | `get_deployment_service()` + route direct | `GET /corridors/risk`, `GET /forecast/corridors` |
| `prophet_models/*.pkl` | `lifespan` (lazy per junction) | `get_forecast_service()` | `GET /forecast/junction/{junction}` |

### MOCK_MODE Architecture

`prediction_service.py` checks for artifact presence at startup:

```
MOCK_MODE = True   → if closure_model.pkl or priority_model.pkl are missing
MOCK_MODE = False  → if all artifacts load without error
```

When `MOCK_MODE = True`, all service methods return hardcoded plausible responses matching the real response schemas. This allows M2 to implement and test `POST /predict/triage` before M1 finishes training on Day 4–5.

`GET /health` exposes `"mock_mode": true/false` in its response so the frontend can display a banner when running against stubs.

---

## 6. API File Mapping

### Endpoint → Route File → Schema → Service → Repository

| Endpoint | Method | Route File | Request Schema | Response Schema | Service | Repository |
|---|---|---|---|---|---|---|
| `/health` | GET | `health.py` | — | `HealthResponse` | — | — |
| `/incidents` | GET | `incidents.py` | Query: corridor, cause, priority, event_type, exclude_stale, limit, offset | `IncidentListResponse` | — | `incident_repository.get_incidents()` |
| `/incidents/summary` | GET | `incidents.py` | — | `SummaryResponse` | — | `incident_repository.get_summary()` |
| `/incidents/junctions` | GET | `incidents.py` | — | `JunctionListResponse` | — | `incident_repository.get_junctions()` |
| `/corridors/risk` | GET | `corridors.py` | — | `CorridorRiskListResponse` | — | `corridor_repository.get_corridor_risk_all()` |
| `/corridors/{corridor}/junctions` | GET | `corridors.py` | Path: corridor | `CorridorJunctionListResponse` | — | `corridor_repository.get_corridor_junctions()` |
| `/predict/triage` | POST | `predict.py` | `TriageRequest` | `TriageResponse` | `prediction_service.predict_triage()` | `triage_log_repository.insert_triage_log()` |
| `/predict/planned-event-lookup` | POST | `predict.py` | `PlannedEventLookupRequest` | `PlannedEventLookupResponse` | — | `incident_repository.get_planned_events()` |
| `/forecast/junction/{junction}` | GET | `forecast.py` | Path: junction, Query: hours_ahead | `JunctionForecastResponse` | `forecast_service.get_junction_forecast()` | — |
| `/forecast/corridors` | GET | `forecast.py` | — | `CorridorForecastListResponse` | `forecast_service.get_corridor_summary()` | — |
| `/deploy/recommend` | POST | `deploy.py` | `DeployRequest` | `DeployResponse` | `deployment_service.recommend()` | — |
| `/lcv/risk` | GET | `flipkart.py` | — | `LCVRiskResponse` | — | `incident_repository.get_lcv_risk()` |

### Schema Field Definitions

#### `TriageRequest`

| Field | Type | Notes |
|---|---|---|
| `corridor` | `str \| None` | Null = Non-corridor path — triggers disagreement flag check |
| `event_cause` | `str` | Required |
| `vehicle_type` | `str \| None` | Optional — sets `has_vehicle_type` feature flag |
| `hour_of_day` | `int` | 0–23 |
| `day_of_week` | `int` | 0 = Monday, 6 = Sunday |

#### `TriageResponse`

| Field | Type | Notes |
|---|---|---|
| `closure_probability` | `float` | Model 1 output, 0.0–1.0 |
| `closure_flag` | `bool` | True if closure_probability >= 0.35 |
| `priority_probability` | `float` | Model 3 output, 0.0–1.0 |
| `predicted_priority` | `str` | `"High"` or `"Low"` |
| `disagreement_flag` | `bool` | True if corridor IS NULL AND predicted_priority = High |
| `disagreement_reason` | `str \| None` | Populated only when disagreement_flag = true |
| `predicted_duration_mins` | `float` | From duration_lookup.json median |
| `duration_bucket` | `str` | `"short"` / `"medium"` / `"long"` |
| `duration_p25` | `float` | 25th percentile |
| `duration_p75` | `float` | 75th percentile |
| `model_versions` | `dict` | `{"closure_model": "v1.0", "priority_model": "v1.0"}` |
| `inference_ms` | `int` | Wall time for model inference |

#### `DeployRequest`

| Field | Type | Notes |
|---|---|---|
| `corridor` | `str` | Required — used for station_map lookup |
| `event_cause` | `str` | Required |
| `vehicle_type` | `str \| None` | Optional |
| `hour_of_day` | `int` | For concurrency lookup |
| `day_of_week` | `int` | For concurrency lookup |
| `closure_probability` | `float` | From triage result or manual override |
| `predicted_priority` | `str` | From triage result or manual override |
| `predicted_duration_mins` | `float` | For escalation tier logic |

#### `DeployResponse`

| Field | Type | Notes |
|---|---|---|
| `recommended_station` | `str` | Primary station (rank=1 from station_map) |
| `secondary_station` | `str` | Rank=2 station |
| `recommended_officer_count` | `int` | ceil(avg_concurrent + adjustment) |
| `officer_count_rationale` | `str` | Human-readable explanation of formula |
| `escalation_tier` | `str` | `"Critical"` / `"Elevated"` / `"Routine"` |
| `escalation_rationale` | `str` | Human-readable explanation of tier logic |
| `deployment_duration_mins` | `float` | Passed through from predicted_duration_mins |
| `suggested_junctions` | `list[str]` | Top junctions in the corridor |
| `corridor_risk_score` | `float` | From corridor_risk_index.json |
| `historical_station_incidents` | `int` | Total incidents handled by recommended_station |

#### Escalation Tier Logic (reference for deployment_service.py)

| Tier | Condition |
|---|---|
| `Critical` | `closure_probability >= 0.60` OR (`predicted_priority = "High"` AND `predicted_duration_mins >= 120`) |
| `Elevated` | `predicted_priority = "High"` AND `closure_probability >= 0.25` AND `predicted_duration_mins < 120` |
| `Routine` | All other cases |

---

## 7. Zustand Store Mapping

### `useIncidentStore`

**File:** `src/store/useIncidentStore.js`

| Property | Type | Source API | Populated By |
|---|---|---|---|
| `incidents` | `Incident[]` | `GET /incidents` | `fetchIncidents(filters)` |
| `summaryStats` | `SummaryResponse` | `GET /incidents/summary` | `fetchSummary()` |
| `corridorRisk` | `CorridorRisk[]` | `GET /corridors/risk` | `fetchCorridorRisk()` |
| `junctions` | `Junction[]` | `GET /incidents/junctions` | `fetchJunctions()` |
| `loading` | `boolean` | internal | async action lifecycle |
| `error` | `string \| null` | internal | async action lifecycle |

**Consumed by:**

| Component | Properties Read |
|---|---|
| `TopBar` | `summaryStats` |
| `IncidentLayer` | `incidents` |
| `JunctionMarker` | `junctions` |
| `MapFilterPanel` | `incidents` (for building filter option lists) |
| `CorridorRiskSidebar` | `corridorRisk` |

**Mock file:** `api/mocks/summary.json`, `api/mocks/incidents.json`, `api/mocks/junctions.json`, `api/mocks/corridorRisk.json`

---

### `useTriageStore`

**File:** `src/store/useTriageStore.js`

| Property | Type | Source API | Populated By |
|---|---|---|---|
| `formValues` | `TriageFormValues` | User input | `setFormValues(values)` |
| `predictionResult` | `TriageResponse \| null` | `POST /predict/triage` | `submitTriage(form)` |
| `deploymentResult` | `DeployResponse \| null` | `POST /deploy/recommend` | `submitDeploy(form)` |
| `loading` | `boolean` | internal | async action lifecycle |
| `error` | `string \| null` | internal | async action lifecycle |

**Consumed by:**

| Component | Properties Read |
|---|---|
| `TriageForm` | `formValues`, `loading` |
| `PredictionResultCard` | `predictionResult` |
| `DisagreementFlag` | `predictionResult.disagreement_flag`, `predictionResult.disagreement_reason` |
| `DeploymentScreen` | `predictionResult` (for pre-fill via router state), `deploymentResult` |
| `DeploymentResultCard` | `deploymentResult` |

**Cross-screen navigation note:** `QuickDeployButton` in `PredictionResultCard` navigates to `/deployment` using `react-router-dom` `useNavigate` with `state: { prefill: predictionResult }`. `DeploymentScreen` reads `useLocation().state.prefill` on mount and pre-fills its form.

**Mock files:** `api/mocks/triageResultA.json`, `api/mocks/triageResultB.json`, `api/mocks/deployResult.json`

---

### `useMapStore`

**File:** `src/store/useMapStore.js`

| Property | Type | Source | Set By |
|---|---|---|---|
| `selectedCorridor` | `string \| null` | User interaction | `setFilter('corridor', value)` |
| `selectedCause` | `string \| null` | User interaction | `setFilter('cause', value)` |
| `selectedPriority` | `string \| null` | User interaction | `setFilter('priority', value)` |
| `selectedEventType` | `string \| null` | User interaction | `setFilter('eventType', value)` |
| `mapBounds` | `LatLngBounds \| null` | Leaflet viewport event | `setMapBounds(bounds)` |

**Consumed by:**

| Component | Properties Read |
|---|---|
| `MapFilterPanel` | All filter states (for controlled inputs) |
| `IncidentLayer` | All filter states (applies client-side filtering to `useIncidentStore.incidents`) |
| `CommandCenterMap` | `mapBounds` |

**No API ownership.** `useMapStore` is UI state only. It never calls any API function directly.

---

## 8. Component Ownership Matrix

| Component | Owner | API Client File | Zustand Store | Mock JSON | Screen |
|---|---|---|---|---|---|
| `AppShell` | M3 | — | — | — | All |
| `Sidebar` | M3 | — | — | — | All |
| `TopBar` | M3 | — | `useIncidentStore.summaryStats` | `summary.json` | All |
| `CommandCenterMap` | M3 | `incidents.js` (via store) | `useIncidentStore`, `useMapStore` | `incidents.json` | A |
| `IncidentLayer` | M3 | — | `useIncidentStore.incidents` + `useMapStore` | — | A |
| `JunctionMarker` | M3 | — | `useIncidentStore.junctions` | `junctions.json` | A |
| `CorridorOverlay` | M3 | — | — (static GeoJSON file) | — | A |
| `MapFilterPanel` | M3 | — | `useMapStore` (write), `useIncidentStore` (options) | — | A |
| `CorridorRiskSidebar` | M4 | `corridors.js` (via store) | `useIncidentStore.corridorRisk` | `corridorRisk.json` | A |
| `TriageScreen` | M4 | `predict.js` (via store) | `useTriageStore` | — | C/D |
| `TriageForm` | M4 | — | `useTriageStore.formValues` (write) | — | C/D |
| `PredictionResultCard` | M4 | — | `useTriageStore.predictionResult` (read) | `triageResultA.json` | C/D |
| `DisagreementFlag` | M4 | — | `useTriageStore.predictionResult.disagreement_flag` | `triageResultB.json` | C/D |
| `ForecastScreen` | M3 | `forecast.js` (local state) | — | `forecast.json` | E |
| `JunctionForecastChart` | M4 | — | — (props) | — | E |
| `PeakHourBadge` | M4 | — | — (props) | — | E |
| `DeploymentScreen` | M4 | `deploy.js` (via store) | `useTriageStore` (read + write) | `deployResult.json` | F |
| `DeploymentResultCard` | M4 | — | `useTriageStore.deploymentResult` (read) | — | F |
| `StationBadge` | M4 | — | — (props) | — | F |
| `EscalationTierBadge` | M4 | — | — (props) | — | F, C/D |
| `FlipkartPanel` | M3 | `flipkart.js` (local state) | — | `lcvRisk.json` | G |
| `LCVRiskChart` | M4 | — | — (props) | — | G |
| `CorridorRiskTable` | M4 | — | — (props) | — | G |
| `StatCard` | M4 | — | — (props) | — | Multiple |
| `CorridorBadge` | M4 | — | — (props) | — | Multiple |
| `PriorityChip` | M4 | — | — (props) | — | Multiple |
| `LoadingSpinner` | M3 | — | — (props) | — | Multiple |
| `ErrorBoundary` | M3 | — | — | — | All screens |

---

## 9. Development Order

### Hard Blocking Dependencies

Nothing downstream can start until these complete:

| Item | Owner | Day | Blocks |
|---|---|---|---|
| `docker-compose.yml` + PostgreSQL running | M2 | 1 | `seed_db.py`, backend integration |
| FastAPI scaffold + `GET /health` | M2 | 1 | All other routes |
| `01_ingest.py` complete → `events_clean.csv` | M1 | 1–2 | All ML and DB seeding |
| `02_feature_engineer.py` → `encoders.pkl` | M1 | 2 | Models 1, 3 |
| `seed_db.py` → incidents table seeded | M2 | 2 | `GET /incidents`, all DB routes |
| All 9 mock JSON files created | M4 | 1 | All frontend development |
| Zustand stores wired to mock JSON | M4 | 1 | All component development |
| `03_train_closure.py` → `closure_model.pkl` | M1 | 3 | `POST /predict/triage` real mode |
| `04_train_priority.py` → `priority_model.pkl` | M1 | 4 | `POST /predict/triage` real mode |
| `07_export_artifacts.py` JSON section | M1 | 2 | `POST /deploy/recommend`, `GET /corridors/risk` |

---

### Day-by-Day Assignments

#### Week 1

| Day | M1 — ML Lead | M2 — Backend | M3 — Frontend Lead | M4 — Data Eng + QA |
|---|---|---|---|---|
| **1** | Set up ML venv, run `01_ingest.py`, validate `events_clean.csv` (null check, date parse, row count) | Repo init, `.env.example`, `docker-compose.yml` with healthcheck, FastAPI scaffold, `config.py`, `core/logging.py`, `core/middleware.py`, `GET /health` | React + Vite scaffold, Tailwind config, React Router, `AppShell`, `Sidebar`, `TopBar` (static) | Create all 9 mock JSON files, configure `client.js` with `USE_MOCK` flag, scaffold all 3 Zustand stores wired to mock data |
| **2** | `02_feature_engineer.py` → `feature_matrix.csv` + `encoders.pkl`. Run `05_train_duration.py`. Run `07_export_artifacts.py` JSON section only (duration_lookup, station_map, concurrency, corridor_risk_index) | `db/connection.py`, `db/base.py`, all 5 ORM models, `db/models/__init__.py`, `0001_initial_schema.py`, `alembic upgrade head`, `seed_db.py`, `GET /incidents`, `GET /incidents/summary` | `CommandCenterMap` + `IncidentLayer` (mock `incidents.json`), `MapFilterPanel` (local state), `CorridorOverlay` (static GeoJSON) | `TriageForm` (local state, no API), `PredictionResultCard` (mock A + B), `DisagreementFlag` |
| **3** | `03_train_closure.py` → `closure_model.pkl`. Log AUC-ROC and F1 at threshold=0.35. Begin `04_train_priority.py` | `GET /incidents/junctions`, `GET /corridors/risk` (from JSON artifact), `GET /lcv/risk`, all 4 repository files | `ForecastScreen` + `JunctionForecastChart` (mock `forecast.json`), `PeakHourBadge` | `DeploymentResultCard` (mock `deployResult.json`), `EscalationTierBadge`, `StationBadge` |
| **4** | `04_train_priority.py` → `priority_model.pkl`. Log overall accuracy + Non-corridor subset accuracy separately. Start `06_train_forecast.py` top 10 junctions | `POST /deploy/recommend` (rule-based — JSON artifacts only, no models needed), `prediction_service.py` stub with `MOCK_MODE=True` | `FlipkartPanel` + `LCVRiskChart` + `CorridorRiskTable` (mock `lcvRisk.json`) | All `api/` client functions — Axios wrappers for all 12 endpoints |
| **5** | `06_train_forecast.py` top 10 junctions complete. `07_export_artifacts.py` full run. `health_check.py` verification pass | `POST /predict/triage` (real models now available — flip `MOCK_MODE=False`), `GET /forecast/junction/{junction}` | Wire `CommandCenterMap` + `TopBar` → real `GET /incidents` and `GET /incidents/summary` | Wire `FlipkartPanel` → real `GET /lcv/risk`. Wire `DeploymentScreen` → real `POST /deploy/recommend` |

#### Week 2

| Day | M1 | M2 | M3 | M4 |
|---|---|---|---|---|
| **6** | `evaluate_closure.py` + `evaluate_priority.py`. Document metrics — AUC-ROC, F1, Non-corridor accuracy | `POST /predict/planned-event-lookup`, CORS config for Vercel domain, error handling on all routes, Swagger descriptions | **Wire `TriageScreen` → real `POST /predict/triage` ← CRITICAL PATH** | Wire `ForecastScreen` → real `GET /forecast/junction/{junction}`. Wire `CorridorRiskSidebar` → real `GET /corridors/risk` |
| **7** | `06_train_forecast.py` remaining junctions (top 20 total). `evaluate_forecast.py` MAE per junction | `GET /corridors/{corridor}/junctions`, `GET /forecast/corridors`, API request validation tightening | `JunctionMarker` wired to real `GET /incidents/junctions`. Loading states on map screen | Loading states + `ErrorBoundary` on all screens. Cross-browser test pass |
| **8** | Draft model metrics content for presentation slide | `scripts/health_check.py` — verifies all artifacts present and loadable, returns status per artifact | `QuickDeployButton` (Triage → Deployment with router state pre-fill), responsive `Sidebar` collapse | Full E2E manual test: Map → Triage → Disagreement flag → Deploy → Flipkart. Bug log |
| **9** | Support judge Q&A prep — worked prediction examples for different corridors + event causes | Deploy backend to Render.com. Set all env vars in Render dashboard. Production `seed_db.py` run | Deploy frontend to Vercel. Fix CORS and `VITE_API_BASE_URL` for production | Production smoke test all 12 endpoints on live Render URL. First full demo rehearsal |
| **10** | Finalize model card (2 pages: inputs, outputs, accuracy, known limitations) | Fix any production issues found in smoke test. Add `/health` cold-start ping from frontend | Fix any Vercel rendering issues. Add cold-start `GET /health` ping on app load | Second demo rehearsal. Prepare judge Q&A responses for top 10 questions |

#### Week 3

| Days | Focus | Owner |
|---|---|---|
| 11–12 | Architecture diagram for presentation slide | M4 |
| 11–12 | Model metrics slide — AUC-ROC, Non-corridor accuracy, Prophet MAE | M1 |
| 11–12 | UI consistency pass — typography, spacing, Recharts axis labels | M3 |
| 11–12 | README — project setup, run pipeline, seed DB, start backend, start frontend | M2 |
| 13–14 | Third demo rehearsal + timing | All |
| 13–14 | Judge Q&A dry run — each member answers questions in their domain | All |
| 15 | Submission | All |

---

### Critical Path Summary

```
Day 1:   events_clean.csv ready                         (M1)
         Mock JSON files ready                          (M4)
Day 2:   Incidents table seeded                         (M2)
         GET /incidents returning real data             (M2)
Day 4:   closure_model.pkl + priority_model.pkl ready   (M1)
         All JSON artifacts ready                       (M1)
Day 5:   POST /predict/triage returning real outputs    (M2 + M1)
Day 6:   TriageScreen wired to real API  ◄── CRITICAL PATH MILESTONE
Day 9:   Deployed to Render + Vercel
Day 15:  Submission
```

**If Day 6 milestone is hit: submission is on track.**  
**If Day 6 slips to Day 8: still achievable, reduce Week 3 polish scope.**  
**If Day 6 slips past Day 10: demo Triage screen on mock data — triageResultA.json and triageResultB.json cover the core disagreement flag moment.**

---

*End of GridSense Project Skeleton*

---

> Document version: 1.0  
> Mode: BUILD MODE — architecture frozen  
> Last updated: June 2026  
> For internal team use — Gridlock Hackathon 2.0