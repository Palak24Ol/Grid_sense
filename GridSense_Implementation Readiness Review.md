# GridSense — Implementation Readiness Review

> Scope: Engineering execution and development workflow only  
> Prerequisite: Implementation Plan v1.0 (GridSense_Implementation_Plan.md)  
> This document does NOT modify the ML architecture, schema design, features, or dashboard screens.

---

## Table of Contents

1. [Database Architecture Review](#1-database-architecture-review)
   - 1.1 [Current State](#11-current-state)
   - 1.2 [Pros and Cons of PostgreSQL-Only](#12-pros-and-cons-of-postgresql-only)
   - 1.3 [Pros and Cons of Keeping SQLite](#13-pros-and-cons-of-keeping-sqlite)
   - 1.4 [Migration, Deployment, Schema, and Debugging Risks](#14-migration-deployment-schema-and-debugging-risks)
   - 1.5 [PostgreSQL from Day One — Analysis](#15-postgresql-from-day-one--analysis)
   - 1.6 [PostgreSQL-Specific Features That Benefit GridSense](#16-postgresql-specific-features-that-benefit-gridsense)
   - 1.7 [Schema Considerations if PostgreSQL is the Only Database](#17-schema-considerations-if-postgresql-is-the-only-database)
   - 1.8 [Final Database Recommendation](#18-final-database-recommendation)

2. [Parallel Development Optimization](#2-parallel-development-optimization)
   - 2.1 [The Core Problem with the Current Timeline](#21-the-core-problem-with-the-current-timeline)
   - 2.2 [What Can Be Built Before ML Models Exist](#22-what-can-be-built-before-ml-models-exist)
   - 2.3 [What Requires Trained Models](#23-what-requires-trained-models)
   - 2.4 [What Requires Real API Integration](#24-what-requires-real-api-integration)
   - 2.5 [Mock JSON Responses for Every Dashboard Screen](#25-mock-json-responses-for-every-dashboard-screen)
   - 2.6 [Updated Task Allocation](#26-updated-task-allocation)
   - 2.7 [Critical Path Analysis](#27-critical-path-analysis)
   - 2.8 [Development Bottlenecks and How to Avoid Them](#28-development-bottlenecks-and-how-to-avoid-them)
   - 2.9 [Recommended Build Order for Maximum Velocity](#29-recommended-build-order-for-maximum-velocity)

---

## 1. Database Architecture Review

### 1.1 Current State

The implementation plan specifies:
- **Production**: PostgreSQL
- **Local development**: SQLite

The current `docker-compose.yml` reference implies PostgreSQL is the container service. SQLite is mentioned as a local fallback, with `scripts/seed_db.py` described as loading data "into SQLite/PG". This dual-database posture is the subject of this review.

---

### 1.2 Pros and Cons of PostgreSQL-Only

#### Pros

**Environment parity eliminates an entire class of bugs.**  
SQLite and PostgreSQL differ in how they handle types, NULL semantics, boolean coercion, datetime storage, and string case sensitivity. Code that works perfectly against SQLite can fail silently or produce wrong query results against PostgreSQL. A GridSense-specific example: the `is_stale_active` boolean column. SQLite stores booleans as integers (0/1) and will accept string comparisons like `WHERE is_stale_active = 'true'` without error. PostgreSQL will raise a type mismatch. If Member 2 develops the `/incidents` filter against SQLite and Member 3 is consuming mock data, neither catches this until integration day.

**One connection string, one ORM configuration, one mental model.**  
With SQLAlchemy as the ORM, the connection string changes between SQLite (`sqlite:///./gridsense.db`) and PostgreSQL (`postgresql://user:pass@host/db`). This means `connection.py` must either branch on environment or maintain two configurations. PostgreSQL-only removes that branch entirely.

**PostGIS and indexing are available from the first line of code.**  
The `incidents` table has 8,173 rows with latitude and longitude. The `/incidents` endpoint supports bounding box queries (implied by the `idx_incidents_geo` index). The geospatial index `ON (latitude, longitude)` works in both databases for simple range queries, but if any spatial distance filtering is ever needed (e.g., "find junctions within 2km of this coordinate"), only PostgreSQL with PostGIS handles that correctly and efficiently. Using PostgreSQL from day one means that optimization is available without a migration.

**The `triage_log` table benefits immediately from PostgreSQL features.**  
The `triage_log` table will accumulate runtime writes. PostgreSQL's MVCC (Multi-Version Concurrency Control) handles concurrent writes from multiple API workers without the write lock contention SQLite imposes. During a live demo with a judge typing scenarios rapidly, concurrent triage requests could trigger write lock timeouts under SQLite.

**Render.com and Railway both offer managed PostgreSQL as a free tier.**  
The deployment target is already Render or Railway. Both services provision a PostgreSQL instance in the same environment as the backend container. There is no setup overhead advantage to SQLite in this context — PostgreSQL is a one-click addition on both platforms, and the connection string arrives as an environment variable automatically.

**Indexing behavior is deterministic and inspectable.**  
PostgreSQL's `EXPLAIN ANALYZE` lets you verify that the `idx_incidents_corridor` and `idx_incidents_start_datetime` indexes are actually being used. SQLite's query planner is significantly simpler and its index usage less predictable at this data volume (8,173 rows is near the threshold where SQLite's planner sometimes ignores indexes).

#### Cons

**PostgreSQL requires a running server process locally.**  
Developers need Docker or a native PostgreSQL installation. This adds 10–15 minutes of setup on a fresh machine and creates a dependency that SQLite eliminates. For a team of 4 where not everyone may have Docker familiarity, this is a real friction point on Day 1.

**No offline-capable fallback.**  
If a developer is working somewhere without their PostgreSQL container (on a train, in a conference room with no internet for cloud DB), they cannot run the backend at all. SQLite allowed zero-dependency local development.

**Slightly more setup in CI if tests are added later.**  
Test suites that hit the database need a PostgreSQL instance in the CI pipeline. For a 3-week hackathon with no formal test suite, this is not a practical concern.

---

### 1.3 Pros and Cons of Keeping SQLite

#### Pros

**Zero-dependency local development on Day 1.**  
`sqlite:///./gridsense.db` works with no installed services. A developer can clone the repo, run `pip install -r requirements.txt`, run `seed_db.py`, and have a working backend in under 5 minutes with no Docker required.

**Simpler `seed_db.py`.**  
SQLite accepts the processed CSV via pandas `to_sql()` with no connection string, no credentials, no user/role setup. This shaves roughly 30 minutes off the first-time setup for any team member.

#### Cons

**It introduces a class of bugs that will not appear until production.**  
This is the decisive argument against it. The specific risks for GridSense:

1. `TIMESTAMPTZ` (timezone-aware timestamp) is a PostgreSQL type. SQLite stores all datetimes as text or real numbers with no timezone awareness. SQLAlchemy's `TIMESTAMPTZ` column type silently degrades to `TEXT` in SQLite. The staleness filter logic in `staleness_filter.py` compares `modified_datetime` to a cutoff timestamp. Under SQLite, this comparison is string-based, not date-based, and will produce correct results for ISO 8601 strings only if the formatting is consistent — a fragile assumption when the raw ASTRAM CSV has mixed UTC offset formats.

2. `BOOLEAN` coercion differs. SQLite accepts `1`, `0`, `'true'`, `'false'`, and `True`/`False` interchangeably. PostgreSQL requires explicit boolean values. Queries that filter on `is_stale_active = True` may behave differently.

3. Case sensitivity in string comparisons differs. `WHERE corridor = 'mysore road'` returns results in SQLite (case-insensitive by default) and returns nothing in PostgreSQL. The corridor filter in `/incidents` is a string equality match. If any frontend component sends a lowercase corridor name, the query silently returns empty results in PostgreSQL but works in SQLite.

**The migration step between SQLite and PostgreSQL is invisible until it breaks.**  
When `seed_db.py` runs against PostgreSQL on Render, the `TIMESTAMPTZ` columns that were `TEXT` in SQLite will need proper casting. This is a quiet failure — `seed_db.py` will appear to succeed, but timestamp comparison queries will return wrong results.

**SQLite does not support concurrent writers.**  
The `triage_log` table is written on every `/predict/triage` call. Under SQLite with multiple concurrent API workers (FastAPI runs async by default), a second write while a first is in progress will raise `OperationalError: database is locked`. This will manifest during the demo if predictions are submitted in quick succession.

**Maintaining two connection configurations adds permanent cognitive overhead.**  
Every database interaction must be mentally verified against both engines. This is a tax on every developer for the full 3 weeks.

---

### 1.4 Migration, Deployment, Schema, and Debugging Risks

#### Migration risk: HIGH

There is no migration framework (Alembic) in the current plan. The schema is created once via `schema.py` and seeded via `seed_db.py`. If a developer builds and tests against SQLite locally, then the deployment script runs `seed_db.py` against PostgreSQL for the first time, any SQLite-specific SQL that crept into the schema definition will fail. With Alembic absent, there is no rollback mechanism. The fix requires manual schema edits against a production database under time pressure — a high-risk situation during the hackathon's final submission window.

#### Deployment risk: MEDIUM-HIGH

Render.com provisions PostgreSQL automatically. The backend container receives a `DATABASE_URL` environment variable pointing to PostgreSQL. If `connection.py` has an `if DATABASE_URL contains sqlite` branch, that branch is dead code in production and will never be tested. If the branch is missing and the developer hardcoded a SQLite path for local dev, the production deployment fails silently or raises an unhandled connection error on startup.

#### Schema risk: MEDIUM

The `TIMESTAMPTZ` vs `TEXT` degradation described above is the primary schema risk. Secondary risk: the `SERIAL` primary key type for `station_concurrency` and `corridor_station_map` is PostgreSQL-specific. SQLAlchemy maps this to `INTEGER AUTOINCREMENT` in SQLite, which behaves slightly differently under concurrent inserts. Neither is a blocking risk for a hackathon, but both require mental tracking.

#### Debugging risk: HIGH

When a bug surfaces in production that does not reproduce locally, the first question is always "is this a database difference?" With two database engines in play, every debugging session carries this overhead. For a 3-week project with a 4-person team, this is a meaningful tax on debugging velocity.

---

### 1.5 PostgreSQL from Day One — Analysis

The objection to PostgreSQL from day one is developer setup friction. This is real but solvable in under 15 minutes using the `docker-compose.yml` already specified in the project structure:

```yaml
# docker-compose.yml — existing file in the project
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: gridsense
      POSTGRES_USER: gridsense
      POSTGRES_PASSWORD: gridsense
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  backend:
    build: ./backend
    depends_on:
      - db
    environment:
      DATABASE_URL: postgresql://gridsense:gridsense@db:5432/gridsense
    ports:
      - "8000:8000"

volumes:
  postgres_data:
```

With this in place, any developer with Docker installed runs `docker compose up -d` and has a PostgreSQL instance ready. The `DATABASE_URL` is injected identically in local and production environments. There is no branching in `connection.py`.

For the one team member who may not have Docker (Member 4, the data engineer and demo lead), a local PostgreSQL install via Homebrew (macOS) or `apt` (Linux) takes 5 minutes and connects on the default port. This is a one-time cost that eliminates a permanent debugging risk.

The alternative — accepting SQLite locally to save 15 minutes of setup — creates a category of bugs that can appear at any time during the 3-week sprint, can be invisible until integration day, and requires debugging effort that will far exceed the 15-minute setup saving.

---

### 1.6 PostgreSQL-Specific Features That Benefit GridSense

#### JSONB columns for `meta_data` and `description` fields

The `incidents` table includes a `description` field that contains Kannada text and an original `meta_data` field from the ASTRAM dataset. These are currently stored as `TEXT`. If any runtime querying of these fields is needed (e.g., the planned event lookup filtering on description content), PostgreSQL's `JSONB` type with GIN indexing makes that efficient.

For the current plan, `description` as `TEXT` is correct. However, the `meta_data` field from the raw dataset is often a JSON blob. Storing it as `JSONB` rather than `TEXT` allows queries like `WHERE meta_data->>'key' = 'value'` without string parsing in application code. This is a low-cost improvement at schema definition time.

**Recommendation:** Keep `description` as `TEXT`. Change `meta_data` from `TEXT` to `JSONB`. No query changes required — the field is never queried in the current plan, so this is purely a correctness improvement.

#### Partial indexes for common filter patterns

The `/incidents` endpoint has a constant filter: `exclude_stale=true` removes `is_stale_active = TRUE` records. This is applied on almost every request. A partial index in PostgreSQL covers this efficiently:

```sql
CREATE INDEX idx_incidents_non_stale_corridor
ON incidents (corridor)
WHERE is_stale_active = FALSE;
```

This index is smaller than a full `(corridor)` index because it only covers the ~7,436 non-stale records, and it is used automatically when the query includes `WHERE is_stale_active = FALSE AND corridor = $1`. SQLite has partial index support but the query planner does not use them as reliably.

**Recommendation:** Add this partial index to the `schema.py` definition alongside the existing indexes.

#### `gen_random_uuid()` for `triage_log` primary key

The `triage_log` table uses `UUID PRIMARY KEY DEFAULT gen_random_uuid()`. This is a PostgreSQL built-in function. SQLite does not have `gen_random_uuid()` — it would require a SQLAlchemy `server_default` that calls a Python-side UUID generator instead. PostgreSQL-only removes this divergence and lets the database generate UUIDs natively, which is both correct and slightly faster.

#### `TIMESTAMPTZ` stores timezone-aware datetimes correctly

The ASTRAM dataset timestamps include UTC offsets (`2024-03-07 17:01:48.111+00`). PostgreSQL's `TIMESTAMPTZ` stores these correctly and returns them in UTC regardless of the server timezone. SQLAlchemy's `TIMESTAMP(timezone=True)` column type maps to `TIMESTAMPTZ` in PostgreSQL and to `TEXT` in SQLite. All staleness filter comparisons, duration calculations, and forecast alignment depend on correct timezone handling. PostgreSQL-only guarantees this.

#### `EXPLAIN ANALYZE` for query verification

The `/incidents` endpoint with multiple filters (`corridor`, `event_cause`, `priority`, `exclude_stale`) generates complex `WHERE` clauses. PostgreSQL's `EXPLAIN ANALYZE` lets any team member verify in seconds whether the query planner is using the intended index. This is a debugging and performance verification tool with no SQLite equivalent.

---

### 1.7 Schema Considerations if PostgreSQL Becomes the Only Database

These are minor adjustments to `backend/db/schema.py` that remove any SQLite-compatibility compromises and take full advantage of PostgreSQL:

1. **Replace `String` with `Text` for `description` and `address` columns.** In SQLAlchemy, `String` maps to `VARCHAR` in PostgreSQL (requiring a length) and `TEXT` in SQLite (no length). Using `Text` explicitly maps to `TEXT` in PostgreSQL, which is the correct type for unbounded strings. No length constraint is needed or appropriate for these fields.

2. **Change `meta_data` column type from `String` / `Text` to `JSONB`.** Use SQLAlchemy's `postgresql.JSONB` type import: `from sqlalchemy.dialects.postgresql import JSONB`. The column definition becomes `meta_data = Column(JSONB, nullable=True)`. This requires no change to the seeding script — pandas handles JSON strings correctly when the target column is JSONB.

3. **Confirm all `DateTime` columns use `timezone=True`.** In SQLAlchemy, `Column(DateTime(timezone=True))` maps to `TIMESTAMPTZ` in PostgreSQL. Verify this is explicitly set for `start_datetime`, `end_datetime`, `closed_datetime`, `created_at` in `incidents`, and `created_at` in `triage_log`. If any column is `DateTime` without `timezone=True`, it maps to `TIMESTAMP WITHOUT TIME ZONE` in PostgreSQL, which will cause incorrect staleness filter results for records near daylight saving time boundaries.

4. **Add the partial index.** As described in section 1.6:
   ```python
   Index('idx_incidents_non_stale_corridor', 
         incidents_table.c.corridor, 
         postgresql_where=(incidents_table.c.is_stale_active == False))
   ```

5. **Remove any `check_same_thread=False` references from `connection.py`.** This is a SQLite-only parameter that prevents cross-thread connection errors. It has no PostgreSQL equivalent and will cause an error if accidentally passed to `create_engine()` with a PostgreSQL URL. Search `connection.py` for this parameter and remove it entirely when switching to PostgreSQL-only.

6. **Update `scripts/seed_db.py` to remove the dual-URL logic.** The current plan's `seed_db.py` loads data "into SQLite/PG." Remove the SQLite path entirely. The script should read `DATABASE_URL` from the environment and connect to PostgreSQL only. Add a guard: `assert 'postgresql' in os.environ['DATABASE_URL'], "seed_db.py requires PostgreSQL"`.

---

### 1.8 Final Database Recommendation

**Remove SQLite entirely. Use PostgreSQL from day one, locally and in production.**

The justification is not about performance or features. The ASTRAM dataset is 8,173 rows. Either database handles this trivially. The justification is purely about risk and debugging cost during a time-constrained sprint.

SQLite introduces four independent risk vectors — timezone handling, boolean coercion, string case sensitivity, and write lock contention — any one of which can consume hours of debugging time during a 3-week project. The bug that surfaces on integration day (when SQLite-tested code hits PostgreSQL for the first time) is the most expensive possible bug: it appears late, it is hard to reproduce locally without switching databases, and it may require schema or query changes that cascade across multiple files.

The setup cost of PostgreSQL locally is `docker compose up -d` plus 15 minutes on the first day. This is a one-time cost. The debugging cost of a SQLite-vs-PostgreSQL divergence during Week 2 integration is 2–4 hours minimum and potentially a full day if the root cause is not immediately obvious.

For a 21-day sprint, the correct trade is 15 minutes of setup friction in exchange for the elimination of an entire class of environment-parity bugs.

**Action items:**
- Remove all SQLite references from `connection.py`, `seed_db.py`, and `docker-compose.yml`
- Set `DATABASE_URL = postgresql://gridsense:gridsense@localhost:5432/gridsense` in `.env.example`
- Apply the four schema adjustments in section 1.7
- Add a `docker-compose.yml` health check so the backend container waits for PostgreSQL to be ready before starting

---

## 2. Parallel Development Optimization

### 2.1 The Core Problem with the Current Timeline

The implementation plan's Week 1 development order implies a serial dependency chain:

```
Raw CSV → ML pipeline → model artifacts → backend endpoints → frontend screens
```

Under this model, Member 3 (Frontend Lead) and Member 4 (Data Engineer) are blocked for most of Days 1–5 while Member 1 trains models and Member 2 seeds the database. This is the primary source of idle time in the current plan.

The fix is to break the false dependency: frontend screens do not need real API responses to be built. They need responses that have the correct shape. This is what mock JSON achieves. Every frontend component can be built, styled, and made interactive against a static mock response. The only step that requires a real API is the final wire-up — and that step is fast when the component is already complete.

The parallel development plan below eliminates all frontend idle time in Week 1 and reduces backend idle time by scaffolding endpoints against mock artifacts before real model training completes.

---

### 2.2 What Can Be Built Before ML Models Exist

The following are fully independent of trained model artifacts:

#### Backend (no models needed)

| Endpoint | Dependency | Can start |
|---|---|---|
| `GET /incidents` | `events_clean.csv` + seeded DB | Day 2 (after ingest script runs) |
| `GET /incidents/summary` | `events_clean.csv` + seeded DB | Day 2 |
| `GET /incidents/junctions` | `events_clean.csv` + seeded DB | Day 2 |
| `GET /corridors/risk` | `corridor_risk_index.json` (JSON artifact, no ML) | Day 2 |
| `GET /corridors/{corridor}/junctions` | DB query only | Day 2 |
| `GET /lcv/risk` | `lcv_incidents.csv` (pre-computed, no ML) | Day 2 |
| `POST /deploy/recommend` | `station_map.json` + `station_concurrency.json` (JSON artifacts, no ML) | Day 3 |
| `GET /health` | Nothing | Day 1 |

**Critical insight:** `POST /deploy/recommend` is entirely rule-based. It reads from `station_map.json` and `station_concurrency.json`, both of which are built in `07_export_artifacts.py` from raw aggregations — no model training required. Member 2 can implement this endpoint as soon as those JSON files exist, which happens on Day 2 alongside the CSV ingest.

The only endpoints that require trained model artifacts are:
- `POST /predict/triage` — needs `closure_model.pkl` and `priority_model.pkl`
- `GET /forecast/junction/{junction}` — needs `prophet_models/*.pkl`
- `POST /predict/planned-event-lookup` — needs `planned_events_lookup.csv` (no ML, but low priority)

#### Frontend (no API needed)

Every frontend component can be built against mock JSON from Day 1. The complete list:

| Component | Needs real API | Can start |
|---|---|---|
| `AppShell`, `Sidebar`, `TopBar` | No | Day 1 |
| `CommandCenterMap` (Leaflet base) | No (hardcode mock incidents) | Day 1 |
| `IncidentLayer` | No (mock incident array) | Day 1 |
| `MapFilterPanel` | No (local state only) | Day 1 |
| `CorridorRiskSidebar` | No (mock corridor list) | Day 1 |
| `TriageForm` | No (form state only) | Day 1 |
| `PredictionResultCard` | No (mock prediction response) | Day 1 |
| `DisagreementFlag` | No (prop-driven render) | Day 1 |
| `JunctionForecastChart` | No (mock forecast array) | Day 1 |
| `PeakHourBadge` | No (prop-driven) | Day 1 |
| `DeploymentResultCard` | No (mock deployment response) | Day 1 |
| `EscalationTierBadge` | No (prop-driven) | Day 1 |
| `FlipkartPanel` | No (mock LCV stats) | Day 1 |
| `LCVRiskChart` | No (mock hourly data) | Day 1 |
| `CorridorRiskTable` | No (mock corridor list) | Day 1 |
| All `shared/` components | No | Day 1 |

#### ML pipeline (partial independence)

`07_export_artifacts.py` — specifically the JSON artifact generation (not model files) — can run as soon as `01_ingest.py` completes. The following JSON artifacts do not require any model training:
- `duration_lookup.json` (pure pandas groupby on `event_cause`)
- `station_map.json` (pure groupby on `corridor` × `police_station`)
- `station_concurrency.json` (pure groupby on `police_station` × `hour` × `dow`)
- `corridor_risk_index.json` (pure aggregations on incident counts and rates)
- `encoders.pkl` (LabelEncoders fit on the processed data, not trained models)

These are computable by end of Day 2, before any model training begins on Day 3. Separating their generation from `07_export_artifacts.py` into a dedicated script (call it `02b_build_lookups.py`) makes this explicit and allows Member 2 to unblock `POST /deploy/recommend` by Day 3 without waiting for model training to complete on Days 3–4.

---

### 2.3 What Requires Trained Models

| Work item | Required artifact | Earliest available |
|---|---|---|
| `POST /predict/triage` backend implementation | `closure_model.pkl`, `priority_model.pkl`, `encoders.pkl` | End of Day 4 |
| Triage screen real API wire-up | `POST /predict/triage` working | End of Day 5 |
| Disagreement flag real data | `POST /predict/triage` working | End of Day 5 |
| `GET /forecast/junction/{junction}` | `prophet_models/*.pkl` | End of Day 4–5 (can run in parallel with model training) |
| Forecast screen real API wire-up | `GET /forecast/junction/{junction}` working | Day 6 |
| Model metrics slide | Evaluation scripts run | End of Day 5 |

**Note on Prophet training:** `06_train_forecast.py` trains one Prophet model per junction. Training 10–20 Prophet models takes approximately 5–15 minutes total (Prophet is fast on small datasets). This can run in the background while Member 1 is training the XGBoost models. It does not need to complete before XGBoost training begins — they can run concurrently if the machine has sufficient CPU.

---

### 2.4 What Requires Real API Integration

"Real API integration" means replacing the mock response in a frontend component with a live `fetch()` or Axios call to the actual running backend.

| Component | Required real endpoint | Earliest wire-up |
|---|---|---|
| `IncidentLayer` (map pins) | `GET /incidents` | Day 5 (DB seeded) |
| `CorridorRiskSidebar` | `GET /corridors/risk` | Day 5 |
| `MapFilterPanel` (live filtering) | `GET /incidents` with query params | Day 5 |
| `PredictionResultCard` | `POST /predict/triage` | Day 6 (models trained) |
| `DisagreementFlag` | `POST /predict/triage` | Day 6 |
| `DeploymentResultCard` | `POST /deploy/recommend` | Day 6 |
| `JunctionForecastChart` | `GET /forecast/junction/{junction}` | Day 7 |
| `FlipkartPanel` (all charts) | `GET /lcv/risk` | Day 6 |
| `JunctionMarkerLayer` | `GET /incidents/junctions` | Day 6 |

The correct build order for every component:

1. Build with mock JSON (immediate)
2. Build the `api/` client function for the corresponding endpoint
3. Wire the component to the client function when the real endpoint is available
4. Remove the mock

Steps 1 and 2 happen simultaneously. Step 3 is a 15–30 minute change per component when the endpoint is ready.

---

### 2.5 Mock JSON Responses for Every Dashboard Screen

These are the exact mock responses to place in `frontend/src/api/mocks/` and import in the Zustand stores during development. Each mock is shaped identically to the real API contract defined in the implementation plan.

---

#### Mock: `GET /incidents/summary`

File: `frontend/src/api/mocks/summary.json`

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

#### Mock: `GET /incidents` (truncated — 20 representative records)

File: `frontend/src/api/mocks/incidents.json`

The real response will have up to 2,000 records. The mock needs enough records to render a meaningful map cluster across Bengaluru. Use 50 records covering all major corridors and priority levels.

```json
{
  "total": 8173,
  "filtered": 8173,
  "incidents": [
    {
      "id": "FKID000000",
      "event_type": "unplanned",
      "event_cause": "vehicle_breakdown",
      "latitude": 13.0400041,
      "longitude": 77.5180991,
      "corridor": "Tumkur Road",
      "junction": "JalahalliCross(SM Circle)",
      "police_station": "Peenya",
      "priority": "High",
      "requires_road_closure": false,
      "start_datetime": "2024-03-07T17:01:48Z",
      "duration_mins": 154,
      "status": "closed",
      "is_stale_active": false
    },
    {
      "id": "FKID000002",
      "event_type": "unplanned",
      "event_cause": "others",
      "latitude": 12.955622,
      "longitude": 77.5857083,
      "corridor": "Non-corridor",
      "junction": "UrvashiJunction",
      "police_station": "Wilson Garden",
      "priority": "Low",
      "requires_road_closure": false,
      "start_datetime": "2023-11-11T06:18:03Z",
      "duration_mins": 4057,
      "status": "closed",
      "is_stale_active": false
    },
    {
      "id": "FKID000008",
      "event_type": "planned",
      "event_cause": "public_event",
      "latitude": 12.97883573,
      "longitude": 77.59953728,
      "corridor": "CBD 2",
      "junction": "QueensStatueCircle",
      "police_station": "Cubbon Park",
      "priority": "High",
      "requires_road_closure": false,
      "start_datetime": "2024-02-12T02:05:46Z",
      "duration_mins": 720,
      "status": "closed",
      "is_stale_active": false
    },
    {
      "id": "FKID000042",
      "event_type": "unplanned",
      "event_cause": "accident",
      "latitude": 12.9218755,
      "longitude": 77.6451585,
      "corridor": "ORR East 1",
      "junction": "SilkBoardJunc",
      "police_station": "HSR Layout",
      "priority": "High",
      "requires_road_closure": true,
      "start_datetime": "2024-01-30T04:07:24Z",
      "duration_mins": 37,
      "status": "closed",
      "is_stale_active": false
    },
    {
      "id": "FKID000100",
      "event_type": "unplanned",
      "event_cause": "water_logging",
      "latitude": 13.0008457,
      "longitude": 77.6813712,
      "corridor": "ORR East 2",
      "junction": null,
      "police_station": "K.R. Pura",
      "priority": "High",
      "requires_road_closure": false,
      "start_datetime": "2024-03-07T18:01:40Z",
      "duration_mins": null,
      "status": "active",
      "is_stale_active": true
    },
    {
      "id": "FKID000201",
      "event_type": "unplanned",
      "event_cause": "pot_holes",
      "latitude": 12.9720418,
      "longitude": 77.6194831,
      "corridor": "Old Madras Road",
      "junction": "TrinityCircle",
      "police_station": "Halasur",
      "priority": "High",
      "requires_road_closure": false,
      "start_datetime": "2024-01-29T22:54:11Z",
      "duration_mins": null,
      "status": "active",
      "is_stale_active": false
    },
    {
      "id": "FKID000305",
      "event_type": "planned",
      "event_cause": "procession",
      "latitude": 12.9767078,
      "longitude": 77.6017133,
      "corridor": "CBD 2",
      "junction": "AnilKumbleCircle",
      "police_station": "Cubbon Park",
      "priority": "High",
      "requires_road_closure": true,
      "start_datetime": "2024-01-29T02:29:03Z",
      "duration_mins": 122,
      "status": "closed",
      "is_stale_active": false
    },
    {
      "id": "FKID000410",
      "event_type": "unplanned",
      "event_cause": "tree_fall",
      "latitude": 13.0061469,
      "longitude": 77.5794348,
      "corridor": "Non-corridor",
      "junction": null,
      "police_station": "Sadashivanagar",
      "priority": "Low",
      "requires_road_closure": true,
      "start_datetime": "2024-03-07T17:56:55Z",
      "duration_mins": 9467,
      "status": "closed",
      "is_stale_active": false
    }
  ]
}
```

> For the mock, include at least 40–50 records spanning all major corridors, both priority levels, both event types, and a geographic spread across the Bengaluru bounding box (lat 12.80–13.27, lon 77.31–77.77). The 8 records above are illustrative — expand with real FKID values from the dataset to fill out map coverage.

---

#### Mock: `GET /incidents/junctions`

File: `frontend/src/api/mocks/junctions.json`

```json
{
  "junctions": [
    {
      "junction": "MekhriCircle",
      "latitude": 13.0056,
      "longitude": 77.5810,
      "incident_count": 64,
      "high_priority_count": 58,
      "closure_count": 4,
      "top_cause": "vehicle_breakdown"
    },
    {
      "junction": "AyyappaTempleJunc",
      "latitude": 12.9196,
      "longitude": 77.6473,
      "incident_count": 49,
      "high_priority_count": 44,
      "closure_count": 2,
      "top_cause": "vehicle_breakdown"
    },
    {
      "junction": "SatteliteBusStandJunc",
      "latitude": 12.9312,
      "longitude": 77.4882,
      "incident_count": 43,
      "high_priority_count": 38,
      "closure_count": 3,
      "top_cause": "vehicle_breakdown"
    },
    {
      "junction": "YeshwanthpuraCircle",
      "latitude": 13.0271,
      "longitude": 77.5513,
      "incident_count": 38,
      "high_priority_count": 36,
      "closure_count": 2,
      "top_cause": "vehicle_breakdown"
    },
    {
      "junction": "YelhankaCircle",
      "latitude": 13.1005,
      "longitude": 77.5962,
      "incident_count": 34,
      "high_priority_count": 30,
      "closure_count": 1,
      "top_cause": "vehicle_breakdown"
    },
    {
      "junction": "SilkBoardJunc",
      "latitude": 12.9172,
      "longitude": 77.6231,
      "incident_count": 33,
      "high_priority_count": 31,
      "closure_count": 5,
      "top_cause": "vehicle_breakdown"
    },
    {
      "junction": "JalahalliCross(SM Circle)",
      "latitude": 13.0401,
      "longitude": 77.5181,
      "incident_count": 32,
      "high_priority_count": 30,
      "closure_count": 2,
      "top_cause": "vehicle_breakdown"
    },
    {
      "junction": "Nagavara-ORR Junction",
      "latitude": 13.0503,
      "longitude": 77.6211,
      "incident_count": 32,
      "high_priority_count": 29,
      "closure_count": 1,
      "top_cause": "vehicle_breakdown"
    }
  ]
}
```

---

#### Mock: `GET /corridors/risk`

File: `frontend/src/api/mocks/corridorRisk.json`

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
    },
    {
      "corridor": "Bellary Road 1",
      "total_incidents": 610,
      "high_priority_rate": 1.0,
      "closure_rate": 0.087,
      "composite_risk_score": 84.1,
      "top_junction": "MekhriCircle",
      "top_police_station": "Sadashivanagar",
      "median_duration_mins": 38.7
    },
    {
      "corridor": "Tumkur Road",
      "total_incidents": 458,
      "high_priority_rate": 0.991,
      "closure_rate": 0.026,
      "composite_risk_score": 71.3,
      "top_junction": "JalahalliCross(SM Circle)",
      "top_police_station": "Yeshwanthpura",
      "median_duration_mins": 35.2
    },
    {
      "corridor": "Bellary Road 2",
      "total_incidents": 379,
      "high_priority_rate": 1.0,
      "closure_rate": 0.058,
      "composite_risk_score": 74.8,
      "top_junction": "YelhankaCircle",
      "top_police_station": "Yelahanka",
      "median_duration_mins": 41.3
    },
    {
      "corridor": "Hosur Road",
      "total_incidents": 298,
      "high_priority_rate": 0.993,
      "closure_rate": 0.094,
      "composite_risk_score": 72.6,
      "top_junction": "SilkBoardJunc",
      "top_police_station": "Madiwala",
      "median_duration_mins": 45.8
    },
    {
      "corridor": "ORR North 1",
      "total_incidents": 275,
      "high_priority_rate": 1.0,
      "closure_rate": 0.069,
      "composite_risk_score": 68.9,
      "top_junction": "Nagavara-ORR Junction",
      "top_police_station": "Hebbala",
      "median_duration_mins": 39.1
    },
    {
      "corridor": "Non-corridor",
      "total_incidents": 3124,
      "high_priority_rate": 0.0,
      "closure_rate": 0.121,
      "composite_risk_score": 18.3,
      "top_junction": null,
      "top_police_station": "Yelahanka",
      "median_duration_mins": 96.2
    }
  ]
}
```

---

#### Mock: `POST /predict/triage` response

File: `frontend/src/api/mocks/triageResult.json`

Two variants needed — one standard High priority result, one with the disagreement flag firing. Import whichever matches the demo scenario.

**Variant A — standard High priority prediction:**

```json
{
  "closure_probability": 0.41,
  "closure_flag": false,
  "priority_probability": 0.94,
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

**Variant B — disagreement flag fires (Non-corridor + predicted High):**

```json
{
  "closure_probability": 0.28,
  "closure_flag": false,
  "priority_probability": 0.71,
  "predicted_priority": "High",
  "disagreement_flag": true,
  "disagreement_reason": "This incident is off the named corridors. The current system defaults these to Low priority. Our model predicts High based on cause, vehicle type, and time pattern.",
  "predicted_duration_mins": 287,
  "duration_bucket": "long",
  "duration_p25": 120,
  "duration_p75": 560,
  "model_versions": {
    "closure_model": "v1.0",
    "priority_model": "v1.0"
  },
  "inference_ms": 31
}
```

---

#### Mock: `POST /deploy/recommend` response

File: `frontend/src/api/mocks/deployResult.json`

```json
{
  "recommended_station": "Yeshwanthpura",
  "secondary_station": "Peenya",
  "recommended_officer_count": 5,
  "officer_count_rationale": "Yeshwanthpura average concurrent load at 20:00 on Thursday is 3.1 incidents. Adding 2 for High priority and closure probability above 35%.",
  "escalation_tier": "Elevated",
  "escalation_rationale": "High priority, closure probability 41%, predicted duration under 2 hours.",
  "deployment_duration_mins": 43,
  "suggested_junctions": [
    "JalahalliCross(SM Circle)",
    "YeshwanthpuraCircle"
  ],
  "corridor_risk_score": 71.3,
  "historical_station_incidents": 239
}
```

---

#### Mock: `GET /forecast/junction/{junction}` response

File: `frontend/src/api/mocks/forecast.json`

> This mock covers the next 24 hours. The real response covers 72 hours. The mock uses the 4–6am and 7–10pm peak pattern from the actual dataset findings.

```json
{
  "junction": "MekhriCircle",
  "corridor": "Bellary Road 1",
  "historical_daily_avg": 0.43,
  "forecast": [
    { "datetime": "2024-06-16T00:00:00Z", "hour_of_day": 0, "predicted_incident_count": 0.3, "yhat_lower": 0.0, "yhat_upper": 0.8, "is_peak_hour": false },
    { "datetime": "2024-06-16T01:00:00Z", "hour_of_day": 1, "predicted_incident_count": 0.2, "yhat_lower": 0.0, "yhat_upper": 0.7, "is_peak_hour": false },
    { "datetime": "2024-06-16T02:00:00Z", "hour_of_day": 2, "predicted_incident_count": 0.2, "yhat_lower": 0.0, "yhat_upper": 0.6, "is_peak_hour": false },
    { "datetime": "2024-06-16T03:00:00Z", "hour_of_day": 3, "predicted_incident_count": 0.3, "yhat_lower": 0.0, "yhat_upper": 0.8, "is_peak_hour": false },
    { "datetime": "2024-06-16T04:00:00Z", "hour_of_day": 4, "predicted_incident_count": 1.4, "yhat_lower": 0.8, "yhat_upper": 2.1, "is_peak_hour": true },
    { "datetime": "2024-06-16T05:00:00Z", "hour_of_day": 5, "predicted_incident_count": 1.8, "yhat_lower": 1.1, "yhat_upper": 2.6, "is_peak_hour": true },
    { "datetime": "2024-06-16T06:00:00Z", "hour_of_day": 6, "predicted_incident_count": 1.6, "yhat_lower": 0.9, "yhat_upper": 2.4, "is_peak_hour": true },
    { "datetime": "2024-06-16T07:00:00Z", "hour_of_day": 7, "predicted_incident_count": 0.5, "yhat_lower": 0.1, "yhat_upper": 1.0, "is_peak_hour": false },
    { "datetime": "2024-06-16T08:00:00Z", "hour_of_day": 8, "predicted_incident_count": 0.3, "yhat_lower": 0.0, "yhat_upper": 0.8, "is_peak_hour": false },
    { "datetime": "2024-06-16T09:00:00Z", "hour_of_day": 9, "predicted_incident_count": 0.1, "yhat_lower": 0.0, "yhat_upper": 0.5, "is_peak_hour": false },
    { "datetime": "2024-06-16T10:00:00Z", "hour_of_day": 10, "predicted_incident_count": 0.1, "yhat_lower": 0.0, "yhat_upper": 0.4, "is_peak_hour": false },
    { "datetime": "2024-06-16T11:00:00Z", "hour_of_day": 11, "predicted_incident_count": 0.1, "yhat_lower": 0.0, "yhat_upper": 0.4, "is_peak_hour": false },
    { "datetime": "2024-06-16T12:00:00Z", "hour_of_day": 12, "predicted_incident_count": 0.1, "yhat_lower": 0.0, "yhat_upper": 0.4, "is_peak_hour": false },
    { "datetime": "2024-06-16T13:00:00Z", "hour_of_day": 13, "predicted_incident_count": 0.1, "yhat_lower": 0.0, "yhat_upper": 0.3, "is_peak_hour": false },
    { "datetime": "2024-06-16T14:00:00Z", "hour_of_day": 14, "predicted_incident_count": 0.0, "yhat_lower": 0.0, "yhat_upper": 0.2, "is_peak_hour": false },
    { "datetime": "2024-06-16T15:00:00Z", "hour_of_day": 15, "predicted_incident_count": 0.0, "yhat_lower": 0.0, "yhat_upper": 0.2, "is_peak_hour": false },
    { "datetime": "2024-06-16T16:00:00Z", "hour_of_day": 16, "predicted_incident_count": 0.0, "yhat_lower": 0.0, "yhat_upper": 0.2, "is_peak_hour": false },
    { "datetime": "2024-06-16T17:00:00Z", "hour_of_day": 17, "predicted_incident_count": 0.1, "yhat_lower": 0.0, "yhat_upper": 0.4, "is_peak_hour": false },
    { "datetime": "2024-06-16T18:00:00Z", "hour_of_day": 18, "predicted_incident_count": 0.4, "yhat_lower": 0.1, "yhat_upper": 0.9, "is_peak_hour": false },
    { "datetime": "2024-06-16T19:00:00Z", "hour_of_day": 19, "predicted_incident_count": 1.2, "yhat_lower": 0.6, "yhat_upper": 1.9, "is_peak_hour": true },
    { "datetime": "2024-06-16T20:00:00Z", "hour_of_day": 20, "predicted_incident_count": 2.1, "yhat_lower": 1.4, "yhat_upper": 2.9, "is_peak_hour": true },
    { "datetime": "2024-06-16T21:00:00Z", "hour_of_day": 21, "predicted_incident_count": 2.4, "yhat_lower": 1.6, "yhat_upper": 3.2, "is_peak_hour": true },
    { "datetime": "2024-06-16T22:00:00Z", "hour_of_day": 22, "predicted_incident_count": 1.7, "yhat_lower": 1.0, "yhat_upper": 2.5, "is_peak_hour": true },
    { "datetime": "2024-06-16T23:00:00Z", "hour_of_day": 23, "predicted_incident_count": 1.1, "yhat_lower": 0.5, "yhat_upper": 1.8, "is_peak_hour": false }
  ],
  "peak_windows": [
    { "start_hour": 4, "end_hour": 6, "label": "early morning peak" },
    { "start_hour": 19, "end_hour": 22, "label": "evening peak" }
  ],
  "model_mae": 1.2
}
```

---

#### Mock: `GET /lcv/risk`

File: `frontend/src/api/mocks/lcvRisk.json`

```json
{
  "total_lcv_incidents": 678,
  "lcv_high_priority_rate": 0.704,
  "lcv_closure_rate": 0.027,
  "overall_closure_rate": 0.083,
  "riskiest_hour": 20,
  "riskiest_corridor": "Tumkur Road",
  "by_corridor": [
    { "corridor": "Tumkur Road", "lcv_incidents": 81, "risk_tag": "avoid", "peak_hour": 20 },
    { "corridor": "Bellary Road 1", "lcv_incidents": 74, "risk_tag": "avoid", "peak_hour": 5 },
    { "corridor": "Mysore Road", "lcv_incidents": 72, "risk_tag": "avoid", "peak_hour": 20 },
    { "corridor": "ORR North 2", "lcv_incidents": 43, "risk_tag": "caution", "peak_hour": 4 },
    { "corridor": "Bellary Road 2", "lcv_incidents": 31, "risk_tag": "caution", "peak_hour": 21 },
    { "corridor": "ORR North 1", "lcv_incidents": 27, "risk_tag": "caution", "peak_hour": 5 },
    { "corridor": "Magadi Road", "lcv_incidents": 25, "risk_tag": "caution", "peak_hour": 20 },
    { "corridor": "ORR East 1", "lcv_incidents": 22, "risk_tag": "prefer", "peak_hour": 4 },
    { "corridor": "Old Madras Road", "lcv_incidents": 21, "risk_tag": "prefer", "peak_hour": 19 }
  ],
  "by_hour": [
    { "hour": 0, "lcv_incidents": 38, "risk_level": "moderate" },
    { "hour": 1, "lcv_incidents": 46, "risk_level": "moderate" },
    { "hour": 2, "lcv_incidents": 32, "risk_level": "moderate" },
    { "hour": 3, "lcv_incidents": 40, "risk_level": "moderate" },
    { "hour": 4, "lcv_incidents": 51, "risk_level": "high" },
    { "hour": 5, "lcv_incidents": 59, "risk_level": "high" },
    { "hour": 6, "lcv_incidents": 55, "risk_level": "high" },
    { "hour": 7, "lcv_incidents": 36, "risk_level": "moderate" },
    { "hour": 8, "lcv_incidents": 32, "risk_level": "moderate" },
    { "hour": 9, "lcv_incidents": 12, "risk_level": "low" },
    { "hour": 10, "lcv_incidents": 4, "risk_level": "low" },
    { "hour": 11, "lcv_incidents": 3, "risk_level": "low" },
    { "hour": 12, "lcv_incidents": 2, "risk_level": "low" },
    { "hour": 13, "lcv_incidents": 3, "risk_level": "low" },
    { "hour": 14, "lcv_incidents": 1, "risk_level": "low" },
    { "hour": 15, "lcv_incidents": 1, "risk_level": "low" },
    { "hour": 16, "lcv_incidents": 1, "risk_level": "low" },
    { "hour": 17, "lcv_incidents": 2, "risk_level": "low" },
    { "hour": 18, "lcv_incidents": 21, "risk_level": "moderate" },
    { "hour": 19, "lcv_incidents": 56, "risk_level": "high" },
    { "hour": 20, "lcv_incidents": 72, "risk_level": "critical" },
    { "hour": 21, "lcv_incidents": 35, "risk_level": "moderate" },
    { "hour": 22, "lcv_incidents": 39, "risk_level": "moderate" },
    { "hour": 23, "lcv_incidents": 35, "risk_level": "moderate" }
  ]
}
```

---

### 2.6 Updated Task Allocation

The revised allocation eliminates idle time by parallelising all four members from Day 1. The key change is that Members 3 and 4 begin frontend work immediately using mock JSON, without waiting for ML training or backend availability.

---

#### New Day-by-Day Allocation (Week 1)

| Day | Member 1 (ML Lead) | Member 2 (Backend) | Member 3 (Frontend Lead) | Member 4 (Data Eng + QA) |
|---|---|---|---|---|
| 1 | Run `01_ingest.py`, fix data issues, validate clean CSV | Set up repo, Docker, PostgreSQL, FastAPI scaffold, `GET /health` | Scaffold React + Vite + Tailwind, build `AppShell` + `Sidebar` + `TopBar` | Create all mock JSON files in `frontend/src/api/mocks/`, set up Zustand stores with mock data |
| 2 | Run `02_feature_engineer.py`, validate feature matrix, fit encoders | Run `seed_db.py`, implement `GET /incidents` + `GET /incidents/summary` using real DB | Build `CommandCenterMap` with Leaflet using `incidents.json` mock, build `MapFilterPanel` (local state), build `CorridorRiskSidebar` using `corridorRisk.json` mock | Build `TriageForm` (local state, no API), build `PredictionResultCard` using `triageResult.json` mock A and B |
| 3 | Run `03_train_closure.py` (XGBoost, ~1h), evaluate, log AUC-ROC | Implement `GET /corridors/risk`, `GET /lcv/risk`, `GET /incidents/junctions` using JSON artifacts + DB | Build `ForecastScreen` + `JunctionForecastChart` using `forecast.json` mock, build `PeakHourBadge` | Build `DeploymentResultCard` using `deployResult.json` mock, build `EscalationTierBadge`, `StationBadge` |
| 4 | Run `04_train_priority.py`, evaluate (overall + Non-corridor accuracy), run `05_train_duration.py` | Implement `POST /deploy/recommend` (rule-based, uses JSON artifacts — no models needed) | Build `FlipkartPanel` + `LCVRiskChart` + `LCVByHourChart` using `lcvRisk.json` mock | Write all `frontend/src/api/` client functions (Axios wrappers for all 10 endpoints) |
| 5 | Run `06_train_forecast.py` for top 10 junctions, run `07_export_artifacts.py` fully | Implement `POST /predict/triage` (models now available from Member 1), implement `GET /forecast/junction/{junction}` | Wire `CommandCenterMap` to real `GET /incidents` (replace mock), wire `CorridorRiskSidebar` to real `GET /corridors/risk` | Wire `FlipkartPanel` to real `GET /lcv/risk`, wire `DeploymentScreen` to real `POST /deploy/recommend` |

---

#### New Day-by-Day Allocation (Week 2)

| Day | Member 1 (ML Lead) | Member 2 (Backend) | Member 3 (Frontend Lead) | Member 4 (Data Eng + QA) |
|---|---|---|---|---|
| 6 | Run evaluation scripts (`evaluate_closure.py`, `evaluate_priority.py`), document model metrics | Implement `POST /predict/planned-event-lookup`, finish all remaining endpoints | Wire `TriageScreen` to real `POST /predict/triage` (replace mock), wire `DisagreementFlag` to live response | Wire `ForecastScreen` to real `GET /forecast/junction/{junction}` |
| 7 | Document Non-corridor accuracy vs overall accuracy, prepare model metrics slide content | Add CORS config for Vercel domain, add error handling on all endpoints, write Swagger descriptions | Wire `JunctionMarkerLayer` to `GET /incidents/junctions`, add loading states to all screens | Add loading states and error boundaries to all screens, run cross-browser tests |
| 8 | Run `06_train_forecast.py` for remaining 10 junctions (top 20 total) | Write `scripts/health_check.py`, validate all endpoints return correct shapes | Build `QuickDeployButton` (Triage → Deployment navigation with pre-fill), responsive Sidebar collapse | End-to-end flow test: map → triage → deployment → Flipkart, document all bugs found |
| 9 | Support Member 4 with model accuracy Q&A, prepare worked examples for demo | Deploy backend to Render.com, validate production DB seeding, test all endpoints on live URL | Deploy frontend to Vercel, fix any CORS or env-variable issues on production | First full demo rehearsal (5-minute version), time each segment, identify weak points |
| 10 | Finalize evaluation metrics, write model card (2 pages: inputs, outputs, accuracy, known limitations) | Production smoke test all endpoints, set up basic logging | Production smoke test all screens, fix any rendering issues on live URL | Second full demo rehearsal, refine pacing, prepare judge Q&A responses for top 10 questions |

---

#### New Day-by-Day Allocation (Week 3)

| Day | Member 1 | Member 2 | Member 3 | Member 4 |
|---|---|---|---|---|
| 11–12 | Backup and verify all model artifacts are in cloud storage | Polish API error responses, add request validation | Polish all chart styling, ensure Recharts renders correctly at all viewport widths | Prepare architecture diagram slide, update README |
| 13–14 | Review and finalize judge Q&A responses | Final API testing | Final UI polish: typography, spacing, Tailwind consistency | Third demo rehearsal, prepare submission materials |
| 15 | Submission | Submission | Submission | Submission |

---

### 2.7 Critical Path Analysis

The critical path is the sequence of tasks where any delay directly delays the final submission. Every task off the critical path can slip without affecting the submission date.

```
Critical path:

Day 1:  01_ingest.py completes
        │
Day 2:  02_feature_engineer.py + encoders.pkl ready
        seed_db.py runs against PostgreSQL
        │
Day 3:  03_train_closure.py completes → closure_model.pkl
        04_train_priority.py starts
        │
Day 4:  04_train_priority.py completes → priority_model.pkl
        07_export_artifacts.py runs fully
        │
Day 5:  POST /predict/triage implemented and returning real predictions
        │
Day 6:  TriageScreen wired to real POST /predict/triage
        DisagreementFlag tested with real model output
        │
Day 9:  Backend deployed to Render
        Frontend deployed to Vercel
        First full demo on production URL
        │
Day 10: All integration issues resolved
        │
Day 15: Submission
```

**Off the critical path (can slip without risk):**

- Prophet training (`06_train_forecast.py`) — runs in background during Days 3–4, does not block the triage demo
- `GET /forecast/junction/{junction}` — forecast screen is a secondary demo moment; triage is the primary
- `POST /predict/planned-event-lookup` — nice-to-have, not in the core demo flow
- `GET /incidents/junctions` — junction markers on the map enhance the visual but are not demo-critical
- Loading states, error boundaries, responsive collapse — polish, not function
- All Week 3 items — polish and rehearsal, all deliverables complete by end of Week 2

---

### 2.8 Development Bottlenecks and How to Avoid Them

#### Bottleneck 1: ML training blocks triage endpoint

**Risk:** Member 2 cannot implement `POST /predict/triage` until `closure_model.pkl` and `priority_model.pkl` exist. If Member 1's training runs into issues on Days 3–4, Member 2 is idle.

**Mitigation:**  
Member 2 writes the `prediction_service.py` shell with a stub that returns hardcoded mock values if the model files do not exist. The endpoint is scaffolded and returning the correct response shape from Day 1. When real artifacts arrive on Day 4–5, Member 2 replaces the stub with the real `joblib.load()` call. The endpoint itself never needs to block.

Stub logic in `prediction_service.py`:
```python
MOCK_MODE = not os.path.exists('ml/artifacts/closure_model.pkl')

def predict_triage(features: dict) -> dict:
    if MOCK_MODE:
        return {
            "closure_probability": 0.35,
            "priority_probability": 0.88,
            # ... rest of mock response
        }
    # real model inference here
```

---

#### Bottleneck 2: Frontend idle while waiting for API

**Risk:** Members 3 and 4 are blocked on backend endpoints being live before they can build and test components.

**Mitigation:** Already resolved by the mock JSON strategy in section 2.5. Every component is built against mock data. The API wire-up is a 15–30 minute change per component once the real endpoint is available. No frontend developer should ever be idle waiting for a backend endpoint.

Implementation: Add a `USE_MOCK` flag to `frontend/src/api/client.js`:
```javascript
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
```

Set `VITE_USE_MOCK=true` in `.env.local` during development. Set `VITE_USE_MOCK=false` in production environment. Each `api/` client function checks this flag and returns the mock JSON if true.

---

#### Bottleneck 3: Database seeding takes longer than expected

**Risk:** `seed_db.py` loading 8,173 rows into PostgreSQL should take under 10 seconds. But if the schema definition has errors, or the CSV has malformed rows the parser doesn't catch, the seed fails and Member 2 is debugging schema issues on Day 2 instead of building endpoints.

**Mitigation:**  
Before running `seed_db.py` on Day 2, Member 1 should validate `events_clean.csv` with a quick pandas profiling check at the end of `01_ingest.py`: count nulls per column, verify no rows have invalid lat/lon, verify all `start_datetime` values parse correctly. Print a summary. If this validation passes, `seed_db.py` will succeed.

Additionally, seed a small test subset first (100 rows) with `--limit 100` flag, verify the schema works, then seed the full dataset.

---

#### Bottleneck 4: PostgreSQL connection issues on Day 1

**Risk:** Member 2 spends Day 1 debugging Docker networking instead of building the FastAPI scaffold.

**Mitigation:**  
Use the exact Docker Compose configuration from section 1.5 of this document. Add a `healthcheck` to the PostgreSQL service so the backend container waits until the DB is actually ready before trying to connect — this prevents "connection refused" errors on cold starts:

```yaml
db:
  image: postgres:16-alpine
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U gridsense"]
    interval: 5s
    timeout: 5s
    retries: 5
```

Add `depends_on: db: condition: service_healthy` to the backend service. This is the correct Docker Compose pattern for database-dependent services.

---

#### Bottleneck 5: Demo breaks on production URL

**Risk:** The demo runs perfectly on localhost but fails on the production Render + Vercel deployment due to CORS, environment variables, or cold-start latency.

**Mitigation:**

1. Deploy to Render on Day 9 (not Day 14). This gives 6 days to find and fix production issues before submission.
2. Render free tier instances spin down after 15 minutes of inactivity. The cold start is 30–60 seconds. Add a `GET /health` ping from the frontend that fires on app load — this wakes the backend before the demo starts.
3. Set `CORS_ORIGINS` in `config.py` to include both `localhost:5173` (Vite dev) and the production Vercel URL.
4. All environment variables (`DATABASE_URL`, `CORS_ORIGINS`) must be set in Render's dashboard before Day 9 deploy.

---

#### Bottleneck 6: Member 4 underutilised in Week 1

**Risk:** The original plan has Member 4 "supporting Member 1" and doing data quality checks in Week 1 — work that amounts to a few hours and leaves Member 4 idle for most of the week.

**Mitigation:** The updated allocation in section 2.6 gives Member 4 full ownership of the `TriageForm`, `PredictionResultCard`, `DisagreementFlag`, `DeploymentResultCard`, and `EscalationTierBadge` components in Week 1, plus all `api/` client functions. These are high-impact components that directly support the demo's centerpiece moment (live triage). Member 4 is fully productive from Day 1 using mock JSON.

---

### 2.9 Recommended Build Order for Maximum Velocity

This is the globally optimal build sequence considering all four members working in parallel. Each numbered item is a task. Items on the same numbered level can happen simultaneously across team members.

```
Level 0 (Day 1 — all members start simultaneously):
  M1: Run 01_ingest.py
  M2: Set up repo, Docker, PostgreSQL, FastAPI scaffold, GET /health
  M3: Scaffold React + Vite + Tailwind + Zustand, build AppShell/Sidebar/TopBar
  M4: Create all mock JSON files, configure USE_MOCK flag, set up Zustand stores

Level 1 (Day 2):
  M1: Run 02_feature_engineer.py, fit encoders
  M2: seed_db.py, GET /incidents, GET /incidents/summary
  M3: CommandCenterMap (mock data), MapFilterPanel (local state), CorridorRiskSidebar (mock)
  M4: TriageForm (local state), PredictionResultCard (mock variant A + B), DisagreementFlag

Level 2 (Day 3):
  M1: 03_train_closure.py
  M2: GET /corridors/risk, GET /lcv/risk, GET /incidents/junctions (all from JSON artifacts or DB)
  M3: ForecastScreen + JunctionForecastChart (mock), PeakHourBadge
  M4: DeploymentResultCard (mock), EscalationTierBadge, StationBadge

Level 3 (Day 4):
  M1: 04_train_priority.py, 05_train_duration.py
  M2: POST /deploy/recommend (rule-based, no models — fully implementable now)
  M3: FlipkartPanel + LCVRiskChart + LCVByHourChart (mock)
  M4: All api/ client functions (Axios wrappers for all 10 endpoints)

Level 4 (Day 5 — INTEGRATION DAY 1):
  M1: 06_train_forecast.py, 07_export_artifacts.py (full)
  M2: POST /predict/triage (models now available), GET /forecast/junction/{junction}
  M3: Wire CommandCenterMap → real GET /incidents, wire CorridorRiskSidebar → real GET /corridors/risk
  M4: Wire FlipkartPanel → real GET /lcv/risk, wire DeploymentScreen → real POST /deploy/recommend

Level 5 (Day 6 — INTEGRATION DAY 2 — critical path moment):
  M1: evaluate_closure.py, evaluate_priority.py
  M2: POST /predict/planned-event-lookup, CORS config, error handling
  M3: Wire TriageScreen → real POST /predict/triage — THIS IS THE CRITICAL PATH MILESTONE
      Wire DisagreementFlag to live response
  M4: Wire ForecastScreen → real GET /forecast/junction/{junction}

Level 6 (Days 7–8 — polish):
  All: Loading states, error boundaries, responsive layout
  All: QA on production-like environment (ngrok or Render staging)
  M4: First demo rehearsal

Level 7 (Day 9 — PRODUCTION DEPLOY):
  M2: Backend to Render
  M3: Frontend to Vercel
  M4: Smoke test all endpoints on live URLs

Level 8 (Days 10–15 — hardening and rehearsal):
  All: Fix production issues, polish, rehearse
  M4: Demo rehearsals × 3, Q&A preparation
```

**The critical path milestone is Level 5, Day 6:** the moment `TriageScreen` calls real `POST /predict/triage` and returns a real closure probability, real priority prediction, and real disagreement flag. Everything before that is preparation. Everything after that is polish.

If the team hits this milestone by end of Day 6, the submission is on track.  
If the team hits this milestone by end of Day 8, the submission is still achievable.  
If the team has not hit this milestone by Day 10, the demo will use mock data, which is recoverable but not optimal.

---

*End of Implementation Readiness Review*

---

> Document version: 1.0  
> Companion to: GridSense_Implementation_Plan.md  
> Last updated: June 2026