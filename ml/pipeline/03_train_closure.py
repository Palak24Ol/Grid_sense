"""
03_train_closure.py — Train XGBoost Road Closure Predictor (v3).

v3 improvements over v2:
  - TIME-BASED train/val/test split (fixes temporal leakage from random split)
  - New features: dow_sin, dow_cos, corridor_events_4h, corridor_events_24h, is_rush_hour
  - SHAP feature importance saved to CSV
  - Baseline comparisons (majority class, rule-based) printed
  - Split indices saved for evaluation scripts

Inputs:
    data/processed/feature_matrix.csv
    data/processed/events_clean.csv   (for lat/lon + raw label columns)

Outputs:
    ml/artifacts/closure_model.pkl
    ml/artifacts/closure_meta.json        (threshold, feature list, metrics)
    ml/artifacts/closure_split.json       (train/val/test indices)
    ml/artifacts/closure_shap.csv         (SHAP feature importances)
    ml/artifacts/closure_encoding_lookups.json

Run:
    python ml/pipeline/03_train_closure.py
"""

import json
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score, f1_score, precision_score,
    recall_score, confusion_matrix, average_precision_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

ROOT         = Path(__file__).parent.parent.parent
FEATURE_CSV  = ROOT / "data" / "processed" / "feature_matrix.csv"
CLEAN_CSV    = ROOT / "data" / "processed" / "events_clean.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
OUT_MODEL    = ARTIFACT_DIR / "closure_model.pkl"
OUT_META     = ARTIFACT_DIR / "closure_meta.json"

# Base features from feature_matrix.csv
BASE_FEATURE_COLS = [
    "corridor_encoded", "event_cause_encoded", "vehicle_type_encoded",
    "hour_of_day", "day_of_week", "month",
    "hour_sin", "hour_cos",
    "dow_sin", "dow_cos",
    "is_high_priority_corridor", "is_non_corridor",
    "has_vehicle_type", "has_zone",
    "police_station_encoded", "zone_encoded",
    "is_rush_hour", "corridor_events_4h", "corridor_events_24h",
]

# Spatial + derived features (added by this script at train time)
NEW_FEATURE_COLS = [
    "lat_bin", "lon_bin",
    "cause_closure_rate",
    "station_priority_rate",
    "is_daytime",
]

FEATURE_COLS = BASE_FEATURE_COLS + NEW_FEATURE_COLS

XGBOOST_PARAMS = {
    "n_estimators": 1000,
    "max_depth": 6,
    "learning_rate": 0.02,
    "subsample": 0.8,
    "colsample_bytree": 0.7,
    "min_child_weight": 3,
    "gamma": 1,
    "eval_metric": "aucpr",
    "random_state": 42,
    "use_label_encoder": False,
    "verbosity": 0,
    "n_jobs": -1,
}


def engineer_features(fm: pd.DataFrame, clean: pd.DataFrame) -> pd.DataFrame:
    """Join new spatial & encoded features onto the feature matrix."""
    clean = clean.copy()
    clean["lat_bin"] = ((clean["latitude"] - 12.8) / 0.05).astype(int).clip(0, 15)
    clean["lon_bin"] = ((clean["longitude"] - 77.3) / 0.05).astype(int).clip(0, 15)
    clean["is_daytime"] = clean["hour_of_day"].between(8, 20).astype(int)

    spatial = clean[["id", "lat_bin", "lon_bin", "is_daytime"]].copy()
    merged = fm.merge(spatial, on="id", how="left")
    merged["lat_bin"]    = merged["lat_bin"].fillna(7).astype(int)
    merged["lon_bin"]    = merged["lon_bin"].fillna(5).astype(int)
    merged["is_daytime"] = merged["is_daytime"].fillna(0).astype(int)
    return merged


def add_target_encoded_features(df: pd.DataFrame, fm_labels: pd.DataFrame, train_idx, val_idx):
    """
    Compute cause_closure_rate and station_priority_rate from TRAIN rows only
    then apply to both train and val — avoids leakage.
    fm_labels must have y_closure, y_priority, event_cause, corridor columns.
    """
    train_labels = fm_labels.iloc[train_idx]

    # Cause → closure rate
    cause_rate = (
        train_labels.groupby("event_cause")["y_closure"]
        .mean()
        .to_dict()
    )
    global_rate = train_labels["y_closure"].mean()
    df["cause_closure_rate"] = fm_labels["event_cause"].map(cause_rate).fillna(global_rate).values

    # Corridor → historical priority rate (proxy for location severity)
    station_rate = (
        train_labels.groupby("corridor")["y_priority"]
        .mean()
        .to_dict()
    )
    df["station_priority_rate"] = fm_labels["corridor"].map(station_rate).fillna(0.5).values

    return df


def tune_threshold(proba: np.ndarray, y_true: np.ndarray) -> float:
    """Pick threshold maximising F1 on provided set."""
    best_f1, best_t = 0, 0.35
    for t in np.arange(0.20, 0.65, 0.01):
        preds = (proba >= t).astype(int)
        f1 = f1_score(y_true, preds, zero_division=0)
        if f1 > best_f1:
            best_f1, best_t = f1, t
    return round(float(best_t), 2)


def main():
    print("=" * 60)
    print("GridSense v2 — Train Closure Model (XGBoost + spatial features)")
    print("=" * 60)

    if not FEATURE_CSV.exists() or not CLEAN_CSV.exists():
        print("ERROR: Run 01_ingest + 02_feature_engineer first.")
        sys.exit(1)

    fm    = pd.read_csv(FEATURE_CSV, low_memory=False)
    clean = pd.read_csv(CLEAN_CSV,   low_memory=False)

    fm    = fm[fm["is_stale_active"] == 0].reset_index(drop=True)
    print(f"Rows after stale filter: {len(fm):,}")

    fm = engineer_features(fm, clean)

    # Keep raw cols for target encoding, select features after
    raw_cols = [c for c in FEATURE_COLS if c not in ["cause_closure_rate", "station_priority_rate"]]
    X_raw    = fm[raw_cols + ["event_cause", "corridor"]].copy()
    y_all    = fm["y_closure"].copy()
    y_pri    = fm["y_priority"].copy()

    pos = int(y_all.sum())
    neg = int((y_all == 0).sum())
    print(f"Closure class dist — pos: {pos:,}  neg: {neg:,}  pos_rate: {pos/len(y_all)*100:.1f}%")

    # TIME-BASED split (fixes temporal leakage from random split)
    fm["start_datetime"] = pd.to_datetime(fm["start_datetime"], format="mixed", utc=True, errors="coerce")
    sort_order = fm["start_datetime"].argsort().values
    n = len(X_raw)
    train_end = int(n * 0.68)
    val_end = int(n * 0.85)
    train_idx = sort_order[:train_end]
    val_idx = sort_order[train_end:val_end]
    test_idx = sort_order[val_end:]

    # Add target-encoded features (leak-free) — now columns exist in fm_aug
    fm_labels = fm[["event_cause", "corridor", "y_closure", "y_priority"]].copy()
    fm_aug = add_target_encoded_features(X_raw.copy(), fm_labels, train_idx, val_idx)
    X_feat = fm_aug[FEATURE_COLS]

    X_train = X_feat.iloc[train_idx]
    y_train = y_all.iloc[train_idx]
    X_val   = X_feat.iloc[val_idx]
    y_val   = y_all.iloc[val_idx]
    X_test  = X_feat.iloc[test_idx]
    y_test  = y_all.iloc[test_idx]

    print(f"Train: {len(X_train):,}  Val: {len(X_val):,}  Test: {len(X_test):,}")

    # Try SMOTE if available, fallback to scale_pos_weight
    try:
        from imblearn.over_sampling import SMOTE
        sm = SMOTE(random_state=42, k_neighbors=3)
        X_res, y_res = sm.fit_resample(X_train, y_train)
        print(f"SMOTE applied: {len(X_res):,} rows (pos_rate={y_res.mean()*100:.1f}%)")
        spw = 1.0
    except ImportError:
        print("imbalanced-learn not found — using scale_pos_weight instead")
        X_res, y_res = X_train, y_train
        spw = neg / max(pos, 1)

    params = {**XGBOOST_PARAMS, "scale_pos_weight": spw}
    print(f"\nTraining XGBoost (n_estimators={params['n_estimators']}, scale_pos_weight={spw:.2f}) …")
    model = XGBClassifier(**params)
    model.fit(
        X_res, y_res,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    # Tune threshold on validation set
    val_proba = model.predict_proba(X_val)[:, 1]
    best_threshold = tune_threshold(val_proba, y_val)
    print(f"\nBest threshold (from val F1 search): {best_threshold}")

    # Evaluate on held-out test set
    test_proba = model.predict_proba(X_test)[:, 1]
    auc    = roc_auc_score(y_test, test_proba)
    auc_pr = average_precision_score(y_test, test_proba)
    print(f"\n{'='*40}")
    print(f"  AUC-ROC:          {auc:.4f}")
    print(f"  AUC-PR:           {auc_pr:.4f}  (more informative for imbalanced)")

    for thresh in [0.5, best_threshold]:
        preds = (test_proba >= thresh).astype(int)
        p  = precision_score(y_test, preds, zero_division=0)
        r  = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)
        cm = confusion_matrix(y_test, preds)
        print(f"\n  Threshold = {thresh}:")
        print(f"    Precision: {p:.4f}  Recall: {r:.4f}  F1: {f1:.4f}")
        print(f"    CM: TN={cm[0,0]}  FP={cm[0,1]}  FN={cm[1,0]}  TP={cm[1,1]}")

    # ── Baseline comparisons ──────────────────────────────────────────────
    preds_best = (test_proba >= best_threshold).astype(int)
    f1_best = f1_score(y_test, preds_best, zero_division=0)

    # Majority class baseline (always predict 0 = no closure)
    majority_f1 = f1_score(y_test, np.zeros(len(y_test)), zero_division=0)

    # Rule-based baseline: event_cause in [accident, tree_fall, public_event] → closure
    rule_causes = {"accident", "tree_fall", "public_event", "protest", "procession"}
    rule_preds = fm["event_cause"].iloc[test_idx].isin(rule_causes).astype(int).values
    rule_f1 = f1_score(y_test, rule_preds, zero_division=0)

    print(f"\n  ── Baseline Comparison ──")
    print(f"    Majority class F1:  {majority_f1:.4f}")
    print(f"    Rule-based F1:      {rule_f1:.4f}")
    print(f"    XGBoost F1:         {f1_best:.4f}")
    if rule_f1 > 0:
        print(f"    Improvement over rule: {(f1_best - rule_f1) / rule_f1 * 100:+.1f}%")

    # ── Feature importances ──────────────────────────────────────────────
    print("\n  Feature importances (top 15):")
    importances = model.feature_importances_
    feat_imp = sorted(zip(FEATURE_COLS, importances), key=lambda x: -x[1])
    for feat, imp in feat_imp[:15]:
        bar = "█" * int(imp * 80)
        print(f"    {feat:<35} {imp:.4f}  {bar}")

    # ── SHAP explainability ──────────────────────────────────────────────
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_test)
        shap_importance = pd.DataFrame({
            "feature": FEATURE_COLS,
            "mean_abs_shap": np.abs(shap_values).mean(axis=0)
        }).sort_values("mean_abs_shap", ascending=False)
        shap_importance.to_csv(ARTIFACT_DIR / "closure_shap.csv", index=False)
        print(f"\n  SHAP importances saved → closure_shap.csv")
        print("  Top 5 SHAP features:")
        for _, row in shap_importance.head(5).iterrows():
            print(f"    {row['feature']:<35} {row['mean_abs_shap']:.4f}")
    except ImportError:
        print("\n  shap not installed — skipping SHAP analysis")
    except Exception as e:
        print(f"\n  SHAP failed: {e}")

    # ── Save split indices ───────────────────────────────────────────────
    split_info = {
        "method": "time_based",
        "train_size": len(train_idx),
        "val_size": len(val_idx),
        "test_size": len(test_idx),
        "train_indices": train_idx.tolist(),
        "val_indices": val_idx.tolist(),
        "test_indices": test_idx.tolist(),
    }
    with open(ARTIFACT_DIR / "closure_split.json", "w") as f:
        json.dump(split_info, f)
    print(f"  Split indices saved → closure_split.json")

    # ── Save model + metadata ────────────────────────────────────────────
    joblib.dump(model, OUT_MODEL)
    meta = {
        "threshold":    best_threshold,
        "feature_cols": FEATURE_COLS,
        "auc_roc":      round(auc, 4),
        "auc_pr":       round(auc_pr, 4),
        "f1":           round(f1_best, 4),
        "baseline_rule_f1": round(rule_f1, 4),
        "split_method": "time_based",
        "version":      "v3",
    }
    with open(OUT_META, "w") as f:
        json.dump(meta, f, indent=2)

    # Export target-encoding lookups so inference doesn't need the raw CSV
    train_labels_full = fm_labels.iloc[train_idx]
    cause_lookup = train_labels_full.groupby("event_cause")["y_closure"].mean().to_dict()
    cause_lookup["__default__"] = float(train_labels_full["y_closure"].mean())
    station_lookup = train_labels_full.groupby("corridor")["y_priority"].mean().to_dict()
    station_lookup["__default__"] = 0.5

    encoding_lookups = {
        "cause_closure_rate":    {k: round(float(v), 4) for k, v in cause_lookup.items()},
        "station_priority_rate": {k: round(float(v), 4) for k, v in station_lookup.items()},
    }
    with open(ARTIFACT_DIR / "closure_encoding_lookups.json", "w") as f:
        json.dump(encoding_lookups, f, indent=2)
    print(f"Encoding lookups → {ARTIFACT_DIR / 'closure_encoding_lookups.json'}")

    print(f"\nModel saved → {OUT_MODEL}  ({OUT_MODEL.stat().st_size/1024:.1f} KB)")
    print(f"Meta saved  → {OUT_META}")
    print("\n✅ Done.")


if __name__ == "__main__":
    main()