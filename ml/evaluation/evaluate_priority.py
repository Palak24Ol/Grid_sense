"""
evaluate_priority.py — Evaluate the priority classifier (Random Forest).

Prints: overall accuracy, Non-corridor subset accuracy, classification report,
and top-10 feature importances.

Run:
    python ml/evaluation/evaluate_priority.py
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).parent.parent.parent
FEATURE_CSV = ROOT / "data" / "processed" / "feature_matrix.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "priority_model.pkl"

FEATURE_COLS = [
    "corridor_encoded", "event_cause_encoded", "vehicle_type_encoded",
    "hour_of_day", "day_of_week", "month",
    "hour_sin", "hour_cos",
    "is_high_priority_corridor", "is_non_corridor",
    "has_vehicle_type", "has_zone",
]


def main():
    print("=" * 60)
    print("GridSense — Evaluate Priority Classifier (Random Forest)")
    print("=" * 60)

    if not MODEL_PATH.exists():
        print(f"ERROR: {MODEL_PATH} not found. Run 04_train_priority.py first.")
        sys.exit(1)

    if not FEATURE_CSV.exists():
        print(f"ERROR: {FEATURE_CSV} not found. Run 02_feature_engineer.py first.")
        sys.exit(1)

    model = joblib.load(MODEL_PATH)
    print(f"Model loaded: {type(model).__name__}")

    df = pd.read_csv(FEATURE_CSV, low_memory=False)
    df = df[df["is_stale_active"] == 0]
    X = df[FEATURE_COLS]
    y = df["y_priority"]
    is_nc = df["is_non_corridor"]

    _, X_test, _, y_test, _, nc_test = train_test_split(
        X, y, is_nc, test_size=0.2, random_state=42, stratify=y
    )

    preds = model.predict(X_test)

    # Overall accuracy
    overall_acc = accuracy_score(y_test, preds)
    print(f"\nOverall Accuracy: {overall_acc:.4f}")
    print(f"\nClassification Report:")
    print(classification_report(y_test, preds, target_names=["Low", "High"], zero_division=0))

    cm = confusion_matrix(y_test, preds)
    print(f"Confusion Matrix:\n  TN={cm[0,0]}  FP={cm[0,1]}\n  FN={cm[1,0]}  TP={cm[1,1]}")

    # Non-corridor subset — the core disagreement flag use case
    nc_mask = nc_test == 1
    nc_count = int(nc_mask.sum())
    print(f"\n── Non-corridor Subset ({nc_count} test records) ──")
    if nc_count > 0:
        nc_acc = accuracy_score(y_test[nc_mask], preds[nc_mask])
        nc_high_rate = float(y_test[nc_mask].mean())
        print(f"  Historical High priority rate: {nc_high_rate*100:.1f}%")
        print(f"  Model accuracy on Non-corridor: {nc_acc:.4f}")
        print(f"  Non-corridor Classification Report:")
        print(classification_report(
            y_test[nc_mask], preds[nc_mask],
            target_names=["Low", "High"], zero_division=0
        ))
        # Disagreement cases: model predicted High, historical was Low
        predicted_high_nc = ((preds[nc_mask] == 1) & (y_test[nc_mask] == 0)).sum()
        print(f"  Disagreement flag would fire for: {predicted_high_nc} incidents")
        print(f"  (Non-corridor incidents our model elevates to High vs historical Low)")

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