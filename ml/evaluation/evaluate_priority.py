"""
evaluate_priority.py — Evaluate the severity/closure classifier v2 (XGBoost).

Updated for v2 feature set:
  - Target is now requires_road_closure (not 'priority') — reframed in v2
  - Spatial features: lat_bin, lon_bin, is_daytime, is_planned
  - New features: corridor_density_log, cause_closure_rate (target-encoded)
  - Threshold loaded from priority_meta.json
  - Reports: AUC-ROC, AUC-PR, F1, CM, plus non-corridor escalation subset
  - Non-corridor analysis: how many incidents does the model flag for closure
    that ops historically missed (escalation flags)

Run:
    python ml/evaluation/evaluate_priority.py
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
    classification_report,
)


warnings.filterwarnings("ignore")

ROOT         = Path(__file__).parent.parent.parent
FEATURE_CSV  = ROOT / "data" / "processed" / "feature_matrix.csv"
CLEAN_CSV    = ROOT / "data" / "processed" / "events_clean.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
MODEL_PATH   = ARTIFACT_DIR / "priority_model.pkl"
META_PATH    = ARTIFACT_DIR / "priority_meta.json"

FEATURE_COLS: list[str] = []  # populated from priority_meta.json at runtime — see main()


def engineer_spatial(fm: pd.DataFrame, clean: pd.DataFrame) -> pd.DataFrame:
    """Add spatial, temporal and event-type features from events_clean.csv."""
    c = clean.copy()
    c["lat_bin"]              = ((c["latitude"]  - 12.8) / 0.05).astype(int).clip(0, 15)
    c["lon_bin"]              = ((c["longitude"] - 77.3) / 0.05).astype(int).clip(0, 15)
    c["is_daytime"]           = c["hour_of_day"].between(8, 20).astype(int)
    c["is_planned"]           = (c["event_type"] == "planned").astype(int)
    corr_density              = c["corridor"].map(c["corridor"].value_counts())
    c["corridor_density_log"] = np.log1p(corr_density)

    spatial = c[["id", "lat_bin", "lon_bin", "is_daytime", "is_planned", "corridor_density_log"]]
    merged  = fm.merge(spatial, on="id", how="left")
    merged["lat_bin"]              = merged["lat_bin"].fillna(7).astype(int)
    merged["lon_bin"]              = merged["lon_bin"].fillna(5).astype(int)
    merged["is_daytime"]           = merged["is_daytime"].fillna(0).astype(int)
    merged["is_planned"]           = merged["is_planned"].fillna(0).astype(int)
    merged["corridor_density_log"] = merged["corridor_density_log"].fillna(0)
    return merged


def add_target_encoded(fm: pd.DataFrame, train_idx) -> pd.DataFrame:
    """Encode cause → closure_rate from train rows only (no leakage)."""
    train_rows = fm.iloc[train_idx]
    cause_rate  = train_rows.groupby("event_cause")["y_closure"].mean().to_dict()
    global_rate = train_rows["y_closure"].mean()
    fm["cause_closure_rate"] = fm["event_cause"].map(cause_rate).fillna(global_rate).values
    return fm


def main():
    print("=" * 60)
    print("GridSense v2 — Evaluate Severity/Closure Classifier (XGBoost)")
    print("TARGET: requires_road_closure")
    print("=" * 60)

    for path, label in [(MODEL_PATH, "priority_model.pkl"), (META_PATH, "priority_meta.json"),
                        (FEATURE_CSV, "feature_matrix.csv"), (CLEAN_CSV, "events_clean.csv")]:
        if not path.exists():
            print(f"ERROR: {label} not found. Run 04_train_priority.py first.")
            sys.exit(1)

    model = joblib.load(MODEL_PATH)
    meta  = json.load(open(META_PATH))
    tuned_threshold = meta["threshold"]

    global FEATURE_COLS
    FEATURE_COLS = meta["feature_cols"]
    print(f"Feature cols ({len(FEATURE_COLS)}): {FEATURE_COLS}")

    print(f"Model      : {type(model).__name__}")
    print(f"Version    : {meta.get('version', 'v1')}")
    print(f"Target     : {meta.get('target', 'requires_road_closure')}")
    print(f"Threshold  : {tuned_threshold}  (tuned on val set during training)")

    fm    = pd.read_csv(FEATURE_CSV, low_memory=False)
    clean = pd.read_csv(CLEAN_CSV,   low_memory=False)
    fm    = fm[fm["is_stale_active"] == 0].reset_index(drop=True)
    print(f"Rows       : {len(fm):,}")

    fm = engineer_spatial(fm, clean)

    # Target: y_severity (v2) with fallback to y_closure
    if "y_severity" in fm.columns:
        y_all = fm["y_severity"].copy()
        target_name = "y_severity"
    else:
        y_all = fm["y_closure"].copy()
        target_name = "y_closure"
        print("[eval_priority] WARNING: y_severity not found, falling back to y_closure")
    is_nc = fm["is_non_corridor"].copy()

    pos = int(y_all.sum())
    neg = int((y_all == 0).sum())
    print(f"\nTarget       : {target_name}")
    print(f"Class dist   : pos={pos:,} ({pos/len(y_all)*100:.1f}%)  "
          f"neg={neg:,} ({neg/len(y_all)*100:.1f}%)")

    # Load time-based split indices
    split_path = ARTIFACT_DIR / "priority_split.json"
    if split_path.exists():
        with open(split_path) as f:
            split = json.load(f)
        test_idx = split["test_indices"]
        train_idx = split.get("train_indices", [i for i in range(len(fm)) if i not in test_idx])
        print(f"[eval_priority] Using time-based split: test set = {len(test_idx):,} rows")
        print("[eval_priority] EVALUATION ON HELD-OUT TEST SET ONLY (time-based split)")
    else:
        print("[eval_priority] WARNING: No split file found. Evaluating on FULL dataset (may include training data).")
        test_idx = list(range(len(fm)))
        train_idx = list(range(len(fm)))

    fm = add_target_encoded(fm, train_idx)

    X_test  = fm[FEATURE_COLS].iloc[test_idx]
    y_test  = y_all.iloc[test_idx]
    nc_test = is_nc.iloc[test_idx]
    print(f"Test set     : {len(X_test):,} rows\n")

    proba = model.predict_proba(X_test)[:, 1]

    # Core metrics
    auc    = roc_auc_score(y_test, proba)
    auc_pr = average_precision_score(y_test, proba)
    print(f"  AUC-ROC  : {auc:.4f}")
    print(f"  AUC-PR   : {auc_pr:.4f}")

    # Naive baseline
    naive_auc_pr = average_precision_score(y_test, np.full(len(y_test), y_test.mean()))
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

    # Non-corridor subset — escalation flag analysis
    nc_mask    = nc_test.values == 1
    nc_count   = int(nc_mask.sum())
    nc_proba   = proba[nc_mask]
    nc_actual  = y_test.values[nc_mask]
    nc_preds   = (proba[nc_mask] >= tuned_threshold).astype(int)
    flags_fired = int(nc_preds.sum())

    print(f"\n── Non-corridor Subset ({nc_count} test records) ──")
    print(f"  Actual closure rate : {nc_actual.mean()*100:.1f}%")
    if nc_actual.sum() > 0:
        nc_auc = roc_auc_score(nc_actual, nc_proba)
        nc_f1  = f1_score(nc_actual, nc_preds, zero_division=0)
        nc_p   = precision_score(nc_actual, nc_preds, zero_division=0)
        nc_r   = recall_score(nc_actual, nc_preds, zero_division=0)
        print(f"  AUC-ROC             : {nc_auc:.4f}")
        print(f"  Precision           : {nc_p:.4f}")
        print(f"  Recall              : {nc_r:.4f}")
        print(f"  F1                  : {nc_f1:.4f}")
    print(f"  Escalation flags fired  : {flags_fired}")
    print(f"  (Non-corridor incidents the model predicts need road closure,")
    print(f"   which ops would have defaulted to Low / no-action)")

    # Planned-event subset
    planned_mask = fm["is_planned"].iloc[test_idx].values == 1
    planned_count = int(planned_mask.sum())
    if planned_count > 0:
        pl_proba  = proba[planned_mask]
        pl_actual = y_test.values[planned_mask]
        pl_preds  = (pl_proba >= tuned_threshold).astype(int)
        pl_f1     = f1_score(pl_actual, pl_preds, zero_division=0)
        pl_auc    = roc_auc_score(pl_actual, pl_proba) if pl_actual.sum() > 0 else float("nan")
        print(f"\n── Planned-Event Subset ({planned_count} test records) ──")
        print(f"  Actual closure rate : {pl_actual.mean()*100:.1f}%")
        print(f"  AUC-ROC             : {pl_auc:.4f}")
        print(f"  F1                  : {pl_f1:.4f}")
        print(f"  Closures predicted  : {int(pl_preds.sum())} / {planned_count}")

    # Feature importances
    print("\n── Feature Importances (all 20 features) ──")
    importances = model.feature_importances_
    feat_imp = sorted(zip(FEATURE_COLS, importances), key=lambda x: -x[1])
    for i, (feat, imp) in enumerate(feat_imp):
        bar = "█" * int(imp * 100)
        print(f"  {i+1:>2}. {feat:<38} {imp:.4f}  {bar}")

    print("\n✅ Severity model evaluation complete.")


if __name__ == "__main__":
    main()