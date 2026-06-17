#!/usr/bin/env bash
# run_pipeline.sh — End-to-end ML pipeline for GridSense
#
# Usage:
#   bash scripts/run_pipeline.sh              # Full pipeline
#   bash scripts/run_pipeline.sh --json-only  # Steps 1, 5, 7 only (unblocks backend)
#   bash scripts/run_pipeline.sh --skip-prophet  # Skip slow Prophet training

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

JSON_ONLY=false
SKIP_PROPHET=false

for arg in "$@"; do
  case $arg in
    --json-only)      JSON_ONLY=true ;;
    --skip-prophet)   SKIP_PROPHET=true ;;
  esac
done

echo "========================================================"
echo "GridSense — ML Pipeline"
echo "Root: $ROOT"
echo "========================================================"

echo ""
echo "▶  Step 1: Ingest & Staleness Filter"
python ml/pipeline/01_ingest.py

if [ "$JSON_ONLY" = true ]; then
  echo ""
  echo "▶  Step 5: Duration Lookup (json-only mode)"
  python ml/pipeline/05_train_duration.py

  echo ""
  echo "▶  Step 7: Export JSON Artifacts (--json-only)"
  python ml/pipeline/07_export_artifacts.py --json-only

  echo ""
  echo "✅ JSON-only pipeline complete."
  echo "   Backend can now be seeded and started."
  echo "   Run full pipeline later: bash scripts/run_pipeline.sh"
  exit 0
fi

echo ""
echo "▶  Step 2: Feature Engineering"
python ml/pipeline/02_feature_engineer.py

echo ""
echo "▶  Step 3: Train Closure Model (XGBoost)"
python ml/pipeline/03_train_closure.py

echo ""
echo "▶  Step 4: Train Priority Classifier (Random Forest)"
python ml/pipeline/04_train_priority.py

echo ""
echo "▶  Step 5: Duration Lookup Table"
python ml/pipeline/05_train_duration.py

if [ "$SKIP_PROPHET" = false ]; then
  echo ""
  echo "▶  Step 6: Train Prophet Junction Forecasters (this may take 5–10 minutes)"
  python ml/pipeline/06_train_forecast.py
else
  echo ""
  echo "⏭  Step 6: Prophet training skipped (--skip-prophet)"
fi

echo "[8/10] Build Chronic Blackspot Engine..."
python ml/pipeline/08_train_blackspot.py

echo "[9/10] Compute Cascade Multipliers..."
python ml/pipeline/09_train_cascade.py

echo "[10/10] Build Weather Surge Profile..."
python ml/pipeline/10_train_surge.py

echo ""
echo "▶  Step 7: Export Artifacts & Full Verification"
python ml/pipeline/07_export_artifacts.py

echo ""
echo "========================================================"
echo "✅ GridSense ML Pipeline complete."
echo "========================================================"