"""
03_train_closure.py — Train XGBoost Road Closure Predictor (Model 1).

Handles 91.7%/8.3% class imbalance via scale_pos_weight.
Uses threshold=0.35 (lower than default 0.5) to improve recall.

Inputs:
    data/processed/feature_matrix.csv

Outputs:
    ml/artifacts/closure_model.pkl

Run:
    python ml/pipeline/03_train_closure.py
"""

import sys
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    roc_auc_score,
    f1_score,
    precision_score,
    recall_score,
    confusion_matrix,
    classification_report,
)
from xgboost import XGBClassifier

ROOT = Path(__file__).parent.parent.parent
FEATURE_CSV = ROOT / "data" / "processed" / "feature_matrix.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
OUT_MODEL = ARTIFACT_DIR / "closure_model.pkl"

CLOSURE_THRESHOLD = 0.35

FEATURE_COLS = [
    "corridor_encoded",
    "event_cause_encoded",
    "vehicle_type_encoded",
    "hour_of_day",
    "day_of_week",
    "month",
    "hour_sin",
    "hour_cos",
    "is_high_priority_corridor",
    "is_non_corridor",
    "has_vehicle_type",
    "has_zone",
]

XGBOOST_PARAMS = {
    "n_estimators": 800,
    "max_depth": 7,
    "learning_rate": 0.03,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "eval_metric": "auc",
    "random_state": 42,
    "use_label_encoder": False,
    "verbosity": 0,
}


def load_features(path: Path) -> tuple[pd.DataFrame, pd.Series]:
    print(f"[03_closure] Loading feature matrix from {path} …")
    df = pd.read_csv(path, low_memory=False)
    # Exclude stale-active incidents from training
    df = df[df["is_stale_active"] == 0]
    print(f"[03_closure] Rows after stale filter: {len(df):,}")

    missing_cols = [c for c in FEATURE_COLS if c not in df.columns]
    if missing_cols:
        print(f"[03_closure] ERROR: Missing feature columns: {missing_cols}")
        sys.exit(1)

    X = df[FEATURE_COLS].copy()
    y = df["y_closure"].copy()

    pos = int(y.sum())
    neg = int((y == 0).sum())
    print(f"[03_closure] Class distribution — positive (closure): {pos:,}  negative: {neg:,}")
    print(f"[03_closure] Positive rate: {pos / len(y) * 100:.1f}%")
    return X, y


def train(X_train, y_train, scale_pos_weight: float) -> XGBClassifier:
    params = {**XGBOOST_PARAMS, "scale_pos_weight": scale_pos_weight}
    print(f"\n[03_closure] Training XGBoost with scale_pos_weight={scale_pos_weight:.2f} …")
    model = XGBClassifier(**params)
    model.fit(X_train, y_train, eval_set=[(X_train, y_train)], verbose=False)
    return model


def evaluate(model: XGBClassifier, X_test: pd.DataFrame, y_test: pd.Series) -> None:
    print("\n[03_closure] ── Evaluation ──")
    proba = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, proba)
    print(f"  AUC-ROC: {auc:.4f}")

    # Evaluate at both default and chosen threshold
    for thresh in [0.5, CLOSURE_THRESHOLD]:
        preds = (proba >= thresh).astype(int)
        p = precision_score(y_test, preds, zero_division=0)
        r = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)
        cm = confusion_matrix(y_test, preds)
        print(f"\n  Threshold = {thresh}:")
        print(f"    Precision: {p:.4f}  Recall: {r:.4f}  F1: {f1:.4f}")
        print(f"    Confusion matrix:\n      {cm}")

    # Feature importance
    print("\n  Top 10 feature importances:")
    importances = model.feature_importances_
    feat_imp = sorted(zip(FEATURE_COLS, importances), key=lambda x: -x[1])
    for feat, imp in feat_imp[:10]:
        print(f"    {feat}: {imp:.4f}")


def main():
    print("=" * 60)
    print("GridSense — Step 3: Train Closure Model (XGBoost)")
    print("=" * 60)

    if not FEATURE_CSV.exists():
        print(f"[03_closure] ERROR: {FEATURE_CSV} not found. Run 02_feature_engineer.py first.")
        sys.exit(1)

    X, y = load_features(FEATURE_CSV)

    neg = int((y == 0).sum())
    pos = int(y.sum())
    scale_pos_weight = neg / max(pos, 1)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"[03_closure] Train: {len(X_train):,}  Test: {len(X_test):,}")

    model = train(X_train, y_train, scale_pos_weight)
    evaluate(model, X_test, y_test)

    joblib.dump(model, OUT_MODEL)
    print(f"\n[03_closure] Model saved → {OUT_MODEL}")
    print(f"[03_closure] Model file size: {OUT_MODEL.stat().st_size / 1024:.1f} KB")
    print("\n[03_closure] ✅ Done.")


if __name__ == "__main__":
    main()