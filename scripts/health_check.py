"""
health_check.py — Verify all GridSense ML artifacts exist and are loadable.

Returns exit code 0 if all required artifacts are present and loadable.
Returns exit code 1 if any are missing or corrupt.

Run:
    python scripts/health_check.py
    python scripts/health_check.py --verbose
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ARTIFACT_DIR = ROOT / "ml" / "artifacts"

REQUIRED_JSON = [
    "duration_lookup.json",
    "corridor_risk_index.json",
    "station_map.json",
    "station_concurrency.json",
    "blackspot_scores.json",
    "neglect_index.json",
    "cascade_multipliers.json",
    "corridor_adjacency.json",
    "surge_profile.json",
    "surge_replay_march7.json",
]

REQUIRED_PKL = [
    "encoders.pkl",
    "closure_model.pkl",
    "priority_model.pkl",
]

MIN_PROPHET_MODELS = 10  # Minimum junction models expected


def check_json_artifact(path: Path, verbose: bool) -> bool:
    if not path.exists():
        print(f"  ❌ MISSING   {path.name}")
        return False
    try:
        with open(path) as f:
            data = json.load(f)
        size_kb = path.stat().st_size / 1024
        entries = len(data) if isinstance(data, dict) else len(data)
        if verbose:
            print(f"  ✅ OK        {path.name}  ({size_kb:.1f} KB, {entries} entries)")
        else:
            print(f"  ✅ {path.name}")
        return True
    except Exception as e:
        print(f"  ❌ CORRUPT   {path.name}: {e}")
        return False


def check_pkl_artifact(path: Path, verbose: bool) -> bool:
    if not path.exists():
        print(f"  ❌ MISSING   {path.name}")
        return False
    try:
        import joblib
        obj = joblib.load(path)
        size_kb = path.stat().st_size / 1024
        obj_type = type(obj).__name__
        if verbose:
            print(f"  ✅ OK        {path.name}  ({size_kb:.1f} KB, type={obj_type})")
        else:
            print(f"  ✅ {path.name}")
        return True
    except Exception as e:
        print(f"  ❌ CORRUPT   {path.name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="GridSense artifact health check")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("=" * 55)
    print("GridSense — Artifact Health Check")
    print("=" * 55)

    all_ok = True

    print("\n-- JSON Artifacts --")
    for fname in REQUIRED_JSON:
        ok = check_json_artifact(ARTIFACT_DIR / fname, args.verbose)
        all_ok = all_ok and ok

    print("\n-- PKL Artifacts --")
    for fname in REQUIRED_PKL:
        ok = check_pkl_artifact(ARTIFACT_DIR / fname, args.verbose)
        all_ok = all_ok and ok

    print("\n-- Prophet Models --")
    prophet_dir = ARTIFACT_DIR / "prophet_models"
    if prophet_dir.exists():
        models = list(prophet_dir.glob("*.pkl"))
        if len(models) >= MIN_PROPHET_MODELS:
            print(f"  OK {len(models)} junction models found")
            if args.verbose:
                for m in sorted(models):
                    size_kb = m.stat().st_size / 1024
                    print(f"     {m.stem}  ({size_kb:.0f} KB)")
        else:
            print(f"  WARN  Only {len(models)} prophet models found (expected >= {MIN_PROPHET_MODELS})")
            print(f"     Run: python ml/pipeline/06_train_forecast.py")
            # Not a hard failure — backend can serve without forecasts
    else:
        print(f"  WARN  prophet_models/ directory not found")
        print(f"     Run: python ml/pipeline/06_train_forecast.py")

    print("\n-- Summary --")
    if all_ok:
        print("  OK All required artifacts present and loadable.")
        print("  OK Backend can start.")
        sys.exit(0)
    else:
        print("  FAIL Some artifacts missing or corrupt.")
        print("  FAIL Run: bash scripts/run_pipeline.sh")
        sys.exit(1)


if __name__ == "__main__":
    main()