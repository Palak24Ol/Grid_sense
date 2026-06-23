"""
Train prototype traffic-intelligence classifiers.

Outputs:
  ml/artifacts/traffic_intelligence_models.pkl
  ml/artifacts/traffic_intelligence_evaluation.json

The target is a proxy label for "congestion pressure" because the dataset does
not contain direct real-time congestion labels. It is intended as a baseline
for precision/recall/F1/ROC-AUC tracking, not as a production truth model.
"""

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit

try:
    import joblib
except Exception:
    joblib = None

try:
    from xgboost import XGBClassifier
except Exception:
    XGBClassifier = None

try:
    from lightgbm import LGBMClassifier
except Exception:
    LGBMClassifier = None


ROOT = Path(__file__).parent.parent.parent
CLEAN_CSV = ROOT / "data" / "processed" / "events_clean.csv"
ARTIFACT_DIR = ROOT / "ml" / "artifacts"
PROFILE_PATH = ARTIFACT_DIR / "traffic_intelligence_profile.json"
OUT_MODEL = ARTIFACT_DIR / "traffic_intelligence_models.pkl"
OUT_EVAL = ARTIFACT_DIR / "traffic_intelligence_evaluation.json"
OUT_IMPORTANCE = ARTIFACT_DIR / "traffic_intelligence_feature_importance.json"

FEATURE_COLS = [
    "density_ratio",
    "speed_drop",
    "delay_ratio",
    "rolling_mean",
    "rolling_std",
    "neighbor_density",
    "neighbor_speed",
    "road_centrality",
    "historical_congestion_frequency",
    "neighbor_congestion_influence",
    "weather_risk",
    "hour_of_day",
    "day_of_week",
    "month",
    "surge_ratio",
    "incoming_vehicle_proxy",
    "outgoing_vehicle_proxy",
    "flow_variance_index",
    "neighbor_capacity_ratio",
    "road_load_ratio",
]


def load_profile() -> dict:
    if not PROFILE_PATH.exists():
        raise FileNotFoundError("Run ml/pipeline/11_build_traffic_intelligence.py first.")
    with open(PROFILE_PATH) as f:
        return json.load(f)


def build_training_frame() -> pd.DataFrame:
    profile = load_profile()
    roads = profile["roads"]
    df = pd.read_csv(CLEAN_CSV, low_memory=False)
    df["start_datetime"] = pd.to_datetime(df["start_datetime"], utc=True, errors="coerce")
    df = df.dropna(subset=["start_datetime", "corridor"])
    df = df[df["corridor"].isin(roads)].copy()
    df = df.sort_values("start_datetime")
    df["requires_road_closure"] = (
        df["requires_road_closure"].astype(str).str.upper().map({"TRUE": 1, "FALSE": 0}).fillna(0)
    )
    df["duration_mins"] = pd.to_numeric(df["duration_mins"], errors="coerce")
    duration_p90 = df["duration_mins"].quantile(0.90)
    df["duration_mins"] = df["duration_mins"].fillna(df["duration_mins"].median())
    
    congestion_causes = {"congestion", "vehicle_breakdown", "accident", "tree_fall", "water_logging"}
    df["is_congestion_cause"] = df["event_cause"].astype(str).str.lower().isin(congestion_causes).astype(int)
    df["is_high_priority"] = df["priority"].astype(str).str.lower().eq("high").astype(int)

    rows = []
    for _, row in df.iterrows():
        road = roads[row["corridor"]]
        density_ratio = 1.0 + road["historical_density_proxy"] * 0.6
        speed_drop = road["speed_drop_pct_proxy"]
        delay_ratio = road["delay_ratio_proxy"]
        
        target = int(
            row["requires_road_closure"] == 1
            or row["is_congestion_cause"] == 1
            or row["duration_mins"] >= duration_p90
        )
        
        capacity = max(road.get("capacity_proxy", 100.0), 1.0)
        
        rows.append(
            {
                "density_ratio": density_ratio,
                "speed_drop": speed_drop,
                "delay_ratio": delay_ratio,
                "rolling_mean": road["rolling_mean_7d"],
                "rolling_std": road["rolling_std_7d"],
                "neighbor_density": road["neighbor_density_proxy"],
                "neighbor_speed": road["neighbor_speed_kmph"],
                "road_centrality": road["road_centrality"],
                "historical_congestion_frequency": road["historical_congestion_frequency_score"],
                "neighbor_congestion_influence": road["neighbor_congestion_influence_score"],
                "weather_risk": road["weather_risk_score"],
                "hour_of_day": row["hour_of_day"],
                "day_of_week": row["day_of_week"],
                "month": row["month"],
                "surge_ratio": density_ratio / capacity,
                "incoming_vehicle_proxy": road["historical_density_proxy"] * capacity,
                "outgoing_vehicle_proxy": road["neighbor_density_proxy"] * capacity,
                "flow_variance_index": road["duration_std_mins"] / max(road["avg_duration_mins"], 1.0),
                "neighbor_capacity_ratio": capacity / max(road.get("neighbor_capacity_proxy", 100.0), 1.0),
                "road_load_ratio": road["historical_density_proxy"] * delay_ratio,
                "y_congestion_pressure": target,
            }
        )
    return pd.DataFrame(rows).dropna()


def evaluate_model(name: str, model, X: pd.DataFrame, y: pd.Series) -> dict:
    splitter = TimeSeriesSplit(n_splits=5)
    fold_metrics = []
    importances = None

    for train_idx, test_idx in splitter.split(X):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        model.fit(X_train, y_train)
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X_test)[:, 1]
        else:
            proba = model.predict(X_test)
        pred = (proba >= 0.5).astype(int)
        cm = confusion_matrix(y_test, pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
        precision = precision_score(y_test, pred, zero_division=0)
        recall = recall_score(y_test, pred, zero_division=0)
        f1 = f1_score(y_test, pred, zero_division=0)
        try:
            auc = roc_auc_score(y_test, proba)
        except ValueError:
            auc = 0.0
        fold_metrics.append(
            {
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "roc_auc": auc,
                "false_positive_rate": fp / max(fp + tn, 1),
                "false_negative_rate": fn / max(fn + tp, 1),
                "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
            }
        )

    model.fit(X, y)
    if hasattr(model, "feature_importances_"):
        importances = {
            col: float(score)
            for col, score in sorted(
                zip(FEATURE_COLS, model.feature_importances_),
                key=lambda item: -item[1],
            )
        }

    summary = {
        "model": name,
        "folds": fold_metrics,
        "aggregate_confusion_matrix": {
            "tn": int(sum(m["confusion_matrix"]["tn"] for m in fold_metrics)),
            "fp": int(sum(m["confusion_matrix"]["fp"] for m in fold_metrics)),
            "fn": int(sum(m["confusion_matrix"]["fn"] for m in fold_metrics)),
            "tp": int(sum(m["confusion_matrix"]["tp"] for m in fold_metrics)),
        },
        "mean_precision": float(np.mean([m["precision"] for m in fold_metrics])),
        "mean_recall": float(np.mean([m["recall"] for m in fold_metrics])),
        "mean_f1": float(np.mean([m["f1"] for m in fold_metrics])),
        "mean_roc_auc": float(np.mean([m["roc_auc"] for m in fold_metrics])),
        "mean_false_positive_rate": float(np.mean([m["false_positive_rate"] for m in fold_metrics])),
        "mean_false_negative_rate": float(np.mean([m["false_negative_rate"] for m in fold_metrics])),
        "feature_importance": importances,
    }
    return summary, model


def main():
    print("=" * 60)
    print("GridSense - Train Traffic Intelligence Models")
    print("=" * 60)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    df = build_training_frame()
    X = df[FEATURE_COLS]
    y = df["y_congestion_pressure"]
    print(f"Rows: {len(df):,}")
    print(f"Positive rate: {y.mean() * 100:.1f}%")

    candidates = {
        "random_forest": RandomForestClassifier(
            n_estimators=250,
            max_depth=8,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
    }
    if XGBClassifier is not None:
        candidates["xgboost"] = XGBClassifier(
            n_estimators=250,
            max_depth=5,
            learning_rate=0.04,
            subsample=0.85,
            colsample_bytree=0.85,
            eval_metric="logloss",
            random_state=42,
            verbosity=0,
        )
    if LGBMClassifier is not None:
        candidates["lightgbm"] = LGBMClassifier(
            n_estimators=250,
            max_depth=5,
            learning_rate=0.04,
            class_weight="balanced",
            random_state=42,
            verbose=-1,
        )

    evaluations = {}
    fitted_models = {}
    feature_importance = {}
    for name, model in candidates.items():
        print(f"Training {name}...")
        summary, fitted = evaluate_model(name, model, X, y)
        evaluations[name] = summary
        fitted_models[name] = fitted
        if summary.get("feature_importance"):
            feature_importance[name] = summary["feature_importance"]
        print(
            f"  F1={summary['mean_f1']:.3f} "
            f"Precision={summary['mean_precision']:.3f} "
            f"Recall={summary['mean_recall']:.3f} "
            f"AUC={summary['mean_roc_auc']:.3f}"
        )

    best_model = max(evaluations.values(), key=lambda item: item["mean_f1"])["model"]

    payload = {
        "target_definition": (
            "Physical y_congestion_pressure = closure OR physical congestion cause OR duration >= p90."
        ),
        "best_model_by_f1": best_model,
        "feature_columns": FEATURE_COLS,
        "rows": int(len(df)),
        "positive_rate": float(y.mean()),
        "models": evaluations,
        "skipped_models": {
            "xgboost": XGBClassifier is None,
            "lightgbm": LGBMClassifier is None,
        },
    }
    with open(OUT_EVAL, "w") as f:
        json.dump(payload, f, indent=2)
    with open(OUT_IMPORTANCE, "w") as f:
        json.dump(
            {
                "best_model_by_f1": best_model,
                "feature_importance": feature_importance,
                "note": "Use this JSON for frontend bar charts after training.",
            },
            f,
            indent=2,
        )
    model_payload = {"features": FEATURE_COLS, "models": fitted_models}
    if joblib is not None:
        joblib.dump(model_payload, OUT_MODEL)
    else:
        with open(OUT_MODEL, "wb") as f:
            pickle.dump(model_payload, f)

    print(f"Saved models: {OUT_MODEL}")
    print(f"Saved evaluation: {OUT_EVAL}")
    print(f"Saved feature importance: {OUT_IMPORTANCE}")


if __name__ == "__main__":
    main()
