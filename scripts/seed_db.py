"""
seed_db.py — Seed PostgreSQL from processed CSV and ML JSON artifacts.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from backend.db.connection import get_engine, get_session_local
from backend.db.base import Base
from backend.db.models import (
    Incident, CorridorRiskIndex, CorridorStationMap,
    StationConcurrency, DurationLookup,
)

CLEAN_CSV = ROOT / "data" / "processed" / "events_clean.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
BATCH_SIZE = 50


def ensure_tables_exist(engine) -> None:
    Base.metadata.create_all(bind=engine)
    print("[seed] Tables verified / created.")


def truncate_all(session) -> None:
    print("[seed] Truncating all tables …")
    tables = [
        "corridor_station_map",
        "corridor_risk_index",
        "station_concurrency",
        "duration_lookup",
        "incidents",
    ]
    for tbl in tables:
        session.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
    session.commit()
    print("[seed] All tables truncated.")


def clean_record(record: dict) -> dict:
    """Convert NaT, nan, and pandas NA values to None for PostgreSQL."""
    cleaned = {}
    for k, v in record.items():
        # Handle pandas NaT
        if v is pd.NaT:
            cleaned[k] = None
        # Handle float nan
        elif isinstance(v, float) and math.isnan(v):
            cleaned[k] = None
        # Handle pandas NA
        elif v is pd.NA:
            cleaned[k] = None
        # Handle pandas Timestamp — convert to Python datetime
        elif hasattr(v, 'to_pydatetime'):
            try:
                cleaned[k] = v.to_pydatetime()
            except Exception:
                cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned


def seed_incidents(session) -> int:
    print(f"\n[seed] Loading incidents from {CLEAN_CSV} …")
    df = pd.read_csv(CLEAN_CSV, low_memory=False)

    # Normalise boolean columns
    for bool_col in ("requires_road_closure", "is_stale_active",
                     "is_high_priority_corridor", "is_non_corridor"):
        if bool_col in df.columns:
            df[bool_col] = (
                df[bool_col]
                .astype(str).str.upper()
                .map({"TRUE": True, "FALSE": False, "1": True, "0": False})
                .fillna(False)
            )

    # Parse datetime columns properly
    for dt_col in ("start_datetime", "end_datetime", "closed_datetime", "modified_datetime"):
        if dt_col in df.columns:
            df[dt_col] = pd.to_datetime(df[dt_col], format="ISO8601", utc=True, errors="coerce")

    # Fill null values in NOT NULL columns with safe defaults
    df["priority"] = df["priority"].fillna("Low")
    df["status"] = df["status"].fillna("closed")
    df["event_type"] = df["event_type"].fillna("unplanned")
    df["event_cause"] = df["event_cause"].fillna("others")
    df["police_station"] = df["police_station"].fillna("Unknown")

    # Drop rows missing critical non-nullable fields that have no safe default
    before = len(df)
    df = df.dropna(subset=["id", "latitude", "longitude", "start_datetime"])
    dropped = before - len(df)
    if dropped > 0:
        print(f"  [seed] Dropped {dropped} rows with null critical fields")

    # Select only schema columns
    schema_cols = [c.name for c in Incident.__table__.columns if c.name != "created_at"]
    available = [c for c in schema_cols if c in df.columns]
    df = df[available]

    total = 0
    for i in range(0, len(df), BATCH_SIZE):
        raw_batch = df.iloc[i: i + BATCH_SIZE].to_dict("records")
        # Clean every record — convert NaT/nan to None
        batch = [clean_record(r) for r in raw_batch]
        stmt = pg_insert(Incident).values(batch)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
        session.execute(stmt)
        session.commit()
        total += len(batch)
        print(f"  … {total:,} / {len(df):,}", end="\r")

    print(f"\n[seed] Incidents seeded: {total:,}")
    return total


def seed_corridor_risk(session) -> int:
    path = ARTIFACT_DIR / "corridor_risk_index.json"
    print(f"\n[seed] Loading corridor risk from {path} …")
    with open(path) as f:
        data = json.load(f)

    rows = []
    for corridor, rec in data.items():
        rows.append({
            "corridor": corridor,
            "total_incidents": rec["total_incidents"],
            "high_priority_count": rec["high_priority_count"],
            "high_priority_rate": rec["high_priority_rate"],
            "closure_count": rec["closure_count"],
            "closure_rate": rec["closure_rate"],
            "composite_risk_score": rec["composite_risk_score"],
            "top_junction": rec.get("top_junction"),
            "top_police_station": rec.get("top_police_station"),
            "median_duration_mins": rec.get("median_duration_mins"),
        })

    stmt = pg_insert(CorridorRiskIndex).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["corridor"],
        set_={"composite_risk_score": stmt.excluded.composite_risk_score,
              "total_incidents": stmt.excluded.total_incidents},
    )
    session.execute(stmt)
    session.commit()
    print(f"[seed] Corridor risk records: {len(rows)}")
    return len(rows)


def seed_station_map(session) -> int:
    path = ARTIFACT_DIR / "station_map.json"
    print(f"\n[seed] Loading station map from {path} …")
    with open(path) as f:
        data = json.load(f)

    rows = []
    for corridor, stations in data.items():
        for s in stations:
            rows.append({
                "corridor": corridor,
                "police_station": s["police_station"],
                "incident_count": s["incident_count"],
                "rank": s["rank"],
            })

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i: i + BATCH_SIZE]
        stmt = pg_insert(CorridorStationMap).values(batch)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_corridor_rank")
        session.execute(stmt)
    session.commit()
    print(f"[seed] Station map records: {len(rows)}")
    return len(rows)


def seed_station_concurrency(session) -> int:
    path = ARTIFACT_DIR / "station_concurrency.json"
    print(f"\n[seed] Loading station concurrency from {path} …")
    with open(path) as f:
        data = json.load(f)

    rows = [
        {
            "police_station": rec["police_station"],
            "hour_of_day": rec["hour_of_day"],
            "day_of_week": rec["day_of_week"],
            "avg_concurrent": rec["avg_concurrent"],
            "max_concurrent": rec["max_concurrent"],
        }
        for rec in data.values()
    ]

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i: i + BATCH_SIZE]
        stmt = pg_insert(StationConcurrency).values(batch)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_station_hour_dow")
        session.execute(stmt)
    session.commit()
    print(f"[seed] Station concurrency records: {len(rows):,}")
    return len(rows)


def seed_duration_lookup(session) -> int:
    path = ARTIFACT_DIR / "duration_lookup.json"
    print(f"\n[seed] Loading duration lookup from {path} …")
    with open(path) as f:
        data = json.load(f)

    rows = [
        {
            "event_cause": cause,
            "median_duration_mins": rec["median"],
            "p25_duration_mins": rec["p25"],
            "p75_duration_mins": rec["p75"],
            "sample_count": rec["count"],
        }
        for cause, rec in data.items()
    ]

    stmt = pg_insert(DurationLookup).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["event_cause"],
        set_={"median_duration_mins": stmt.excluded.median_duration_mins},
    )
    session.execute(stmt)
    session.commit()
    print(f"[seed] Duration lookup records: {len(rows)}")
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Seed GridSense database")
    parser.add_argument("--truncate", action="store_true",
                        help="Truncate all tables before seeding")
    args = parser.parse_args()

    print("=" * 60)
    print("GridSense — Database Seed")
    print("=" * 60)

    required = [
        CLEAN_CSV,
        ARTIFACT_DIR / "corridor_risk_index.json",
        ARTIFACT_DIR / "station_map.json",
        ARTIFACT_DIR / "station_concurrency.json",
        ARTIFACT_DIR / "duration_lookup.json",
    ]
    missing = [p for p in required if not p.exists()]
    if missing:
        print(f"[seed] ERROR: Missing files:")
        for p in missing:
            print(f"  ❌ {p}")
        sys.exit(1)

    engine = get_engine()
    ensure_tables_exist(engine)

    SessionLocal = get_session_local()
    session = SessionLocal()

    try:
        if args.truncate:
            truncate_all(session)

        seed_incidents(session)
        seed_corridor_risk(session)
        seed_station_map(session)
        seed_station_concurrency(session)
        seed_duration_lookup(session)

        print("\n" + "=" * 60)
        print("✅ Database seeded successfully.")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"\n[seed] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()