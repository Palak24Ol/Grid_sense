"""
evaluate_closure.py — Evaluate the closure model (XGBoost).

Prints: AUC-ROC, precision, recall, F1 at threshold=0.35, confusion matrix,
feature importances.

Run:
    python ml/evaluation/evaluate_closure.py
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score,
    f1_score,
    precision_score,
    recall_score,
    confusion_matrix,
    roc_curve,
)
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).parent.parent.parent
FEATURE_CSV = ROOT / "data" / "processed" / "feature_matrix.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "closure_model.pkl"
THRESHOLD = 0.35

FEATURE_COLS = [
    "corridor_encoded", "event_cause_encoded", "vehicle_type_encoded",
    "hour_of_day", "day_of_week", "month",
    "hour_sin", "hour_cos",
    "is_high_priority_corridor", "is_non_corridor",
    "has_vehicle_type", "has_zone",
]


def main():
    print("=" * 60)
    print("GridSense — Evaluate Closure Model (XGBoost)")
    print("=" * 60)

    if not MODEL_PATH.exists():
        print(f"ERROR: {MODEL_PATH} not found. Run 03_train_closure.py first.")
        sys.exit(1)

    if not FEATURE_CSV.exists():
        print(f"ERROR: {FEATURE_CSV} not found. Run 02_feature_engineer.py first.")
        sys.exit(1)

    model = joblib.load(MODEL_PATH)
    print(f"Model loaded: {type(model).__name__}")

    df = pd.read_csv(FEATURE_CSV, low_memory=False)
    df = df[df["is_stale_active"] == 0]
    X = df[FEATURE_COLS]
    y = df["y_closure"]

    _, X_test, _, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    proba = model.predict_proba(X_test)[:, 1]

    # AUC
    auc = roc_auc_score(y_test, proba)
    print(f"\nAUC-ROC: {auc:.4f}")

    # Evaluate at both thresholds
    for thresh in [0.5, THRESHOLD]:
        preds = (proba >= thresh).astype(int)
        p = precision_score(y_test, preds, zero_division=0)
        r = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)
        cm = confusion_matrix(y_test, preds)
        print(f"\n── Threshold = {thresh} ──")
        print(f"  Precision: {p:.4f}")
        print(f"  Recall:    {r:.4f}")
        print(f"  F1 Score:  {f1:.4f}")
        print(f"  Confusion Matrix:\n    TN={cm[0,0]}  FP={cm[0,1]}\n    FN={cm[1,0]}  TP={cm[1,1]}")

    # Feature importances
    print("\n── Feature Importances (top 12) ──")
    importances = model.feature_importances_
    feat_imp = sorted(zip(FEATURE_COLS, importances), key=lambda x: -x[1])
    for feat, imp in feat_imp:
        bar = "█" * int(imp * 100)
        print(f"  {feat:<35} {imp:.4f}  {bar}")

    print("\n✅ Evaluation complete.")


if __name__ == "__main__":
    main()