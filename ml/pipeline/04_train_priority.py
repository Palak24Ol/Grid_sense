"""
04_train_priority.py — Train Random Forest Priority Classifier (Model 3).

Also reports Non-corridor subset accuracy separately — this is the
disagreement flag use case where historical ops defaulted to Low priority.

Inputs:
    data/processed/feature_matrix.csv

Outputs:
    ml/artifacts/priority_model.pkl

Run:
    python ml/pipeline/04_train_priority.py
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)

ROOT = Path(__file__).parent.parent.parent
FEATURE_CSV = ROOT / "data" / "processed" / "feature_matrix.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
OUT_MODEL = ARTIFACT_DIR / "priority_model.pkl"

FEATURE_COLS = [
    "event_cause_encoded",
    "vehicle_type_encoded",
    "hour_of_day",
    "day_of_week",
    "month",
    "hour_sin",
    "hour_cos",
    "is_high_priority_corridor",
    "has_vehicle_type",
    "has_zone",
]

RF_PARAMS = {
    "n_estimators": 200,
    "max_depth": 10,
    "min_samples_leaf": 5,
    "class_weight": "balanced",
    "random_state": 42,
    "n_jobs": -1,
}


def load_features(path: Path):
    print(f"[04_priority] Loading feature matrix from {path} …")
    df = pd.read_csv(path, low_memory=False)
    # Exclude stale-active
    df = df[df["is_stale_active"] == 0]
    print(f"[04_priority] Rows after stale filter: {len(df):,}")

    missing_cols = [c for c in FEATURE_COLS if c not in df.columns]
    if missing_cols:
        print(f"[04_priority] ERROR: Missing feature columns: {missing_cols}")
        sys.exit(1)

    X = df[FEATURE_COLS].copy()
    y = df["y_priority"].copy()
    is_non_corridor = df["is_non_corridor"].copy()

    pos = int(y.sum())
    neg = int((y == 0).sum())
    print(f"[04_priority] Class distribution — High: {pos:,}  Low: {neg:,}")
    print(f"[04_priority] High priority rate: {pos / len(y) * 100:.1f}%")
    return X, y, is_non_corridor


def train(X_train: pd.DataFrame, y_train: pd.Series) -> RandomForestClassifier:
    print(f"\n[04_priority] Training Random Forest …")
    model = RandomForestClassifier(**RF_PARAMS)
    model.fit(X_train, y_train)
    return model


def evaluate(
    model: RandomForestClassifier,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    is_non_corridor_test: pd.Series,
) -> None:
    print("\n[04_priority] ── Evaluation ──")

    preds = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]

    # Overall accuracy
    overall_acc = accuracy_score(y_test, preds)
    print(f"  Overall accuracy: {overall_acc:.4f}")
    print(f"\n  Classification report (overall):")
    print(classification_report(y_test, preds, target_names=["Low", "High"], zero_division=0))

    # Non-corridor subset accuracy — critical metric for GridSense's value prop
    nc_mask = is_non_corridor_test == 1
    nc_count = int(nc_mask.sum())
    if nc_count > 0:
        nc_acc = accuracy_score(y_test[nc_mask], preds[nc_mask])
        nc_high_rate = float(y_test[nc_mask].mean())
        print(f"  Non-corridor subset:")
        print(f"    Rows: {nc_count:,}  Historical High rate: {nc_high_rate*100:.1f}%")
        print(f"    Accuracy on Non-corridor: {nc_acc:.4f}")
        print(f"    (Note: Operational baseline defaults to Low priority for all Non-corridor)")
        print(f"    Classification report (Non-corridor only):")
        print(classification_report(
            y_test[nc_mask], preds[nc_mask],
            target_names=["Low", "High"], zero_division=0
        ))

    # Feature importance
    print("  Top 10 feature importances:")
    importances = model.feature_importances_
    feat_imp = sorted(zip(FEATURE_COLS, importances), key=lambda x: -x[1])
    for feat, imp in feat_imp[:10]:
        print(f"    {feat}: {imp:.4f}")


def main():
    print("=" * 60)
    print("GridSense — Step 4: Train Priority Classifier (Random Forest)")
    print("=" * 60)

    if not FEATURE_CSV.exists():
        print(f"[04_priority] ERROR: {FEATURE_CSV} not found. Run 02_feature_engineer.py first.")
        sys.exit(1)

    X, y, is_non_corridor = load_features(FEATURE_CSV)

    X_train, X_test, y_train, y_test, nc_train, nc_test = train_test_split(
        X, y, is_non_corridor, test_size=0.2, random_state=42, stratify=y
    )
    print(f"[04_priority] Train: {len(X_train):,}  Test: {len(X_test):,}")
    print(f"[04_priority] Non-corridor in test set: {int(nc_test.sum()):,}")

    # FIX: Train priority model ONLY on named corridors to remove operational bias
    # This forces the model to learn severity from 'event_cause' rather than 'is_non_corridor'
    corridor_mask = nc_train == 0
    X_train_unbiased = X_train[corridor_mask].copy()
    y_train_unbiased = y_train[corridor_mask].copy()
    
    # Also drop 'corridor_encoded' and 'is_non_corridor' so the model doesn't use location as a crutch
    # (Optional, but if we drop them we must drop them everywhere. We'll just train on unbiased data)
    
    model = train(X_train_unbiased, y_train_unbiased)
    evaluate(model, X_test, y_test, nc_test)

    joblib.dump(model, OUT_MODEL)
    print(f"\n[04_priority] Model saved → {OUT_MODEL}")
    print(f"[04_priority] Model file size: {OUT_MODEL.stat().st_size / 1024:.1f} KB")
    print("\n[04_priority] ✅ Done.")


if __name__ == "__main__":
    main()