"""
03_train_closure.py - Train XGBoost Road Closure Predictor.

This script trains two closure models on the same train/test split:
  1. Baseline model: original feature set.
  2. Enhanced model: baseline + new time flags + station/zone encodings +
     interaction frequency features + leakage-safe historical closure rates.

Historical rate features are target encoded with:
  - train/test split first
  - out-of-fold encodings for training rows
  - full-train encodings for test rows

Outputs:
    ml/artifacts/closure_model.pkl
    ml/artifacts/closure_before_after_metrics.json
    ml/artifacts/closure_feature_importance.json
    ml/artifacts/closure_feature_importance.csv

Run:
    python ml/pipeline/03_train_closure.py
"""

import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from xgboost import XGBClassifier

ROOT = Path(__file__).parent.parent.parent
FEATURE_CSV = ROOT / "data" / "processed" / "feature_matrix.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

OUT_MODEL = ARTIFACT_DIR / "closure_model.pkl"
OUT_METRICS_JSON = ARTIFACT_DIR / "closure_before_after_metrics.json"
OUT_IMPORTANCE_JSON = ARTIFACT_DIR / "closure_feature_importance.json"
OUT_IMPORTANCE_CSV = ARTIFACT_DIR / "closure_feature_importance.csv"
OUT_FULL_IMPORTANCE_CSV = ARTIFACT_DIR / "full_feature_importance_ranked.csv"
OUT_THRESHOLD_ANALYSIS_JSON = ARTIFACT_DIR / "closure_threshold_analysis.json"
OUT_ABLATION_REPORT_JSON = ARTIFACT_DIR / "feature_ablation_report.json"
OUT_STATION_EXPERIMENT_JSON = ARTIFACT_DIR / "station_feature_experiment.json"

CLOSURE_THRESHOLD = 0.35
THRESHOLD_SWEEP = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75]

BASE_FEATURE_COLS = [
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

TARGET_ENCODING_SPECS = {
    "event_cause": "cause_closure_rate",
    "corridor": "corridor_closure_rate",
    "cause_corridor_key": "cause_corridor_closure_rate",
}

STATION_TARGET_ENCODING_SPECS = {
    "police_station": "station_closure_rate",
    "cause_station_key": "cause_station_closure_rate",
    "zone": "zone_closure_rate",
}

FREQUENCY_ENCODING_SPECS = {
    "cause_corridor_key": "cause_corridor_key_freq",
    "cause_priority_key": "cause_priority_key_freq",
}

ENHANCED_FEATURE_COLS = BASE_FEATURE_COLS + [
    "police_station_encoded",
    "zone_encoded",
    "is_peak_hour",
    "is_weekend",
    "is_night",
    "cause_corridor_key_freq",
    "cause_priority_key_freq",
    "cause_closure_rate",
    "corridor_closure_rate",
    "cause_corridor_closure_rate",
]

STATION_EXPERIMENT_FEATURE_COLS = ENHANCED_FEATURE_COLS + [
    "station_load",
    "station_closure_rate",
    "cause_station_closure_rate",
    "zone_closure_rate",
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
    print(f"[03_closure] Loading feature matrix from {path} ...")
    df = pd.read_csv(path, low_memory=False)
    df = df[df["is_stale_active"] == 0].copy()
    print(f"[03_closure] Rows after stale filter: {len(df):,}")

    required_cols = sorted(
        set(BASE_FEATURE_COLS)
        | {
            "police_station_encoded",
            "zone_encoded",
            "is_peak_hour",
            "is_weekend",
            "is_night",
            "station_load",
        }
        | set(TARGET_ENCODING_SPECS)
        | set(STATION_TARGET_ENCODING_SPECS)
        | set(FREQUENCY_ENCODING_SPECS)
        | {"y_closure"}
    )
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"[03_closure] ERROR: Missing feature columns: {missing_cols}")
        print("[03_closure] Run 02_feature_engineer.py first.")
        sys.exit(1)

    y = df["y_closure"].astype(int).copy()
    pos = int(y.sum())
    neg = int((y == 0).sum())
    print(f"[03_closure] Class distribution - positive (closure): {pos:,}  negative: {neg:,}")
    print(f"[03_closure] Positive rate: {pos / len(y) * 100:.1f}%")
    return df, y


def _select_features(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    return df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)


def _smoothed_rates(
    values: pd.Series,
    y: pd.Series,
    global_rate: float,
    smoothing: float,
) -> dict:
    stats = pd.DataFrame({
        "key": values.fillna("__MISSING__").astype(str),
        "target": y.astype(float).values,
    })
    grouped = stats.groupby("key")["target"].agg(["sum", "count"])
    rates = (grouped["sum"] + global_rate * smoothing) / (grouped["count"] + smoothing)
    return rates.to_dict()


def add_cross_fold_target_features(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    n_splits: int = 5,
    smoothing: float = 20.0,
    encoding_specs: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add leakage-safe historical closure-rate features."""
    X_train_enc = X_train.copy()
    X_test_enc = X_test.copy()
    global_rate = float(y_train.mean())
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    encoding_specs = encoding_specs or TARGET_ENCODING_SPECS

    for source_col, out_col in encoding_specs.items():
        X_train_enc[out_col] = global_rate
        out_idx = X_train_enc.columns.get_loc(out_col)

        for train_idx, valid_idx in skf.split(X_train_enc, y_train):
            fold_rates = _smoothed_rates(
                X_train_enc.iloc[train_idx][source_col],
                y_train.iloc[train_idx],
                global_rate,
                smoothing,
            )
            valid_values = X_train_enc.iloc[valid_idx][source_col].fillna("__MISSING__").astype(str)
            X_train_enc.iloc[valid_idx, out_idx] = valid_values.map(fold_rates).fillna(global_rate).values

        full_train_rates = _smoothed_rates(X_train_enc[source_col], y_train, global_rate, smoothing)
        X_test_enc[out_col] = (
            X_test_enc[source_col].fillna("__MISSING__").astype(str).map(full_train_rates).fillna(global_rate)
        )

    for source_col, out_col in FREQUENCY_ENCODING_SPECS.items():
        train_values = X_train_enc[source_col].fillna("__MISSING__").astype(str)
        freqs = train_values.value_counts(normalize=True).to_dict()
        X_train_enc[out_col] = train_values.map(freqs).fillna(0.0)
        X_test_enc[out_col] = (
            X_test_enc[source_col].fillna("__MISSING__").astype(str).map(freqs).fillna(0.0)
        )

    return X_train_enc, X_test_enc


def train_model(X_train: pd.DataFrame, y_train: pd.Series, scale_pos_weight: float, label: str) -> XGBClassifier:
    params = {**XGBOOST_PARAMS, "scale_pos_weight": scale_pos_weight}
    print(f"\n[03_closure] Training {label} XGBoost with scale_pos_weight={scale_pos_weight:.2f} ...")
    model = XGBClassifier(**params)
    model.fit(X_train, y_train, eval_set=[(X_train, y_train)], verbose=False)
    return model


def evaluate(model: XGBClassifier, X_test: pd.DataFrame, y_test: pd.Series, label: str) -> dict:
    print(f"\n[03_closure] -- {label} Evaluation --")
    proba = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, proba)
    print(f"  AUC-ROC: {auc:.4f}")

    metrics = {"roc_auc": float(auc), "thresholds": {}}
    for threshold in THRESHOLD_SWEEP:
        preds = (proba >= threshold).astype(int)
        precision = precision_score(y_test, preds, zero_division=0)
        recall = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)
        cm = confusion_matrix(y_test, preds)
        tn, fp, fn, tp = cm.ravel()
        fpr = fp / max(fp + tn, 1)
        fnr = fn / max(fn + tp, 1)
        metrics["thresholds"][str(threshold)] = {
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "fpr": float(fpr),
            "fnr": float(fnr),
            "roc_auc": float(auc),
            "confusion_matrix": {
                "tn": int(tn),
                "fp": int(fp),
                "fn": int(fn),
                "tp": int(tp),
            },
        }
    print_threshold_table(metrics["thresholds"])
    return metrics


def print_threshold_table(thresholds: dict) -> None:
    print("\n  Threshold  Precision  Recall     F1       FPR      FNR      ROC-AUC")
    print("  -------------------------------------------------------------------")
    for threshold in THRESHOLD_SWEEP:
        row = thresholds[str(threshold)]
        print(
            f"  {threshold:>8.2f}  "
            f"{row['precision']:>9.4f}  "
            f"{row['recall']:>7.4f}  "
            f"{row['f1']:>7.4f}  "
            f"{row['fpr']:>7.4f}  "
            f"{row['fnr']:>7.4f}  "
            f"{row['roc_auc']:>7.4f}"
        )


def threshold_rows(metrics: dict) -> list[dict]:
    rows = []
    for threshold in THRESHOLD_SWEEP:
        values = metrics["thresholds"][str(threshold)]
        rows.append({
            "threshold": threshold,
            "precision": values["precision"],
            "recall": values["recall"],
            "f1": values["f1"],
            "fpr": values["fpr"],
            "fnr": values["fnr"],
            "roc_auc": values["roc_auc"],
            "confusion_matrix": values["confusion_matrix"],
        })
    return rows


def best_threshold(rows: list[dict], metric: str) -> dict:
    return max(rows, key=lambda row: (row[metric], row["f1"], row["precision"], row["recall"]))


def save_threshold_analysis(enhanced_metrics: dict) -> dict:
    rows = threshold_rows(enhanced_metrics)
    best_precision = best_threshold(rows, "precision")
    best_f1 = best_threshold(rows, "f1")
    best_recall = best_threshold(rows, "recall")
    recommendations = {
        "traffic_police_mode": {
            "threshold": best_recall["threshold"],
            "reason": "Maximizes recall to avoid missing road-closure events.",
            "metrics": best_recall,
        },
        "balanced_mode": {
            "threshold": best_f1["threshold"],
            "reason": "Maximizes F1 for a balance between false alarms and missed closures.",
            "metrics": best_f1,
        },
        "high_precision_mode": {
            "threshold": best_precision["threshold"],
            "reason": "Maximizes precision to reduce false alerts.",
            "metrics": best_precision,
        },
    }
    payload = {
        "model": "enhanced_closure_xgboost",
        "thresholds": rows,
        "best_precision_threshold": best_precision,
        "best_f1_threshold": best_f1,
        "best_recall_threshold": best_recall,
        "business_recommendations": recommendations,
    }
    with open(OUT_THRESHOLD_ANALYSIS_JSON, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


def print_business_recommendations(analysis: dict) -> None:
    print("\n[03_closure] Business threshold recommendation")
    for label, key in [
        ("Traffic Police Mode", "traffic_police_mode"),
        ("Balanced Mode", "balanced_mode"),
        ("High Precision Mode", "high_precision_mode"),
    ]:
        rec = analysis["business_recommendations"][key]
        metrics = rec["metrics"]
        print(
            f"  {label}: threshold={rec['threshold']:.2f} | "
            f"precision={metrics['precision']:.4f}, recall={metrics['recall']:.4f}, "
            f"F1={metrics['f1']:.4f}, FPR={metrics['fpr']:.4f}, FNR={metrics['fnr']:.4f}"
        )
        print(f"    {rec['reason']}")
    print(f"\n[03_closure] Threshold analysis saved -> {OUT_THRESHOLD_ANALYSIS_JSON}")


def print_before_after(before: dict, after: dict) -> None:
    before_t = before["thresholds"][str(CLOSURE_THRESHOLD)]
    after_t = after["thresholds"][str(CLOSURE_THRESHOLD)]
    print(f"\n[03_closure] Before vs After at threshold {CLOSURE_THRESHOLD}")
    print("  Metric      Before     After      Delta")
    for key, label in [
        ("precision", "Precision"),
        ("recall", "Recall"),
        ("f1", "F1"),
        ("roc_auc", "ROC-AUC"),
    ]:
        before_val = before["roc_auc"] if key == "roc_auc" else before_t[key]
        after_val = after["roc_auc"] if key == "roc_auc" else after_t[key]
        print(f"  {label:<10} {before_val:>8.4f}  {after_val:>8.4f}  {after_val-before_val:>+8.4f}")


def save_feature_importance(model: XGBClassifier, feature_cols: list[str]) -> list[dict]:
    ranked = sorted(
        zip(feature_cols, model.feature_importances_),
        key=lambda item: -item[1],
    )
    total_importance = sum(float(importance) for _, importance in ranked) or 1.0
    cumulative = 0.0
    rows = []
    for rank, (feature, importance) in enumerate(ranked, start=1):
        importance = float(importance)
        cumulative += importance
        rows.append({
            "rank": rank,
            "feature": feature,
            "importance": importance,
            "importance_pct": importance / total_importance * 100.0,
            "cumulative_importance_pct": cumulative / total_importance * 100.0,
        })
    with open(OUT_IMPORTANCE_JSON, "w") as f:
        json.dump(rows, f, indent=2)
    pd.DataFrame(rows).to_csv(OUT_IMPORTANCE_CSV, index=False)
    pd.DataFrame(rows).to_csv(OUT_FULL_IMPORTANCE_CSV, index=False)

    print("\n[03_closure] Top 15 enhanced feature importances:")
    for row in rows[:15]:
        print(
            f"    {row['rank']:>2}. {row['feature']}: "
            f"{row['importance']:.4f} "
            f"({row['importance_pct']:.2f}%, cumulative {row['cumulative_importance_pct']:.2f}%)"
        )
    print(f"\n[03_closure] Feature importance JSON saved -> {OUT_IMPORTANCE_JSON}")
    print(f"[03_closure] Feature importance CSV saved -> {OUT_IMPORTANCE_CSV}")
    print(f"[03_closure] Full ranked feature importance CSV saved -> {OUT_FULL_IMPORTANCE_CSV}")
    return rows


def metric_at_operating_threshold(metrics: dict) -> dict:
    values = metrics["thresholds"][str(CLOSURE_THRESHOLD)]
    return {
        "precision": values["precision"],
        "recall": values["recall"],
        "f1": values["f1"],
        "roc_auc": metrics["roc_auc"],
        "fpr": values["fpr"],
        "fnr": values["fnr"],
        "confusion_matrix": values["confusion_matrix"],
    }


def compare_metric_dict(before: dict, after: dict) -> dict:
    return {
        key: after[key] - before[key]
        for key in ["precision", "recall", "f1", "roc_auc", "fpr", "fnr"]
    }


def print_metric_comparison(title: str, before: dict, after: dict) -> None:
    print(f"\n[03_closure] {title} at threshold {CLOSURE_THRESHOLD}")
    print("  Metric      Current    Experiment Delta")
    for key, label in [
        ("precision", "Precision"),
        ("recall", "Recall"),
        ("f1", "F1"),
        ("roc_auc", "ROC-AUC"),
    ]:
        print(
            f"  {label:<10} "
            f"{before[key]:>8.4f}  "
            f"{after[key]:>10.4f} "
            f"{after[key]-before[key]:>+8.4f}"
        )


def run_station_feature_experiment(
    X_train_base_encoded: pd.DataFrame,
    X_test_base_encoded: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
    scale_pos_weight: float,
    current_metrics: dict,
) -> dict:
    X_train_station_raw, X_test_station_raw = add_cross_fold_target_features(
        X_train_base_encoded,
        y_train,
        X_test_base_encoded,
        encoding_specs=STATION_TARGET_ENCODING_SPECS,
    )
    X_train_station = _select_features(X_train_station_raw, STATION_EXPERIMENT_FEATURE_COLS)
    X_test_station = _select_features(X_test_station_raw, STATION_EXPERIMENT_FEATURE_COLS)

    station_model = train_model(
        X_train_station,
        y_train,
        scale_pos_weight,
        label="station-feature experiment",
    )
    station_metrics = evaluate(station_model, X_test_station, y_test, label="Station Feature Experiment")
    current_at_threshold = metric_at_operating_threshold(current_metrics)
    station_at_threshold = metric_at_operating_threshold(station_metrics)
    delta = compare_metric_dict(current_at_threshold, station_at_threshold)
    print_metric_comparison("Current enhanced vs station-feature experiment", current_at_threshold, station_at_threshold)

    report = {
        "operating_threshold": CLOSURE_THRESHOLD,
        "added_features": [
            "station_load",
            "station_closure_rate",
            "cause_station_key",
            "cause_station_closure_rate",
            "zone_closure_rate",
        ],
        "target_encoding": {
            "method": "train/test split plus 5-fold out-of-fold target encoding on training rows",
            "smoothing": 20.0,
            "encoded_features": STATION_TARGET_ENCODING_SPECS,
        },
        "current_model_features": ENHANCED_FEATURE_COLS,
        "station_experiment_features": STATION_EXPERIMENT_FEATURE_COLS,
        "current_metrics": current_at_threshold,
        "station_feature_metrics": station_at_threshold,
        "delta_station_minus_current": delta,
        "full_threshold_metrics": {
            "current": current_metrics,
            "station_feature_experiment": station_metrics,
        },
    }
    with open(OUT_STATION_EXPERIMENT_JSON, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n[03_closure] Station feature experiment saved -> {OUT_STATION_EXPERIMENT_JSON}")
    return report


def run_feature_ablation(
    importance_rows: list[dict],
    X_train_enhanced_raw: pd.DataFrame,
    X_test_enhanced_raw: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
    scale_pos_weight: float,
    enhanced_metrics: dict,
) -> dict:
    top_10 = importance_rows[:10]
    bottom_10 = importance_rows[-10:]
    bottom_features = [row["feature"] for row in bottom_10]
    reduced_feature_cols = [
        feature for feature in ENHANCED_FEATURE_COLS if feature not in set(bottom_features)
    ]

    print("\n[03_closure] Feature ablation")
    print("  Top 10 features:")
    for row in top_10:
        print(f"    {row['feature']}: {row['importance']:.4f}")
    print("  Bottom 10 features removed:")
    for row in bottom_10:
        print(f"    {row['feature']}: {row['importance']:.4f}")

    X_train_reduced = _select_features(X_train_enhanced_raw, reduced_feature_cols)
    X_test_reduced = _select_features(X_test_enhanced_raw, reduced_feature_cols)
    reduced_model = train_model(
        X_train_reduced,
        y_train,
        scale_pos_weight,
        label="feature-ablated",
    )
    reduced_metrics = evaluate(reduced_model, X_test_reduced, y_test, label="Feature Ablated")

    enhanced_at_threshold = metric_at_operating_threshold(enhanced_metrics)
    reduced_at_threshold = metric_at_operating_threshold(reduced_metrics)
    delta = compare_metric_dict(enhanced_at_threshold, reduced_at_threshold)

    print(f"\n[03_closure] Enhanced vs Feature-Ablated at threshold {CLOSURE_THRESHOLD}")
    print("  Metric      Enhanced   Ablated    Delta")
    for key, label in [
        ("precision", "Precision"),
        ("recall", "Recall"),
        ("f1", "F1"),
        ("roc_auc", "ROC-AUC"),
    ]:
        print(
            f"  {label:<10} "
            f"{enhanced_at_threshold[key]:>8.4f}  "
            f"{reduced_at_threshold[key]:>8.4f}  "
            f"{delta[key]:>+8.4f}"
        )

    report = {
        "operating_threshold": CLOSURE_THRESHOLD,
        "ranked_features": importance_rows,
        "top_10_features": top_10,
        "bottom_10_features": bottom_10,
        "removed_features": bottom_features,
        "remaining_features": reduced_feature_cols,
        "enhanced_metrics": enhanced_at_threshold,
        "feature_ablated_metrics": reduced_at_threshold,
        "delta_feature_ablated_minus_enhanced": delta,
        "full_threshold_metrics": {
            "enhanced": enhanced_metrics,
            "feature_ablated": reduced_metrics,
        },
    }
    with open(OUT_ABLATION_REPORT_JSON, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n[03_closure] Feature ablation report saved -> {OUT_ABLATION_REPORT_JSON}")
    return report


def main():
    print("=" * 60)
    print("GridSense - Step 3: Train Closure Model (XGBoost)")
    print("=" * 60)

    if not FEATURE_CSV.exists():
        print(f"[03_closure] ERROR: {FEATURE_CSV} not found. Run 02_feature_engineer.py first.")
        sys.exit(1)

    X, y = load_features(FEATURE_CSV)

    neg = int((y == 0).sum())
    pos = int(y.sum())
    scale_pos_weight = neg / max(pos, 1)

    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"[03_closure] Train: {len(X_train_raw):,}  Test: {len(X_test_raw):,}")

    X_train_base = _select_features(X_train_raw, BASE_FEATURE_COLS)
    X_test_base = _select_features(X_test_raw, BASE_FEATURE_COLS)
    base_model = train_model(X_train_base, y_train, scale_pos_weight, label="baseline")
    base_metrics = evaluate(base_model, X_test_base, y_test, label="Baseline")

    X_train_enhanced_raw, X_test_enhanced_raw = add_cross_fold_target_features(
        X_train_raw, y_train, X_test_raw
    )
    X_train_enhanced = _select_features(X_train_enhanced_raw, ENHANCED_FEATURE_COLS)
    X_test_enhanced = _select_features(X_test_enhanced_raw, ENHANCED_FEATURE_COLS)

    enhanced_model = train_model(X_train_enhanced, y_train, scale_pos_weight, label="enhanced")
    enhanced_metrics = evaluate(enhanced_model, X_test_enhanced, y_test, label="Enhanced")

    print_before_after(base_metrics, enhanced_metrics)
    importance_rows = save_feature_importance(enhanced_model, ENHANCED_FEATURE_COLS)
    station_experiment_report = run_station_feature_experiment(
        X_train_enhanced_raw,
        X_test_enhanced_raw,
        y_train,
        y_test,
        scale_pos_weight,
        enhanced_metrics,
    )
    ablation_report = run_feature_ablation(
        importance_rows,
        X_train_enhanced_raw,
        X_test_enhanced_raw,
        y_train,
        y_test,
        scale_pos_weight,
        enhanced_metrics,
    )
    threshold_analysis = save_threshold_analysis(enhanced_metrics)
    print_business_recommendations(threshold_analysis)

    joblib.dump(enhanced_model, OUT_MODEL)
    with open(OUT_METRICS_JSON, "w") as f:
        json.dump(
            {
                "threshold": CLOSURE_THRESHOLD,
                "baseline": base_metrics,
                "enhanced": enhanced_metrics,
                "base_feature_cols": BASE_FEATURE_COLS,
                "enhanced_feature_cols": ENHANCED_FEATURE_COLS,
                "feature_ablation_report": str(OUT_ABLATION_REPORT_JSON),
                "station_feature_experiment": str(OUT_STATION_EXPERIMENT_JSON),
                "target_encoding": {
                    "method": "train/test split plus 5-fold out-of-fold target encoding on training rows",
                    "smoothing": 20.0,
                    "encoded_features": TARGET_ENCODING_SPECS,
                },
            },
            f,
            indent=2,
        )

    print(f"\n[03_closure] Model saved -> {OUT_MODEL}")
    print(f"[03_closure] Metrics saved -> {OUT_METRICS_JSON}")
    print(f"[03_closure] Model file size: {OUT_MODEL.stat().st_size / 1024:.1f} KB")
    print("\n[03_closure] Done.")


if __name__ == "__main__":
    main()
