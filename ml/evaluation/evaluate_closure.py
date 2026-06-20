"""
evaluate_closure.py — Evaluate the closure model v2 (XGBoost).

Updated for v2 feature set:
  - Spatial features: lat_bin, lon_bin, is_daytime
  - New encoded features: police_station_encoded, zone_encoded
  - Target-encoded features: cause_closure_rate, station_priority_rate
  - Threshold loaded from closure_meta.json (tuned on val set during training)
  - Reports: AUC-ROC, AUC-PR, Precision, Recall, F1, CM at both 0.5 and tuned threshold
  - Naive baseline comparison for context

Run:
    python ml/evaluation/evaluate_closure.py
"""

import json
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    confusion_matrix,
)


warnings.filterwarnings("ignore")

ROOT         = Path(__file__).parent.parent.parent
FEATURE_CSV  = ROOT / "data" / "processed" / "feature_matrix.csv"
CLEAN_CSV    = ROOT / "data" / "processed" / "events_clean.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
MODEL_PATH   = ARTIFACT_DIR / "closure_model.pkl"
META_PATH    = ARTIFACT_DIR / "closure_meta.json"

FEATURE_COLS = [
    "corridor_encoded", "event_cause_encoded", "vehicle_type_encoded",
    "hour_of_day", "day_of_week", "month",
    "hour_sin", "hour_cos",
    "is_high_priority_corridor", "is_non_corridor",
    "has_vehicle_type", "has_zone",
    "police_station_encoded", "zone_encoded",
    "lat_bin", "lon_bin",
    "cause_closure_rate", "station_priority_rate",
    "is_daytime",
]


def engineer_spatial(fm: pd.DataFrame, clean: pd.DataFrame) -> pd.DataFrame:
    """Add spatial + temporal features from events_clean.csv."""
    c = clean.copy()
    c["lat_bin"]    = ((c["latitude"]  - 12.8) / 0.05).astype(int).clip(0, 15)
    c["lon_bin"]    = ((c["longitude"] - 77.3) / 0.05).astype(int).clip(0, 15)
    c["is_daytime"] = c["hour_of_day"].between(8, 20).astype(int)
    spatial = c[["id", "lat_bin", "lon_bin", "is_daytime"]]
    merged  = fm.merge(spatial, on="id", how="left")
    merged["lat_bin"]    = merged["lat_bin"].fillna(7).astype(int)
    merged["lon_bin"]    = merged["lon_bin"].fillna(5).astype(int)
    merged["is_daytime"] = merged["is_daytime"].fillna(0).astype(int)
    return merged


def add_target_encoded(fm: pd.DataFrame, train_idx) -> pd.DataFrame:
    """Compute cause_closure_rate and station_priority_rate from train rows only."""
    train_rows = fm.iloc[train_idx]
    cause_rate    = train_rows.groupby("event_cause")["y_closure"].mean().to_dict()
    global_rate   = train_rows["y_closure"].mean()
    station_rate  = train_rows.groupby("corridor")["y_priority"].mean().to_dict()

    fm["cause_closure_rate"]    = fm["event_cause"].map(cause_rate).fillna(global_rate).values
    fm["station_priority_rate"] = fm["corridor"].map(station_rate).fillna(0.5).values
    return fm


def main():
    print("=" * 60)
    print("GridSense v2 — Evaluate Closure Model (XGBoost)")
    print("=" * 60)

    for path, label in [(MODEL_PATH, "closure_model.pkl"), (META_PATH, "closure_meta.json"),
                        (FEATURE_CSV, "feature_matrix.csv"), (CLEAN_CSV, "events_clean.csv")]:
        if not path.exists():
            print(f"ERROR: {label} not found. Run 03_train_closure.py first.")
            sys.exit(1)

    model = joblib.load(MODEL_PATH)
    meta  = json.load(open(META_PATH))
    tuned_threshold = meta["threshold"]
    print(f"Model      : {type(model).__name__}")
    print(f"Version    : {meta.get('version', 'v1')}")
    print(f"Threshold  : {tuned_threshold}  (tuned on val set during training)")

    fm    = pd.read_csv(FEATURE_CSV, low_memory=False)
    clean = pd.read_csv(CLEAN_CSV,   low_memory=False)
    fm    = fm[fm["is_stale_active"] == 0].reset_index(drop=True)
    print(f"Rows       : {len(fm):,}")

    fm = engineer_spatial(fm, clean)

    y_all = fm["y_closure"].copy()
    pos   = int(y_all.sum())
    neg   = int((y_all == 0).sum())
    print(f"\nClass dist : closure={pos:,} ({pos/len(y_all)*100:.1f}%)  "
          f"no-closure={neg:,} ({neg/len(y_all)*100:.1f}%)")

    # Load time-based split indices
    split_path = ARTIFACT_DIR / "closure_split.json"
    if split_path.exists():
        with open(split_path) as f:
            split = json.load(f)
        test_idx = split["test_indices"]
        train_idx = split.get("train_indices", [i for i in range(len(fm)) if i not in test_idx])
        print(f"[eval_closure] Using time-based split: test set = {len(test_idx):,} rows")
        print("[eval_closure] EVALUATION ON HELD-OUT TEST SET ONLY (time-based split)")
    else:
        print("[eval_closure] WARNING: No split file found. Evaluating on FULL dataset (may include training data).")
        test_idx = list(range(len(fm)))
        train_idx = list(range(len(fm)))

    fm = add_target_encoded(fm, train_idx)

    X_test = fm[FEATURE_COLS].iloc[test_idx]
    y_test = y_all.iloc[test_idx]
    print(f"Test set   : {len(X_test):,} rows\n")

    proba = model.predict_proba(X_test)[:, 1]

    # Core metrics
    auc    = roc_auc_score(y_test, proba)
    auc_pr = average_precision_score(y_test, proba)
    print(f"  AUC-ROC  : {auc:.4f}")
    print(f"  AUC-PR   : {auc_pr:.4f}  (better metric for imbalanced data)")

    # Naive baseline: always predict the majority class probability
    naive_proba = np.full(len(y_test), y_test.mean())
    naive_auc_pr = average_precision_score(y_test, naive_proba)
    print(f"  Naive AUC-PR (baseline): {naive_auc_pr:.4f}")
    print(f"  Improvement over naive  : +{(auc_pr - naive_auc_pr):.4f}")

    for thresh in [0.5, tuned_threshold]:
        preds = (proba >= thresh).astype(int)
        p  = precision_score(y_test, preds, zero_division=0)
        r  = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)
        cm = confusion_matrix(y_test, preds)
        label = "tuned" if thresh == tuned_threshold else "default"
        print(f"\n── Threshold = {thresh} ({label}) ──")
        print(f"  Precision : {p:.4f}")
        print(f"  Recall    : {r:.4f}")
        print(f"  F1 Score  : {f1:.4f}")
        print(f"  CM        : TN={cm[0,0]}  FP={cm[0,1]}  |  FN={cm[1,0]}  TP={cm[1,1]}")
        if thresh == tuned_threshold:
            print(f"  Closures caught  : {cm[1,1]}/{cm[1,0]+cm[1,1]} "
                  f"({cm[1,1]/(cm[1,0]+cm[1,1])*100:.1f}% recall)")
            print(f"  False alarm rate : {cm[0,1]}/{cm[0,0]+cm[0,1]} "
                  f"({cm[0,1]/(cm[0,0]+cm[0,1])*100:.1f}%)")

    # Baseline comparisons
    majority_f1 = f1_score(y_test, np.zeros(len(y_test)), zero_division=0)
    rule_causes = {"accident", "tree_fall", "public_event", "protest", "procession"}
    rule_preds = fm["event_cause"].iloc[test_idx].isin(rule_causes).astype(int).values
    rule_f1 = f1_score(y_test, rule_preds, zero_division=0)
    model_f1 = f1_score(y_test, (proba >= tuned_threshold).astype(int), zero_division=0)

    print(f"\n── Baseline Comparison ──")
    print(f"  Majority class F1:  {majority_f1:.4f}")
    print(f"  Rule-based F1:      {rule_f1:.4f}")
    print(f"  XGBoost F1:         {model_f1:.4f}")

    # Feature importances
    print("\n── Feature Importances (all 19 features) ──")
    importances = model.feature_importances_
    feat_imp = sorted(zip(FEATURE_COLS, importances), key=lambda x: -x[1])
    for i, (feat, imp) in enumerate(feat_imp):
        bar = "█" * int(imp * 100)
        print(f"  {i+1:>2}. {feat:<35} {imp:.4f}  {bar}")

    print("\n✅ Closure model evaluation complete.")


if __name__ == "__main__":
    main()