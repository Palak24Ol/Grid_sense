# GridSense — Implementation Plan

> Flipkart Gridlock Hackathon 2.0 · Theme 2: Event-Driven Congestion  
> Version: Final (post architecture review)  
> Team size: 4 members  
> Target timeline: 3 weeks to full submission

---

## Table of Contents

1. [Project Folder Structure](#1-project-folder-structure)
2. [Database Schema](#2-database-schema)
3. [API Design](#3-api-design)
4. [ML Training Pipeline](#4-ml-training-pipeline)
5. [Feature Engineering Pipeline](#5-feature-engineering-pipeline)
6. [Exact Model Inputs and Outputs](#6-exact-model-inputs-and-outputs)
7. [React Dashboard Component Hierarchy](#7-react-dashboard-component-hierarchy)
8. [Week-by-Week Development Plan](#8-week-by-week-development-plan)
9. [Team Role Allocation](#9-team-role-allocation)
10. [MVP Version — 48 Hours](#10-mvp-version--48-hours)
11. [Extended Version — Final Submission](#11-extended-version--final-submission)
12. [Development Order](#12-development-order)

---

## 1. Project Folder Structure

```
gridsense/
│
├── README.md
├── .env.example
├── docker-compose.yml
│
├── backend/
│   ├── main.py                          # FastAPI app entry point
│   ├── config.py                        # Environment config, constants
│   ├── requirements.txt
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── incidents.py             # /incidents endpoints
│   │   │   ├── predict.py               # /predict endpoints
│   │   │   ├── forecast.py              # /forecast endpoints
│   │   │   ├── deploy.py                # /deploy endpoints
│   │   │   ├── corridors.py             # /corridors endpoints
│   │   │   └── flipkart.py              # /lcv endpoints
│   │   └── dependencies.py              # Shared FastAPI dependencies
│   │
│   ├── models/                          # Pydantic request/response models
│   │   ├── __init__.py
│   │   ├── incident.py
│   │   ├── prediction.py
│   │   ├── forecast.py
│   │   ├── deployment.py
│   │   └── corridor.py
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py                # SQLAlchemy engine + session
│   │   ├── schema.py                    # SQLAlchemy table definitions
│   │   └── queries/
│   │       ├── __init__.py
│   │       ├── incidents.py
│   │       ├── corridors.py
│   │       └── deployments.py
│   │
│   └── services/
│       ├── __init__.py
│       ├── staleness_filter.py          # Correction layer logic
│       ├── prediction_service.py        # Calls ML models
│       ├── deployment_service.py        # Response layer logic
│       └── forecast_service.py          # Prophet wrapper
│
├── ml/
│   ├── requirements.txt
│   │
│   ├── pipeline/
│   │   ├── 01_ingest.py                 # Load raw CSV, apply staleness filter
│   │   ├── 02_feature_engineer.py       # Build feature matrix
│   │   ├── 03_train_closure.py          # Train Model 1
│   │   ├── 04_train_priority.py         # Train Model 3
│   │   ├── 05_train_duration.py         # Train duration estimator
│   │   ├── 06_train_forecast.py         # Train Prophet per junction
│   │   └── 07_export_artifacts.py       # Save all models + encoders
│   │
│   ├── features/
│   │   ├── __init__.py
│   │   ├── encoders.py                  # Label encoders, corridor maps
│   │   ├── time_features.py             # Hour, dow, month extraction
│   │   ├── corridor_features.py         # Corridor risk index builder
│   │   └── historical_features.py       # Station concurrency lookups
│   │
│   ├── artifacts/                       # Serialised model files (gitignored)
│   │   ├── closure_model.pkl
│   │   ├── priority_model.pkl
│   │   ├── duration_lookup.json         # Median duration by event_cause
│   │   ├── prophet_models/              # One .pkl per top junction
│   │   │   ├── MekhriCircle.pkl
│   │   │   ├── SilkBoardJunc.pkl
│   │   │   └── ...
│   │   ├── corridor_risk_index.json     # Pre-computed risk scores
│   │   ├── station_map.json             # Corridor → top stations
│   │   ├── station_concurrency.json     # Station × hour × dow → avg load
│   │   └── encoders.pkl                 # LabelEncoders for cat features
│   │
│   ├── evaluation/
│   │   ├── evaluate_closure.py
│   │   ├── evaluate_priority.py
│   │   └── evaluate_forecast.py
│   │
│   └── notebooks/
│       ├── 01_eda.ipynb
│       ├── 02_feature_analysis.ipynb
│       └── 03_model_selection.ipynb
│
├── data/
│   ├── raw/
│   │   └── astram_events.csv            # Original dataset (gitignored)
│   ├── processed/
│   │   ├── events_clean.csv             # After staleness filter
│   │   ├── feature_matrix.csv           # Model-ready feature set
│   │   └── lcv_incidents.csv            # LCV-filtered subset
│   └── reference/
│       ├── corridor_junctions.json      # Junction → corridor mapping
│       ├── planned_events_lookup.csv    # 122 planned event records
│       └── corridor_boundaries.geojson  # For map overlay (OpenStreetMap)
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── index.html
│   │
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       │
│       ├── api/
│       │   ├── client.js                # Axios base config
│       │   ├── incidents.js
│       │   ├── predict.js
│       │   ├── forecast.js
│       │   ├── deploy.js
│       │   └── corridors.js
│       │
│       ├── store/
│       │   ├── useIncidentStore.js      # Zustand store for incident state
│       │   ├── useTriageStore.js        # Triage form + results state
│       │   └── useMapStore.js           # Map filter state
│       │
│       ├── components/
│       │   ├── layout/
│       │   │   ├── AppShell.jsx
│       │   │   ├── Sidebar.jsx
│       │   │   └── TopBar.jsx
│       │   │
│       │   ├── map/
│       │   │   ├── CommandCenterMap.jsx  # Screen A
│       │   │   ├── IncidentLayer.jsx
│       │   │   ├── JunctionMarker.jsx
│       │   │   ├── CorridorOverlay.jsx
│       │   │   └── MapFilterPanel.jsx
│       │   │
│       │   ├── triage/
│       │   │   ├── TriageScreen.jsx      # Screen C (merged with D)
│       │   │   ├── TriageForm.jsx
│       │   │   ├── PredictionResultCard.jsx
│       │   │   └── DisagreementFlag.jsx
│       │   │
│       │   ├── forecast/
│       │   │   ├── ForecastScreen.jsx    # Screen E
│       │   │   ├── JunctionForecastChart.jsx
│       │   │   └── PeakHourBadge.jsx
│       │   │
│       │   ├── deployment/
│       │   │   ├── DeploymentScreen.jsx  # Screen F
│       │   │   ├── DeploymentResultCard.jsx
│       │   │   ├── StationBadge.jsx
│       │   │   └── EscalationTierBadge.jsx
│       │   │
│       │   ├── flipkart/
│       │   │   ├── FlipkartPanel.jsx     # Screen G
│       │   │   ├── LCVRiskChart.jsx
│       │   │   └── CorridorRiskTable.jsx
│       │   │
│       │   └── shared/
│       │       ├── StatCard.jsx
│       │       ├── CorridorBadge.jsx
│       │       ├── PriorityChip.jsx
│       │       ├── LoadingSpinner.jsx
│       │       └── ErrorBoundary.jsx
│       │
│       └── pages/
│           ├── Dashboard.jsx             # Routes to all 5 screens
│           ├── Map.jsx
│           ├── Triage.jsx
│           ├── Forecast.jsx
│           ├── Deployment.jsx
│           └── Flipkart.jsx
│
└── scripts/
    ├── seed_db.py                        # Load processed CSV into SQLite/PG
    ├── run_pipeline.sh                   # End-to-end: ingest → train → export
    └── health_check.py                   # Verify all model artifacts exist
```

---

## 2. Database Schema

### Overview

- Database: PostgreSQL (production) / SQLite (local dev)
- ORM: SQLAlchemy (backend), raw queries for analytics
- All timestamps stored as UTC

---

### Table: `incidents`

Primary store. Loaded from the processed ASTRAM CSV. Read-heavy, never written to during runtime.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | VARCHAR(20) | PRIMARY KEY | Original FKID000000 format |
| `event_type` | VARCHAR(20) | NOT NULL | `planned` or `unplanned` |
| `event_cause` | VARCHAR(50) | NOT NULL | vehicle_breakdown, accident, etc. |
| `latitude` | FLOAT | NOT NULL | |
| `longitude` | FLOAT | NOT NULL | |
| `address` | TEXT | | |
| `corridor` | VARCHAR(100) | | NULL for Non-corridor |
| `junction` | VARCHAR(100) | | |
| `zone` | VARCHAR(50) | | NULL for ~58% of records |
| `police_station` | VARCHAR(100) | NOT NULL | |
| `priority` | VARCHAR(10) | NOT NULL | `High` or `Low` |
| `requires_road_closure` | BOOLEAN | NOT NULL | |
| `vehicle_type` | VARCHAR(30) | | |
| `start_datetime` | TIMESTAMPTZ | NOT NULL | |
| `end_datetime` | TIMESTAMPTZ | | |
| `closed_datetime` | TIMESTAMPTZ | | |
| `status` | VARCHAR(20) | NOT NULL | `closed`, `resolved`, `active` |
| `is_stale_active` | BOOLEAN | NOT NULL DEFAULT FALSE | Set by staleness filter |
| `duration_mins` | FLOAT | | Computed at ingest |
| `hour_of_day` | INT | | Computed at ingest |
| `day_of_week` | INT | | 0=Mon, 6=Sun |
| `month` | INT | | |
| `is_high_priority_corridor` | BOOLEAN | NOT NULL DEFAULT FALSE | Derived field |
| `is_non_corridor` | BOOLEAN | NOT NULL DEFAULT FALSE | Derived field |
| `description` | TEXT | | Original field, may contain Kannada |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |

**Indexes:**
- `idx_incidents_corridor` on `corridor`
- `idx_incidents_junction` on `junction`
- `idx_incidents_start_datetime` on `start_datetime`
- `idx_incidents_status` on `status`
- `idx_incidents_priority` on `priority`
- `idx_incidents_police_station` on `police_station`
- `idx_incidents_geo` on `(latitude, longitude)` — for bounding box queries

---

### Table: `corridor_risk_index`

Pre-computed. Rebuilt each time the ML pipeline runs. Never written to at runtime.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `corridor` | VARCHAR(100) | PRIMARY KEY | |
| `total_incidents` | INT | NOT NULL | |
| `high_priority_count` | INT | NOT NULL | |
| `high_priority_rate` | FLOAT | NOT NULL | 0.0–1.0 |
| `closure_count` | INT | NOT NULL | |
| `closure_rate` | FLOAT | NOT NULL | 0.0–1.0 |
| `composite_risk_score` | FLOAT | NOT NULL | 0–100, computed |
| `top_junction` | VARCHAR(100) | | Highest-incident junction |
| `top_police_station` | VARCHAR(100) | | Mode station for corridor |
| `median_duration_mins` | FLOAT | | |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |

---

### Table: `station_concurrency`

Pre-computed lookup for deployment engine. Station × hour × day-of-week → average concurrent active incidents.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | SERIAL | PRIMARY KEY | |
| `police_station` | VARCHAR(100) | NOT NULL | |
| `hour_of_day` | INT | NOT NULL | 0–23 |
| `day_of_week` | INT | NOT NULL | 0–6 |
| `avg_concurrent` | FLOAT | NOT NULL | Historical average load |
| `max_concurrent` | INT | NOT NULL | Historical peak |

**Unique constraint:** `(police_station, hour_of_day, day_of_week)`

---

### Table: `corridor_station_map`

Pre-computed mapping of corridor to its top historical police stations.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | SERIAL | PRIMARY KEY | |
| `corridor` | VARCHAR(100) | NOT NULL | FK → corridor_risk_index |
| `police_station` | VARCHAR(100) | NOT NULL | |
| `incident_count` | INT | NOT NULL | How many incidents this station handled |
| `rank` | INT | NOT NULL | 1 = primary, 2 = secondary, 3 = tertiary |

**Unique constraint:** `(corridor, rank)`

---

### Table: `duration_lookup`

Median duration per event cause. Used by the duration estimator.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `event_cause` | VARCHAR(50) | PRIMARY KEY | |
| `median_duration_mins` | FLOAT | NOT NULL | |
| `p25_duration_mins` | FLOAT | | |
| `p75_duration_mins` | FLOAT | | |
| `sample_count` | INT | NOT NULL | Number of records used |

---

### Table: `triage_log`

Runtime write table. Every live prediction gets logged. Used for the post-event feedback loop in future work.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID | PRIMARY KEY DEFAULT gen_random_uuid() | |
| `session_id` | VARCHAR(50) | | Browser session ID |
| `corridor` | VARCHAR(100) | | |
| `event_cause` | VARCHAR(50) | | |
| `vehicle_type` | VARCHAR(30) | | |
| `hour_of_day` | INT | | |
| `day_of_week` | INT | | |
| `closure_probability` | FLOAT | | Model 1 output |
| `priority_probability` | FLOAT | | Model 3 output |
| `predicted_priority` | VARCHAR(10) | | |
| `disagreement_flag` | BOOLEAN | | True if Non-corridor + predicted High |
| `predicted_duration_mins` | FLOAT | | Duration lookup output |
| `recommended_station` | VARCHAR(100) | | |
| `recommended_officer_count` | INT | | |
| `escalation_tier` | VARCHAR(20) | | Routine / Elevated / Critical |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |

---

### Table: `planned_events`

122 real planned event records from the dataset. Used for the historical analog lookup.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | VARCHAR(20) | PRIMARY KEY | Original FKID |
| `event_cause` | VARCHAR(50) | NOT NULL | public_event, procession, vip_movement, protest |
| `corridor` | VARCHAR(100) | | |
| `junction` | VARCHAR(100) | | |
| `police_station` | VARCHAR(100) | | |
| `start_datetime` | TIMESTAMPTZ | | |
| `requires_road_closure` | BOOLEAN | | |
| `duration_mins` | FLOAT | | |
| `priority` | VARCHAR(10) | | |
| `description` | TEXT | | |

---

### Relationships Summary

```
incidents (id) ─────────────────────────────── (no FK, self-contained)
corridor_risk_index (corridor) ──────────────── referenced by corridor_station_map.corridor
corridor_station_map (corridor) → corridor_risk_index (corridor)
station_concurrency (police_station) ──────────── no FK, string match
triage_log ──────────────────────────────────── no FK, standalone log
planned_events ──────────────────────────────── standalone lookup
duration_lookup (event_cause) ───────────────── no FK, string match
```

---

## Problem Framing

GridSense addresses two fundamentally different congestion problems:

### Planned Events
- VIP movement
- Public events
- Processions
- Protests

These events are known beforehand and require:
- historical analog lookup
- congestion forecasting
- proactive deployment planning

### Unplanned Incidents
- accidents
- vehicle breakdowns
- water logging
- tree fall
- potholes

These events require:
- rapid triage
- road closure prediction
- priority assessment
- deployment recommendation

---

## 3. API Design

Base URL: `http://localhost:8000/api/v1`  
All responses: `Content-Type: application/json`  
All timestamps: ISO 8601 UTC strings

---

### 3.1 Incidents

#### `GET /incidents`

Returns paginated incident records for map rendering and analytics.

**Query parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `corridor` | string | null | Filter by corridor name |
| `event_cause` | string | null | Filter by cause |
| `priority` | string | null | `High` or `Low` |
| `event_type` | string | null | `planned` or `unplanned` |
| `exclude_stale` | boolean | true | Exclude stale-active incidents |
| `limit` | int | 2000 | Max records returned |
| `offset` | int | 0 | Pagination offset |

**Response:**

```json
{
  "total": 8173,
  "filtered": 743,
  "incidents": [
    {
      "id": "FKID000042",
      "event_type": "unplanned",
      "event_cause": "vehicle_breakdown",
      "latitude": 12.9718,
      "longitude": 77.5946,
      "corridor": "Mysore Road",
      "junction": "SilkBoardJunc",
      "police_station": "Halasuru Gate",
      "priority": "High",
      "requires_road_closure": false,
      "start_datetime": "2024-01-15T19:42:00Z",
      "duration_mins": 87,
      "status": "closed",
      "is_stale_active": false
    }
  ]
}
```

---

#### `GET /incidents/summary`

Returns aggregate statistics for the stats bar at top of dashboard.

**Response:**

```json
{
  "total_incidents": 8173,
  "corrected_active_count": 270,
  "raw_active_count": 1007,
  "stale_removed": 737,
  "total_closures": 676,
  "planned_count": 467,
  "unplanned_count": 7706,
  "date_range": {
    "start": "2023-11-09T19:24:48Z",
    "end": "2024-04-08T17:11:42Z",
    "days": 150
  }
}
```

---

#### `GET /incidents/junctions`

Returns junction-level aggregates for the map marker layer.

**Response:**

```json
{
  "junctions": [
    {
      "junction": "MekhriCircle",
      "latitude": 13.0056,
      "longitude": 77.5810,
      "incident_count": 64,
      "high_priority_count": 52,
      "closure_count": 4,
      "top_cause": "vehicle_breakdown"
    }
  ]
}
```

---

### 3.2 Corridors

#### `GET /corridors/risk`

Returns the pre-computed corridor risk leaderboard.

**Response:**

```json
{
  "corridors": [
    {
      "corridor": "Mysore Road",
      "total_incidents": 743,
      "high_priority_rate": 0.997,
      "closure_rate": 0.113,
      "composite_risk_score": 87.4,
      "top_junction": "SilkBoardJunc",
      "top_police_station": "Halasuru Gate",
      "median_duration_mins": 42.1
    }
  ]
}
```

---

#### `GET /corridors/{corridor}/junctions`

Returns junction breakdown within a single corridor.

**Response:**

```json
{
  "corridor": "Mysore Road",
  "total_incidents": 743,
  "junctions": [
    {
      "junction": "SilkBoardJunc",
      "incident_count": 33,
      "share_of_corridor": 0.044,
      "high_priority_count": 33,
      "closure_count": 3
    }
  ]
}
```

---

### 3.3 Predict

#### `POST /predict/triage`

Core ML inference endpoint. Accepts a hypothetical incident, returns all model outputs.

**Request:**

```json
{
  "corridor": "ORR North 1",
  "event_cause": "accident",
  "vehicle_type": "heavy_vehicle",
  "hour_of_day": 21,
  "day_of_week": 2
}
```

**Response:**

```json
{
  "closure_probability": 0.31,
  "closure_flag": false,
  "priority_probability": 0.89,
  "predicted_priority": "High",
  "disagreement_flag": false,
  "disagreement_reason": null,
  "predicted_duration_mins": 43,
  "duration_bucket": "short",
  "duration_p25": 18,
  "duration_p75": 94,
  "model_versions": {
    "closure_model": "v1.0",
    "priority_model": "v1.0"
  },
  "inference_ms": 34
}
```

### Why the disagreement flag exists

Historical operations heavily prioritize named corridors.
As a result, many Non-corridor incidents receive Low priority
even when cause, vehicle type and timing suggest elevated risk.

GridSense highlights these cases whenever:

- corridor = Non-corridor
- model predicts High priority

This prevents potentially severe incidents from being overlooked.

**Disagreement flag logic:**  
`disagreement_flag = true` when `corridor IS NULL` (Non-corridor) AND `predicted_priority = "High"`

**Response when disagreement fires:**

```json
{
  "disagreement_flag": true,
  "disagreement_reason": "This incident is off the named corridors. The current system defaults these to Low priority. Our model predicts High based on cause, vehicle type, and time pattern."
}
```

---

#### `POST /predict/planned-event-lookup`

Finds historical analog events for a new planned event.

**Request:**

```json
{
  "event_cause": "procession",
  "corridor": "Mysore Road",
  "hour_of_day": 18,
  "day_of_week": 0
}
```

**Response:**

```json
{
  "analogs": [
    {
      "id": "FKID000512",
      "event_cause": "procession",
      "corridor": "Mysore Road",
      "start_datetime": "2024-02-14T18:30:00Z",
      "duration_mins": 36,
      "requires_road_closure": true,
      "similarity_score": 0.92,
      "description": "ಮೆರವಣಿಗೆ ಸರ್"
    }
  ],
  "total_analogs_found": 3,
  "sample_size_warning": "Based on 38 historical procession records. Treat as pattern matching, not model prediction."
}
```

---

### 3.4 Forecast

#### `GET /forecast/junction/{junction}`

Returns Prophet forecast for a single junction for the next 72 hours.

**Path parameter:** `junction` — URL-encoded junction name (e.g., `MekhriCircle`)

**Query parameters:**

| Param | Type | Default |
|---|---|---|
| `hours_ahead` | int | 72 |

**Response:**

```json
{
  "junction": "MekhriCircle",
  "corridor": "Bellary Road 1",
  "historical_daily_avg": 0.43,
  "forecast": [
    {
      "datetime": "2024-06-16T18:00:00Z",
      "hour_of_day": 18,
      "predicted_incident_count": 0.6,
      "yhat_lower": 0.1,
      "yhat_upper": 1.2,
      "is_peak_hour": false
    },
    {
      "datetime": "2024-06-16T20:00:00Z",
      "hour_of_day": 20,
      "predicted_incident_count": 2.1,
      "yhat_lower": 1.4,
      "yhat_upper": 2.9,
      "is_peak_hour": true
    }
  ],
  "peak_windows": [
    { "start_hour": 4, "end_hour": 6, "label": "early morning peak" },
    { "start_hour": 19, "end_hour": 22, "label": "evening peak" }
  ],
  "model_mae": 1.2
}
```

---

#### `GET /forecast/corridors`

Returns 24-hour forecast summary for all top corridors. Used for the forecast screen overview.

**Response:**

```json
{
  "generated_at": "2024-06-16T10:00:00Z",
  "corridors": [
    {
      "corridor": "Mysore Road",
      "next_24h_predicted_incidents": 31,
      "peak_hour": 20,
      "peak_predicted_count": 4.2,
      "risk_level": "high"
    }
  ]
}
```

---

### 3.5 Deploy

#### `POST /deploy/recommend`

Deployment engine endpoint. Takes a triage result and returns the full deployment recommendation.

**Request:**

```json
{
  "corridor": "Tumkur Road",
  "event_cause": "vehicle_breakdown",
  "vehicle_type": "heavy_vehicle",
  "hour_of_day": 20,
  "day_of_week": 3,
  "closure_probability": 0.41,
  "predicted_priority": "High",
  "predicted_duration_mins": 43
}
```

**Response:**

```json
{
  "recommended_station": "Yeshwanthpura",
  "secondary_station": "Peenya",
  "recommended_officer_count": 5,
  "officer_count_rationale": "Yeshwanthpura average concurrent load at 20:00 on Thursday is 3.1 incidents. Adding 2 for High priority closure risk.",
  "escalation_tier": "Elevated",
  "escalation_rationale": "High priority, closure probability 41%, predicted duration under 2 hours.",
  "deployment_duration_mins": 43,
  "suggested_junctions": ["JalahalliCross(SM Circle)", "YeshwanthpuraCircle"],
  "corridor_risk_score": 81.2,
  "historical_station_incidents": 239
}
```

**Escalation tier logic:**

| Tier | Condition |
|---|---|
| `Critical` | `closure_probability >= 0.60` OR (`predicted_priority = High` AND `predicted_duration_mins >= 120`) |
| `Elevated` | `predicted_priority = High` AND `closure_probability >= 0.25` AND `predicted_duration_mins < 120` |
| `Routine` | All other cases |

---

### 3.6 LCV / Flipkart

#### `GET /lcv/risk`

Returns LCV-specific risk data by corridor and hour.

**Response:**

```json
{
  "total_lcv_incidents": 678,
  "lcv_high_priority_rate": 0.704,
  "lcv_closure_rate": 0.027,
  "overall_closure_rate": 0.083,
  "riskiest_hour": 20,
  "riskiest_corridor": "Tumkur Road",
  "by_corridor": [
    {
      "corridor": "Tumkur Road",
      "lcv_incidents": 81,
      "risk_tag": "avoid",
      "peak_hour": 20
    },
    {
      "corridor": "Bellary Road 1",
      "lcv_incidents": 74,
      "risk_tag": "caution",
      "peak_hour": 5
    }
  ],
  "by_hour": [
    { "hour": 20, "lcv_incidents": 72, "risk_level": "critical" },
    { "hour": 5, "lcv_incidents": 59, "risk_level": "high" },
    { "hour": 21, "lcv_incidents": 35, "risk_level": "moderate" }
  ]
}
```

**Corridor risk tag logic:**

| Tag | Condition |
|---|---|
| `avoid` | LCV incidents >= 70 |
| `caution` | LCV incidents 40–69 |
| `prefer` | LCV incidents < 40 |

---

## 4. ML Training Pipeline

Each script is self-contained and runs in sequence. Run via `scripts/run_pipeline.sh`.

---

### Step 1 — `01_ingest.py`

**Input:** `data/raw/astram_events.csv`

**Operations:**
1. Load CSV with `pd.read_csv`, parse datetimes as UTC
2. Compute `duration_mins = (closed_datetime - start_datetime).total_seconds() / 60`
3. Apply staleness filter: set `is_stale_active = True` where `status == 'active'` AND `modified_datetime` is older than 30 days from dataset end date (2024-04-08)
4. Compute derived fields: `hour_of_day`, `day_of_week`, `month`
5. Set `is_high_priority_corridor = True` for the 10 named corridors (Mysore Road, Bellary Road 1, Bellary Road 2, Tumkur Road, Hosur Road, ORR North 1, ORR North 2, ORR East 1, ORR East 2, Magadi Road, Old Madras Road, Bannerghatta Road, West of Chord Road, CBD 2, ORR West 1, ORR West 2)
6. Set `is_non_corridor = True` where `corridor == 'Non-corridor'`
7. Save to `data/processed/events_clean.csv`
8. Save LCV subset to `data/processed/lcv_incidents.csv`

**Output:** `data/processed/events_clean.csv`

---

### Step 2 — `02_feature_engineer.py`

**Input:** `data/processed/events_clean.csv`

**Operations:**
1. Load encoders for categorical columns: `corridor`, `event_cause`, `vehicle_type`, `police_station`, `zone`
2. Fit `LabelEncoder` on each — save all encoders to `ml/artifacts/encoders.pkl`
3. Build feature matrix with columns:

```
corridor_encoded, event_cause_encoded, vehicle_type_encoded,
hour_of_day, day_of_week, month,
is_high_priority_corridor, is_non_corridor,
has_vehicle_type (binary),
has_zone (binary),
hour_sin, hour_cos  (cyclical encoding of hour_of_day)
```

4. Build target vectors:
   - `y_closure`: `requires_road_closure` as 0/1
   - `y_priority`: `priority == 'High'` as 0/1
   - `y_duration`: `duration_mins` (for records where 0 < duration < 5000)

5. Save to `data/processed/feature_matrix.csv`

**Output:** `data/processed/feature_matrix.csv`, `ml/artifacts/encoders.pkl`

---

### Step 3 — `03_train_closure.py` (Model 1)

**Input:** `data/processed/feature_matrix.csv`

**Algorithm:** XGBoost classifier  
**Class weight:** `scale_pos_weight = (total_negative / total_positive)` to handle 91.7%/8.3% imbalance  
**Train/test split:** 80/20 stratified on `y_closure`

**Hyperparameters (baseline, tune if time permits):**

```
n_estimators: 300
max_depth: 6
learning_rate: 0.05
subsample: 0.8
colsample_bytree: 0.8
eval_metric: auc
```

**Evaluation metrics to compute and print:**

- AUC-ROC (primary)
- Precision, Recall, F1 on closure-positive class
- Confusion matrix

**Threshold selection:** Use 0.35 (lower than default 0.5 to improve recall given high class imbalance — log the precision/recall tradeoff at this threshold)

**Output:** `ml/artifacts/closure_model.pkl`

---

### Step 4 — `04_train_priority.py` (Model 3)

**Input:** `data/processed/feature_matrix.csv`

**Algorithm:** Random Forest classifier  
**Train/test split:** 80/20 stratified on `y_priority`

**Hyperparameters:**

```
n_estimators: 200
max_depth: 10
min_samples_leaf: 5
class_weight: balanced
```

**Evaluation metrics:**

- Overall accuracy
- Non-corridor subset accuracy (reported separately — filter test set to `is_non_corridor == True`) Non-corridor subset accuracy
(reported separately because the current operational system
defaults many Non-corridor incidents to Low priority.

GridSense specifically evaluates whether severe
Non-corridor incidents can be identified correctly.)
- Feature importance (log top 10)

**Output:** `ml/artifacts/priority_model.pkl`

---

### Step 5 — `05_train_duration.py`

**No ML model — pure lookup table.**

**Input:** `data/processed/events_clean.csv`

**Operations:**
1. Filter to records where `0 < duration_mins < 5000`
2. Group by `event_cause`, compute `median`, `p25`, `p75`, `count`
3. Save as JSON

**Output:** `ml/artifacts/duration_lookup.json`

Format:
```json
{
  "pot_holes": { "median": 1306.4, "p25": 420.1, "p75": 2810.3, "count": 312 },
  "construction": { "median": 412.3, "p25": 180.0, "p75": 890.5, "count": 198 },
  "vehicle_breakdown": { "median": 40.7, "p25": 18.2, "p75": 93.6, "count": 2841 }
}
```

---

### Step 6 — `06_train_forecast.py` (Model 2)

**Algorithm:** Facebook Prophet  
**Run per junction:** Only for junctions with >= 15 total incidents (covers top ~30 junctions)

**Operations per junction:**
1. Filter incidents to that junction
2. Aggregate to hourly counts: `ds = hour bucket`, `y = incident count`
3. Fit Prophet with:
   - `daily_seasonality: True`
   - `weekly_seasonality: True`
   - `yearly_seasonality: False` (only 150 days of data)
4. Generate 72-hour forecast
5. Compute MAE on held-out last 14 days
6. Save model

**Output per junction:** `ml/artifacts/prophet_models/{JunctionName}.pkl`  
**Output global:** `ml/artifacts/corridor_risk_index.json`, `ml/artifacts/station_map.json`, `ml/artifacts/station_concurrency.json`

---

### Step 7 — `07_export_artifacts.py`

**Operations:**
1. Build `corridor_risk_index.json` from grouped aggregations
2. Build `station_map.json` (corridor → top 3 stations with incident counts)
3. Build `station_concurrency.json` (station × hour × dow → avg_concurrent, max_concurrent)
4. Verify all artifact files exist and are loadable
5. Print model file sizes and a readiness summary

**Output:** All files in `ml/artifacts/` confirmed present

---

## 5. Feature Engineering Pipeline

All feature engineering is encapsulated in `ml/features/`. These modules are imported by both the training pipeline and the FastAPI prediction service.

---

### `encoders.py`

Provides `load_encoders()` and `encode_input()`.

```
load_encoders() → dict of LabelEncoder objects (loaded from encoders.pkl)
encode_input(corridor, event_cause, vehicle_type) → dict of encoded integer values
encode_input handles unseen labels by mapping to -1 (unknown category)
```

---

### `time_features.py`

Provides `extract_time_features(hour, dow)`.

```
hour_sin = sin(2π × hour / 24)
hour_cos = cos(2π × hour / 24)
```

Cyclical encoding ensures hour 23 and hour 0 are treated as adjacent by the model.

---

### `corridor_features.py`

Provides `get_corridor_flags(corridor)`.

```
HIGH_PRIORITY_CORRIDORS = set of 15 named corridors
is_high_priority_corridor = corridor in HIGH_PRIORITY_CORRIDORS
is_non_corridor = corridor == 'Non-corridor' or corridor is None
```

---

### `historical_features.py`

Provides:

```
get_station_recommendation(corridor) → primary and secondary station names
get_station_concurrency(station, hour, dow) → avg_concurrent, max_concurrent
get_corridor_risk(corridor) → composite_risk_score from pre-computed index
```

All these functions load from the JSON artifacts in `ml/artifacts/`. They do not query the database at inference time. This keeps prediction latency under 50ms.

---

### Full Feature Vector (at inference time)

```python
features = {
    # Categorical (encoded)
    'corridor_encoded': int,
    'event_cause_encoded': int,
    'vehicle_type_encoded': int,

    # Time
    'hour_of_day': int,          # raw
    'day_of_week': int,          # 0=Mon
    'month': int,
    'hour_sin': float,
    'hour_cos': float,

    # Corridor flags
    'is_high_priority_corridor': int,    # 0 or 1
    'is_non_corridor': int,              # 0 or 1

    # Missingness flags
    'has_vehicle_type': int,     # 1 if vehicle_type provided
    'has_zone': int              # always 0 at inference (zone not user-provided)
}
```

Total features: 13  
Both `closure_model` and `priority_model` use this identical feature vector.

---

## 6. Exact Model Inputs and Outputs

### Model 1 — Closure / Escalation Predictor

| | Detail |
|---|---|
| Algorithm | XGBoost classifier |
| Input shape | (N, 13) |
| Input features | Full 13-feature vector above |
| Output | `closure_probability` ∈ [0.0, 1.0] |
| Threshold | 0.35 → `closure_flag` boolean |
| Training target | `requires_road_closure` (0/1) |
| Training records | ~8,173 (after staleness filter) |
| Positive class rate | ~8.3% (676 closure events) |
| Expected AUC-ROC | 0.78–0.85 |
| Expected F1 (positive class) | 0.55–0.65 |
| Serialisation | `joblib.dump` → `closure_model.pkl` |

---

### Model 2 — Junction Incident Volume Forecast (Prophet)

| | Detail |
|---|---|
| Algorithm | Facebook Prophet |
| One model per | Top junction (>= 15 incidents) |
| Input | Historical hourly incident count time series |
| Output | `yhat`, `yhat_lower`, `yhat_upper` per hour for next 72 hours |
| Target variable | Incident count per hour at junction level |
| Training records | Variable per junction (MekhriCircle: ~64 events over 150 days) |
| Seasonality | Daily + weekly (no yearly — insufficient data) |
| Expected MAE | 1–3 incidents per hour on busiest junctions |
| Serialisation | `joblib.dump` → `prophet_models/{JunctionName}.pkl` |

---

### Model 3 — Priority Classifier with Disagreement Flag

| | Detail |
|---|---|
| Algorithm | Random Forest classifier |
| Input shape | (N, 13) |
| Input features | Full 13-feature vector above |
| Output | `priority_probability` ∈ [0.0, 1.0], `predicted_priority` (High/Low) |
| Derived output | `disagreement_flag` = `is_non_corridor AND predicted_priority == High` |
| Training target | `priority == 'High'` (0/1) |
| Training records | ~8,173 |
| Expected overall accuracy | 85–92% |
| Expected Non-corridor accuracy | 65–72% (reported separately) |
| Serialisation | `joblib.dump` → `priority_model.pkl` |

---

### Duration Estimator (Lookup, not ML)

| | Detail |
|---|---|
| Type | Static lookup table |
| Input | `event_cause` string |
| Output | `median_duration_mins`, `p25`, `p75` |
| Source | Pre-computed from 3,126 valid-duration records |
| Serialisation | JSON file → `duration_lookup.json` |

---

### Deployment Engine (Rule-based, not ML)

| | Detail |
|---|---|
| Type | Deterministic rules on model outputs |
| Inputs | `corridor`, `hour_of_day`, `day_of_week`, `closure_probability`, `predicted_priority`, `predicted_duration_mins` |
| Outputs | `recommended_station`, `secondary_station`, `recommended_officer_count`, `escalation_tier`, `suggested_junctions`, `officer_count_rationale` |
| Station logic | `station_map[corridor][rank=1]` |
| Officer count | `ceil(station_concurrency[station][hour][dow].avg_concurrent + adjustment)` |
| Adjustment | +1 for High priority; +2 if closure_probability > 0.35 |

---

## 7. React Dashboard Component Hierarchy

```
App
└── AppShell
    ├── TopBar
    │   ├── GridSenseLogo
    │   └── SummaryStatBar (total incidents, corrected active, data range)
    │
    ├── Sidebar
    │   ├── NavItem (Map)
    │   ├── NavItem (Triage)
    │   ├── NavItem (Forecast)
    │   ├── NavItem (Deploy)
    │   └── NavItem (Flipkart)
    │
    └── PageRouter
        │
        ├── [Screen A] Map.jsx
        │   └── CommandCenterMap
        │       ├── LeafletMap (base tile layer — OpenStreetMap)
        │       ├── IncidentLayer
        │       │   └── CircleMarker × N (one per incident, coloured by priority)
        │       ├── JunctionMarkerLayer
        │       │   └── JunctionMarker × 20 (top junctions, sized by count)
        │       ├── MapFilterPanel
        │       │   ├── CorridorFilter (dropdown)
        │       │   ├── CauseFilter (dropdown)
        │       │   ├── PriorityFilter (radio)
        │       │   └── EventTypeFilter (radio)
        │       └── CorridorRiskSidebar
        │           └── CorridorRiskRow × 15 (mini leaderboard)
        │
        ├── [Screen C+D] Triage.jsx
        │   └── TriageScreen
        │       ├── TriageForm
        │       │   ├── CorridorSelect
        │       │   ├── CauseSelect
        │       │   ├── VehicleTypeSelect
        │       │   ├── HourSlider
        │       │   ├── DayOfWeekSelect
        │       │   └── SubmitButton
        │       └── PredictionResultCard (shown after submission)
        │           ├── ClosureProbabilityGauge
        │           ├── PriorityChip (High/Low + probability)
        │           ├── DisagreementFlag (conditional — only when flag fires)
        │           │   └── DisagreementExplanationBox
        │           ├── DurationEstimate (median + p25/p75 bar)
        │           └── QuickDeployButton → navigates to Deploy with pre-filled values
        │
        ├── [Screen E] Forecast.jsx
        │   └── ForecastScreen
        │       ├── JunctionSelector (dropdown of top 20 junctions)
        │       ├── JunctionForecastChart (Recharts LineChart — 72h forecast)
        │       │   ├── ForecastLine (yhat)
        │       │   ├── ConfidenceBand (yhat_lower / yhat_upper area)
        │       │   └── PeakHourHighlights (shaded rectangles for 4–6am, 7–10pm)
        │       └── PeakSummaryCard
        │           ├── EveningPeakBadge
        │           └── MorningPeakBadge
        │
        ├── [Screen F] Deployment.jsx
        │   └── DeploymentScreen
        │       ├── DeploymentForm (pre-fills from Triage if navigated via QuickDeployButton)
        │       │   ├── CorridorSelect
        │       │   ├── CauseSelect
        │       │   ├── HourSlider
        │       │   ├── DayOfWeekSelect
        │       │   ├── ClosureProbInput (manual override)
        │       │   └── SubmitButton
        │       └── DeploymentResultCard
        │           ├── EscalationTierBadge (Critical/Elevated/Routine)
        │           ├── StationCard (primary station, officer count, rationale)
        │           ├── SecondaryStationCard
        │           ├── SuggestedJunctionsList
        │           └── DeploymentDurationEstimate
        │
        └── [Screen G] Flipkart.jsx
            └── FlipkartPanel
                ├── LCVSummaryStats (4 stat cards)
                │   ├── StatCard (678 total LCV incidents)
                │   ├── StatCard (70.4% High priority)
                │   ├── StatCard (2.7% closure rate)
                │   └── StatCard (Riskiest hour: 8pm)
                ├── LCVByCorridorChart (Recharts HorizontalBarChart)
                │   └── CorridorRiskTag (avoid / caution / prefer)
                ├── LCVByHourChart (Recharts BarChart — 24h profile)
                └── FlipkartInsightBox (hardcoded key finding text)
```

---

### State Management (Zustand stores)

**`useIncidentStore`**

```
state: { incidents[], summaryStats, corridorRisk[], junctions[], loading, error }
actions: fetchIncidents(filters), fetchSummary(), fetchJunctions(), fetchCorridorRisk()
```

**`useTriageStore`**

```
state: { formValues, predictionResult, deploymentResult, loading, error }
actions: submitTriage(form), submitDeploy(form), clearResults()
```

**`useMapStore`**

```
state: { selectedCorridor, selectedCause, selectedPriority, selectedEventType, mapBounds }
actions: setFilter(key, value), resetFilters(), setMapBounds(bounds)
```

---

## 8. Week-by-Week Development Plan

### Week 1: Data, Models, and Backend Foundation

**Days 1–2: Data pipeline (ML lead + data engineer)**

- Set up project repo, branch strategy, and environment
- Run `01_ingest.py` — clean CSV, apply staleness filter, compute derived fields
- Run `02_feature_engineer.py` — build feature matrix, fit and save encoders
- Verify: `data/processed/feature_matrix.csv` has correct shape and no nulls in key columns
- Run `07_export_artifacts.py` partial — build `duration_lookup.json`, `station_map.json`, `station_concurrency.json`, `corridor_risk_index.json` from raw aggregations

Milestone: All non-ML artifacts ready by end of Day 2.

**Days 3–4: Model training**

- Run `03_train_closure.py` — train, evaluate, save closure model. Log AUC-ROC and F1.
- Run `04_train_priority.py` — train, evaluate, save priority model. Log overall and Non-corridor accuracy separately.
- Run `05_train_duration.py` — build duration lookup
- Run `06_train_forecast.py` — train Prophet for top 10 junctions (top 20 if time permits)
- Verify: all artifacts in `ml/artifacts/` loadable with expected output shapes

Milestone: All model artifacts ready by end of Day 4.

**Day 5: Backend skeleton**

- FastAPI app scaffold — `main.py`, `config.py`, `db/connection.py`
- Seed database: run `scripts/seed_db.py` to load `events_clean.csv` into PostgreSQL
- Implement `GET /incidents` and `GET /incidents/summary` — no ML required, pure DB queries
- Implement `GET /corridors/risk` — load from pre-computed JSON artifact
- Basic health check endpoint: `GET /health`
- Verify: frontend can hit these endpoints and receive correct JSON

Milestone: Two read endpoints working with real data by end of Day 5.

---

### Week 2: Core API and Dashboard Skeleton

**Days 6–7: Prediction and deployment endpoints**

- Implement prediction service: load models at startup, `encode_input()`, `predict()`
- Implement `POST /predict/triage` — full inference pipeline, disagreement flag logic
- Implement `POST /deploy/recommend` — station lookup, officer count formula, escalation tier
- Implement `GET /forecast/junction/{junction}` — load Prophet artifact, generate forecast
- Write response models in `backend/models/` for all endpoints

Milestone: All five core API endpoints functioning with real model outputs.

**Days 8–9: Frontend scaffold and map**

- React + Vite scaffold, Tailwind config, Zustand stores
- `AppShell`, `Sidebar`, `TopBar` layout components
- `CommandCenterMap` with Leaflet — plot all 8,173 incidents as circle markers
- `MapFilterPanel` connected to `useMapStore` — live filtering by corridor and cause
- `CorridorRiskSidebar` — mini leaderboard from `/corridors/risk`

Milestone: Map screen live with real incident data from the API.

**Day 10: Triage screen**

- `TriageForm` — all dropdowns populated from static constants
- `PredictionResultCard` — renders closure probability, priority, duration
- `DisagreementFlag` — renders only when flag fires, with explanation box
- Wire to `POST /predict/triage` via `useTriageStore`

Milestone: Live triage working end-to-end. A judge can type a scenario and get a real prediction.

---

### Week 3: Remaining Screens, Polish, and Deployment

**Days 11–12: Forecast and deployment screens**

- `JunctionForecastChart` — Recharts LineChart with confidence band and peak highlights
- `ForecastScreen` with junction selector
- `DeploymentResultCard` — escalation badge, station card, officer count with rationale
- `QuickDeployButton` on Triage screen pre-filling Deployment form
- Wire all screens to API

**Days 13–14: Flipkart panel and final polish**

- `FlipkartPanel` — all four stat cards, two Recharts charts, insight box
- Wire to `GET /lcv/risk`
- `PlannedEventLookup` — basic UI + `POST /predict/planned-event-lookup`
- Cross-browser testing, loading states, error boundaries on all screens
- Mobile-responsive check for Sidebar collapse

**Day 15: Deploy and demo prep**

- Deploy backend to Render.com or Railway (free tier)
- Deploy frontend to Vercel
- Run `scripts/health_check.py` against production
- Test full demo flow on live URL
- Prepare model metrics slide (AUC-ROC, Non-corridor accuracy, Prophet MAE)
- Two full demo rehearsals

---

## 9. Team Role Allocation

### Team of 4

---

#### Member 1 — ML Lead

**Primary ownership:** Everything in `ml/`

**Week 1:**
- Drives `01_ingest.py` through `07_export_artifacts.py`
- Trains all models, evaluates, documents metrics
- Writes `ml/evaluation/` scripts

**Week 2:**
- Writes `prediction_service.py` in backend (model loading, inference)
- Implements `POST /predict/triage` logic
- Supports Member 2 on `POST /deploy/recommend` formula

**Week 3:**
- Trains Prophet for remaining junctions
- Prepares model metrics slides for demo
- Answers model-related Q&A in rehearsals

**Deliverables:** All model artifacts, evaluation reports, prediction service

---

#### Member 2 — Backend Engineer

**Primary ownership:** Everything in `backend/`

**Week 1:**
- Sets up FastAPI scaffold, database connection, SQLAlchemy schema
- Runs `scripts/seed_db.py`, verifies data integrity
- Implements `GET /incidents`, `GET /incidents/summary`, `GET /corridors/risk`

**Week 2:**
- Implements `POST /deploy/recommend`, `GET /forecast/junction/{junction}`, `GET /lcv/risk`
- Writes all Pydantic response models
- Implements `GET /incidents/junctions`

**Week 3:**
- Implements `POST /predict/planned-event-lookup`
- Handles deployment to Render/Railway
- API documentation and Swagger verification

**Deliverables:** All API endpoints functional, database seeded, production deployment

---

#### Member 3 — Frontend Lead

**Primary ownership:** Everything in `frontend/`

**Week 1:**
- Sets up React + Vite + Tailwind + Zustand scaffold
- Builds `AppShell`, `Sidebar`, `TopBar`
- Builds `CommandCenterMap` with Leaflet (static data first, API second)

**Week 2:**
- Builds `TriageScreen`, `TriageForm`, `PredictionResultCard`, `DisagreementFlag`
- Wires map filters to `useMapStore`
- Builds `FlipkartPanel` structure (static first)

**Week 3:**
- Builds `ForecastScreen`, `DeploymentScreen`
- Wires all screens to live API
- Handles loading states, error boundaries, responsive layout

**Deliverables:** All five dashboard screens live and wired to API

---

#### Member 4 — Data Engineer + QA + Demo

**Primary ownership:** `data/`, `scripts/`, demo rehearsals, presentation

**Week 1:**
- Supports Member 1 on data pipeline — validates processed CSV, checks for data quality
- Builds `data/reference/corridor_junctions.json` and `data/reference/corridor_boundaries.geojson`
- Runs quality checks on all artifacts (null rates, value distributions)

**Week 2:**
- Builds `CorridorRiskSidebar` and `CorridorRiskRow` components
- Builds `LCVRiskChart` and `LCVByHourChart` Recharts components
- Writes `api/` client functions for all endpoints

**Week 3:**
- Owns demo flow script and rehearsal coordination
- Tests full E2E flow on production URL
- Prepares the architecture slide and the model metrics slide
- Manages judge Q&A preparation (rehearses all 10 critical questions from the document)

**Deliverables:** Clean data pipeline, Recharts chart components, demo script, Q&A preparation

---

### Cross-cutting responsibilities

| Responsibility | Owner |
|---|---|
| GitHub repo setup and branching | Member 2 |
| Environment variables and secrets | Member 2 |
| Docker compose (local dev) | Member 2 |
| Demo URL (Vercel + Render) | Member 2 + Member 4 |
| Presentation slide deck | Member 4 |
| Model metrics documentation | Member 1 |
| Demo script and rehearsal | Member 4 (all members attend) |

---

## 10. MVP Version — 48 Hours

This is the version buildable in a hackathon emergency scenario or the first working end-to-end cut.

### What to build in 48 hours

**Hour 0–8: Data and models**

1. Run `01_ingest.py` — clean CSV (2 hours)
2. Run `02_feature_engineer.py` — feature matrix and encoders (1 hour)
3. Run `03_train_closure.py` — closure model only (1 hour)
4. Run `04_train_priority.py` — priority model (1 hour)
5. Build all JSON lookup artifacts manually (station_map, corridor_risk, duration_lookup) (2 hours)
6. Seed SQLite database (1 hour)

**Hour 8–20: Backend**

1. FastAPI app with three endpoints only:
   - `GET /incidents` — returns all incidents as JSON from SQLite
   - `GET /corridors/risk` — returns pre-computed corridor risk JSON
   - `POST /predict/triage` — runs both models and returns prediction
2. No forecast endpoint in MVP (Prophet takes time to train)
3. No deployment endpoint in MVP (rule-based but needs station_concurrency lookup)

**Hour 20–40: Frontend**

1. Single-page React app with two functional screens:
   - Screen A (Map): Leaflet map with all incidents plotted, coloured by priority, corridor filter
   - Screen C+D (Triage): Form + prediction result card with disagreement flag
2. No Recharts, no forecast screen, no deployment screen, no Flipkart panel in MVP
3. Hardcode the API base URL to localhost

**Hour 40–48: Integration and demo prep**

1. Connect frontend to backend, verify end-to-end triage works
2. Prepare the two-minute demo: map → triage → disagreement flag moment
3. Deploy to any public URL (ngrok is acceptable for MVP demo)

### MVP scope summary

| Feature | In MVP |
|---|---|
| Incident map with filter | Yes |
| Corridor risk leaderboard (sidebar) | Yes — as static list |
| Live triage (Models 1 + 3) | Yes |
| Disagreement flag | Yes |
| Duration estimate | Yes — from JSON lookup |
| Junction forecast (Prophet) | No |
| Deployment recommender | No |
| Flipkart panel | No |
| Planned event lookup | No |

---

## 11. Extended Version — Final Submission

### What the extended version adds on top of MVP

| Feature | Priority | Estimated effort |
|---|---|---|
| Junction-resolution map markers (top 20) | High | 4 hours |
| Corridor risk sidebar wired to live API | High | 2 hours |
| Prophet forecast per top 10 junctions | High | 6 hours training + 4 hours frontend |
| Forecast screen with Recharts | High | 8 hours |
| Deployment recommender API + screen | High | 6 hours |
| LCV / Flipkart panel (all charts) | High | 6 hours |
| Planned event historical lookup | Medium | 4 hours |
| `GET /incidents/junctions` endpoint | Medium | 2 hours |
| Loading states and error boundaries | Medium | 4 hours |
| Responsive Sidebar collapse | Low | 2 hours |
| Production deployment (Vercel + Render) | Required | 3 hours |
| Demo rehearsals × 2 | Required | 4 hours |

**Total extended effort beyond MVP:** ~55 hours (fits in Week 2 + 3 if MVP is done in Week 1)

---

## 12. Development Order

### What to build first

These are blocking dependencies — nothing else can start until these exist:

1. `01_ingest.py` — all models need the clean dataset
2. `02_feature_engineer.py` + encoders — all models need the feature matrix
3. `03_train_closure.py` — the flagship model, needed for triage endpoint
4. `04_train_priority.py` — needed for triage endpoint
5. All JSON lookup artifacts (`duration_lookup`, `station_map`, `corridor_risk_index`, `station_concurrency`) — needed by backend services
6. `backend/db/schema.py` + `scripts/seed_db.py` — all API endpoints need the database
7. `POST /predict/triage` backend endpoint — the triage screen cannot be built without it
8. `CommandCenterMap` frontend component — the map is the first visual proof that the data is real

---

### What to build second

These can start in parallel once the blocking dependencies above exist:

- `GET /corridors/risk` endpoint (parallel with triage endpoint)
- `TriageForm` + `PredictionResultCard` frontend (parallel with backend model work)
- `06_train_forecast.py` (can train while backend and frontend are being built)
- `CorridorRiskSidebar` frontend component (depends only on `/corridors/risk`)
- `POST /deploy/recommend` endpoint (depends on `station_concurrency.json` artifact)
- `FlipkartPanel` static structure (can be built with hardcoded data, wired to API later)

---

### What can be postponed

These have no blocking dependencies on other features and can be added in Week 3:

- Prophet forecast screen (Frontend `ForecastScreen` + `JunctionForecastChart`)
- `GET /forecast/junction/{junction}` endpoint
- Planned event historical lookup (both endpoint and frontend)
- `GET /incidents/junctions` endpoint and `JunctionMarkerLayer` frontend
- Loading state animations and skeleton screens
- `triage_log` table and logging
- Mobile-responsive Sidebar collapse
- All error boundary components (build with console.error logging first)
- Any README, architecture diagram in repo

---

### Dependency graph summary

```
Raw CSV
  └── 01_ingest.py
        └── 02_feature_engineer.py (encoders.pkl, feature_matrix.csv)
              ├── 03_train_closure.py  ──────────────────────────┐
              ├── 04_train_priority.py ──────────────────────────┤
              └── 05_train_duration.py (duration_lookup.json)   │
                                                                  │
07_export_artifacts.py (station_map, corridor_risk, concurrency) │
        │                                                          │
        └── backend/db seeding                                    │
              └── GET /incidents ──────── CommandCenterMap        │
              └── GET /corridors/risk ─── CorridorRiskSidebar    │
                                                                  ▼
                                          POST /predict/triage ← closure_model.pkl
                                                │               ← priority_model.pkl
                                                ▼               ← duration_lookup.json
                                          TriageScreen
                                          PredictionResultCard
                                          DisagreementFlag
                                                │
                                                ▼
                                          POST /deploy/recommend ← station_map.json
                                                │                 ← concurrency.json
                                                ▼
                                          DeploymentScreen

06_train_forecast.py ← feature_matrix.csv
        └── prophet_models/*.pkl
              └── GET /forecast/junction
                    └── ForecastScreen

GET /lcv/risk ← lcv_incidents.csv (pre-computed)
        └── FlipkartPanel
```

---

*End of GridSense Implementation Plan*

---

> Document version: 1.0  
> Last updated: June 2026  
> For internal team use — Gridlock Hackathon 2.0 submission
