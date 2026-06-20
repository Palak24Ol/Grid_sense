"""
04_train_priority.py — Train Severity Classifier v3 (XGBoost).

v3 changes:
  - TARGET: y_severity (composite score = 0.4*closure + 0.3*long_duration + 0.3*high_disruption)
    This differentiates from the closure model (03) which predicts y_closure alone.
  - TIME-BASED train/val/test split (fixes temporal leakage)
  - New features: dow_sin, dow_cos, corridor_events_4h, corridor_events_24h, is_rush_hour
  - SHAP feature importance saved
  - Baseline comparisons printed
  - Split indices saved for evaluation

Inputs:
    data/processed/feature_matrix.csv
    data/processed/events_clean.csv

Outputs:
    ml/artifacts/priority_model.pkl
    ml/artifacts/priority_meta.json
    ml/artifacts/priority_split.json
    ml/artifacts/priority_shap.csv
    ml/artifacts/priority_encoding_lookups.json

Run:
    python ml/pipeline/04_train_priority.py
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
    classification_report,
)
from sklearn.model_selection import train_test_split, StratifiedKFold
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

ROOT         = Path(__file__).parent.parent.parent
FEATURE_CSV  = ROOT / "data" / "processed" / "feature_matrix.csv"
CLEAN_CSV    = ROOT / "data" / "processed" / "events_clean.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
OUT_MODEL    = ARTIFACT_DIR / "priority_model.pkl"
OUT_META     = ARTIFACT_DIR / "priority_meta.json"

BASE_FEATURES = [
    "event_cause_encoded", "vehicle_type_encoded",
    "hour_of_day", "day_of_week", "month",
    "hour_sin", "hour_cos",
    "dow_sin", "dow_cos",
    "is_high_priority_corridor", "is_non_corridor",
    "has_vehicle_type", "has_zone",
    "police_station_encoded", "zone_encoded",
    "corridor_encoded",
    "is_rush_hour", "corridor_events_4h", "corridor_events_24h",
]

NEW_FEATURES = [
    "lat_bin", "lon_bin",
    "is_daytime", "is_planned",
    "cause_closure_rate",
    "corridor_density_log",
]

FEATURE_COLS = BASE_FEATURES + NEW_FEATURES

XGBOOST_PARAMS = {
    "n_estimators": 800,
    "max_depth": 6,
    "learning_rate": 0.025,
    "subsample": 0.8,
    "colsample_bytree": 0.7,
    "min_child_weight": 5,
    "gamma": 2,
    "eval_metric": "aucpr",
    "random_state": 42,
    "use_label_encoder": False,
    "verbosity": 0,
    "n_jobs": -1,
}


def engineer_features(fm: pd.DataFrame, clean: pd.DataFrame) -> pd.DataFrame:
    """Add spatial, temporal and event-type features."""
    clean = clean.copy()
    clean["lat_bin"]    = ((clean["latitude"] - 12.8) / 0.05).astype(int).clip(0, 15)
    clean["lon_bin"]    = ((clean["longitude"] - 77.3) / 0.05).astype(int).clip(0, 15)
    clean["is_daytime"] = clean["hour_of_day"].between(8, 20).astype(int)
    clean["is_planned"] = (clean["event_type"] == "planned").astype(int)

    # Corridor density: log(#incidents on that corridor)
    corr_density = clean["corridor"].map(clean["corridor"].value_counts())
    clean["corridor_density_log"] = np.log1p(corr_density)

    spatial = clean[["id", "lat_bin", "lon_bin", "is_daytime", "is_planned", "corridor_density_log"]]
    merged  = fm.merge(spatial, on="id", how="left")
    merged["lat_bin"]              = merged["lat_bin"].fillna(7).astype(int)
    merged["lon_bin"]              = merged["lon_bin"].fillna(5).astype(int)
    merged["is_daytime"]           = merged["is_daytime"].fillna(0).astype(int)
    merged["is_planned"]           = merged["is_planned"].fillna(0).astype(int)
    merged["corridor_density_log"] = merged["corridor_density_log"].fillna(0)
    return merged


def add_target_encoded_cause(df: pd.DataFrame, fm_labels: pd.DataFrame, train_idx) -> pd.DataFrame:
    """Encode cause → closure_rate from train rows only (no leakage)."""
    train_labels = fm_labels.iloc[train_idx]
    cause_rate   = train_labels.groupby("event_cause")["y_closure"].mean().to_dict()
    global_rate  = train_labels["y_closure"].mean()
    df["cause_closure_rate"] = fm_labels["event_cause"].map(cause_rate).fillna(global_rate).values
    return df


def tune_threshold(proba, y_true):
    best_f1, best_t = 0, 0.5
    for t in np.arange(0.20, 0.75, 0.01):
        preds = (proba >= t).astype(int)
        f1    = f1_score(y_true, preds, zero_division=0)
        if f1 > best_f1:
            best_f1, best_t = f1, t
    return round(float(best_t), 2)


def main():
    print("=" * 60)
    print("GridSense v3 — Train Severity Classifier (XGBoost)")
    print("TARGET: y_severity  (composite: closure + duration + disruption)")
    print("=" * 60)

    if not FEATURE_CSV.exists() or not CLEAN_CSV.exists():
        print("ERROR: Run 01_ingest + 02_feature_engineer first.")
        sys.exit(1)

    fm    = pd.read_csv(FEATURE_CSV, low_memory=False)
    clean = pd.read_csv(CLEAN_CSV,   low_memory=False)

    fm = fm[fm["is_stale_active"] == 0].reset_index(drop=True)
    print(f"Rows: {len(fm):,}")

    fm = engineer_features(fm, clean)

    # Target is SEVERITY (composite), not closure or priority
    y_all = fm["y_severity"].copy()
    is_nc = fm["is_non_corridor"].copy()
    # Keep raw cols (without target-encoded ones that don't exist yet)
    raw_cols = [c for c in FEATURE_COLS if c != "cause_closure_rate"]
    X_raw = fm[raw_cols + ["event_cause", "corridor"]].copy()

    pos = int(y_all.sum())
    neg = int((y_all == 0).sum())
    print(f"\nTarget: y_severity (composite)")
    print(f"  Positive (severe): {pos:,} ({pos/len(y_all)*100:.1f}%)")
    print(f"  Negative:          {neg:,} ({neg/len(y_all)*100:.1f}%)")

    # TIME-BASED split (fixes temporal leakage)
    fm["start_datetime"] = pd.to_datetime(fm["start_datetime"], format="mixed", utc=True, errors="coerce")
    sort_order = fm["start_datetime"].argsort().values
    n = len(X_raw)
    train_end = int(n * 0.68)
    val_end = int(n * 0.85)
    train_idx = sort_order[:train_end]
    val_idx = sort_order[train_end:val_end]
    test_idx = sort_order[val_end:]

    fm_labels = fm[["event_cause", "corridor", "y_closure", "y_priority", "y_severity"]].copy()
    fm_aug = add_target_encoded_cause(X_raw.copy(), fm_labels, train_idx)
    X_feat = fm_aug[FEATURE_COLS]

    X_train, y_train = X_feat.iloc[train_idx], y_all.iloc[train_idx]
    X_val,   y_val   = X_feat.iloc[val_idx],   y_all.iloc[val_idx]
    X_test,  y_test  = X_feat.iloc[test_idx],  y_all.iloc[test_idx]
    nc_test          = is_nc.iloc[test_idx]

    print(f"Train: {len(X_train):,}  Val: {len(X_val):,}  Test: {len(X_test):,}")

    spw = neg / max(pos, 1)
    print(f"\nTraining XGBoost (scale_pos_weight={spw:.2f}) …")
    params = {**XGBOOST_PARAMS, "scale_pos_weight": spw}
    model  = XGBClassifier(**params)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    # Tune threshold on val
    val_proba = model.predict_proba(X_val)[:, 1]
    best_t    = tune_threshold(val_proba, y_val)
    print(f"Best threshold (val): {best_t}")

    # Test evaluation
    test_proba = model.predict_proba(X_test)[:, 1]
    auc        = roc_auc_score(y_test, test_proba)
    auc_pr     = average_precision_score(y_test, test_proba)

    print(f"\n{'='*45}")
    print(f"  AUC-ROC: {auc:.4f}")
    print(f"  AUC-PR:  {auc_pr:.4f}")

    for thresh in [0.5, best_t]:
        preds = (test_proba >= thresh).astype(int)
        p  = precision_score(y_test, preds, zero_division=0)
        r  = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)
        cm = confusion_matrix(y_test, preds)
        print(f"\n  Threshold = {thresh}:")
        print(f"    Precision: {p:.4f}  Recall: {r:.4f}  F1: {f1:.4f}")
        print(f"    CM: TN={cm[0,0]}  FP={cm[0,1]}  FN={cm[1,0]}  TP={cm[1,1]}")

    # Non-corridor subset analysis
    nc_mask  = nc_test == 1
    nc_count = int(nc_mask.sum())
    preds_at_best = (test_proba >= best_t).astype(int)
    print(f"\n── Non-corridor Subset ({nc_count} records) ──")
    if nc_count > 0:
        nc_proba  = test_proba[nc_mask]
        nc_actual = y_test[nc_mask]
        nc_preds  = preds_at_best[nc_mask]
        nc_auc    = roc_auc_score(nc_actual, nc_proba) if nc_actual.sum() > 0 else float("nan")
        nc_f1     = f1_score(nc_actual, nc_preds, zero_division=0)
        print(f"  Closure rate (actual): {nc_actual.mean()*100:.1f}%")
        print(f"  AUC-ROC:   {nc_auc:.4f}")
        print(f"  F1:        {nc_f1:.4f}")
        print(f"  Escalation flags fired: {int(nc_preds.sum())} "
              f"(non-corridor incidents predicted to need closure)")

    # ── Baseline comparisons ──────────────────────────────────────────────
    preds_best = (test_proba >= best_t).astype(int)
    f1_best = f1_score(y_test, preds_best, zero_division=0)
    majority_f1 = f1_score(y_test, np.zeros(len(y_test)), zero_division=0)

    rule_causes = {"accident", "tree_fall", "public_event", "protest", "procession"}
    rule_preds = fm["event_cause"].iloc[test_idx].isin(rule_causes).astype(int).values
    rule_f1 = f1_score(y_test, rule_preds, zero_division=0)

    print(f"\n  ── Baseline Comparison ──")
    print(f"    Majority class F1:  {majority_f1:.4f}")
    print(f"    Rule-based F1:      {rule_f1:.4f}")
    print(f"    XGBoost F1:         {f1_best:.4f}")
    if rule_f1 > 0:
        print(f"    Improvement over rule: {(f1_best - rule_f1) / rule_f1 * 100:+.1f}%")

    # Feature importances
    print("\n── Feature importances (top 15) ──")
    importances = model.feature_importances_
    feat_imp    = sorted(zip(FEATURE_COLS, importances), key=lambda x: -x[1])
    for feat, imp in feat_imp[:15]:
        bar = "█" * int(imp * 80)
        print(f"  {feat:<38} {imp:.4f}  {bar}")

    # ── SHAP explainability ──────────────────────────────────────────────
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_test)
        shap_importance = pd.DataFrame({
            "feature": FEATURE_COLS,
            "mean_abs_shap": np.abs(shap_values).mean(axis=0)
        }).sort_values("mean_abs_shap", ascending=False)
        shap_importance.to_csv(ARTIFACT_DIR / "priority_shap.csv", index=False)
        print(f"\n  SHAP importances saved → priority_shap.csv")
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
    with open(ARTIFACT_DIR / "priority_split.json", "w") as f:
        json.dump(split_info, f)
    print(f"  Split indices saved → priority_split.json")

    # Save
    joblib.dump(model, OUT_MODEL)
    meta = {
        "threshold":    best_t,
        "feature_cols": FEATURE_COLS,
        "target":       "y_severity",
        "problem":      "composite_severity",
        "auc_roc":      round(auc,   4),
        "auc_pr":       round(auc_pr,4),
        "f1":           round(f1_best, 4),
        "baseline_rule_f1": round(rule_f1, 4),
        "split_method": "time_based",
        "version":      "v3",
        "note": (
            "v3: composite severity target (closure + duration + disruption). "
            "Time-based split. New features: dow_sin/cos, corridor_events_4h/24h, is_rush_hour."
        ),
    }
    with open(OUT_META, "w") as f:
        json.dump(meta, f, indent=2)

    # Export encoding lookups for inference
    train_labels_full = fm_labels.iloc[train_idx]
    cause_lookup = train_labels_full.groupby("event_cause")["y_closure"].mean().to_dict()
    cause_lookup["__default__"] = float(train_labels_full["y_closure"].mean())

    corridor_density_lookup = (
        clean.groupby("corridor").size().apply(lambda c: float(np.log1p(c))).to_dict()
    )
    corridor_density_lookup["__default__"] = 0.0

    encoding_lookups = {
        "cause_closure_rate":    {k: round(float(v), 4) for k, v in cause_lookup.items()},
        "corridor_density_log":  {k: round(float(v), 4) for k, v in corridor_density_lookup.items()},
    }
    with open(ARTIFACT_DIR / "priority_encoding_lookups.json", "w") as f:
        json.dump(encoding_lookups, f, indent=2)
    print(f"Encoding lookups → {ARTIFACT_DIR / 'priority_encoding_lookups.json'}")

    print(f"\nModel → {OUT_MODEL} ({OUT_MODEL.stat().st_size/1024:.1f} KB)")
    print(f"Meta  → {OUT_META}")
    print("\n✅ Done.")


if __name__ == "__main__":
    main()