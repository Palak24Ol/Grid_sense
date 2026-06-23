"""
Gateway A - Operational AI training.

This gateway is for models that can be evaluated directly against labels in
the current incident dataset.

Implemented:
  - Cross-fold target encoding
  - Frequency encoding
  - Cause-corridor interactions
  - Cause-station interactions
  - Station load
  - Station closure rate
  - Zone closure rate
  - Random Forest, XGBoost, LightGBM candidates
  - Automatic best-model selection
  - Feature importance, confusion matrix, threshold analysis

Outputs:
  ml/gateway_a/models/
  ml/gateway_a/evaluations/
  ml/gateway_a/artifacts/
  ml/artifacts/gateway_a_report.json

Run:
  python ml/gateway_a/train_operational_ai.py
"""

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import LabelEncoder

try:
    from xgboost import XGBClassifier
except Exception:
    XGBClassifier = None

try:
    from lightgbm import LGBMClassifier
except Exception:
    LGBMClassifier = None


ROOT = Path(__file__).parent.parent.parent
DATA_PATH = ROOT / "data" / "processed" / "events_clean.csv"
GLOBAL_ARTIFACT_DIR = ROOT / "ml" / "artifacts"
GATEWAY_DIR = ROOT / "ml" / "gateway_a"
MODEL_DIR = GATEWAY_DIR / "models"
EVAL_DIR = GATEWAY_DIR / "evaluations"
ARTIFACT_DIR = GATEWAY_DIR / "artifacts"

for path in (MODEL_DIR, EVAL_DIR, ARTIFACT_DIR, GLOBAL_ARTIFACT_DIR):
    path.mkdir(parents=True, exist_ok=True)

GLOBAL_REPORT_PATH = GLOBAL_ARTIFACT_DIR / "gateway_a_report.json"
LOCAL_REPORT_PATH = EVAL_DIR / "gateway_a_report.json"

BASE_NUMERIC_COLS = [
    "latitude",
    "longitude",
    "hour_of_day",
    "day_of_week",
    "month",
    "is_high_priority_corridor",
    "is_non_corridor",
    "requires_road_closure",
]

CATEGORICAL_COLS = [
    "event_type",
    "event_cause",
    "corridor",
    "junction",
    "zone",
    "police_station",
    "vehicle_type",
    "cause_corridor_key",
    "cause_station_key",
]

TARGET_ENCODING_COLS = [
    "event_cause",
    "corridor",
    "police_station",
    "zone",
    "cause_corridor_key",
    "cause_station_key",
]

FREQUENCY_COLS = [
    "event_cause",
    "corridor",
    "police_station",
    "zone",
    "cause_corridor_key",
    "cause_station_key",
]

BINARY_THRESHOLD_SWEEP = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]


def save_json(path: Path, payload: dict) -> None:
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def clean_bool(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({"true": 1, "false": 0, "1": 1, "0": 0})
        .fillna(0)
        .astype(int)
    )


def load_incidents() -> pd.DataFrame:
    print(f"[gateway_a] Loading {DATA_PATH}")
    df = pd.read_csv(DATA_PATH, low_memory=False)
    df = df.copy()
    df["is_stale_active"] = clean_bool(df["is_stale_active"])
    df["is_high_priority_corridor"] = clean_bool(df["is_high_priority_corridor"])
    df["is_non_corridor"] = clean_bool(df["is_non_corridor"])
    df["requires_road_closure"] = clean_bool(df["requires_road_closure"])
    df["duration_mins"] = pd.to_numeric(df["duration_mins"], errors="coerce")

    for col in ["latitude", "longitude", "hour_of_day", "day_of_week", "month"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    for col in ["event_type", "event_cause", "corridor", "junction", "zone", "police_station", "vehicle_type"]:
        df[col] = df[col].fillna("__MISSING__").astype(str)

    df["cause_corridor_key"] = df["event_cause"] + "_" + df["corridor"]
    df["cause_station_key"] = df["event_cause"] + "_" + df["police_station"]
    df = df[df["is_stale_active"] == 0].copy()
    print(f"[gateway_a] Rows after stale filter: {len(df):,}")
    return df


def _smooth_binary_rates(values: pd.Series, y: pd.Series, global_rate: float, smoothing: float) -> dict:
    temp = pd.DataFrame({
        "key": values.fillna("__MISSING__").astype(str),
        "target": y.astype(float).values,
    })
    grouped = temp.groupby("key")["target"].agg(["sum", "count"])
    rates = (grouped["sum"] + global_rate * smoothing) / (grouped["count"] + smoothing)
    return rates.to_dict()


def add_binary_oof_encoding(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    y_train: pd.Series,
    cols: list[str],
    prefix: str,
    smoothing: float = 20.0,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    train_out = pd.DataFrame(index=train_df.index)
    test_out = pd.DataFrame(index=test_df.index)
    global_rate = float(y_train.mean())
    min_class = int(y_train.value_counts().min())
    n_splits = max(2, min(5, min_class))
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    feature_names = []

    for col in cols:
        out_col = f"{col}_{prefix}_rate"
        feature_names.append(out_col)
        train_out[out_col] = global_rate
        out_idx = train_out.columns.get_loc(out_col)

        for fit_idx, valid_idx in skf.split(train_df, y_train):
            rates = _smooth_binary_rates(train_df.iloc[fit_idx][col], y_train.iloc[fit_idx], global_rate, smoothing)
            valid_values = train_df.iloc[valid_idx][col].fillna("__MISSING__").astype(str)
            train_out.iloc[valid_idx, out_idx] = valid_values.map(rates).fillna(global_rate).values

        full_rates = _smooth_binary_rates(train_df[col], y_train, global_rate, smoothing)
        test_out[out_col] = test_df[col].fillna("__MISSING__").astype(str).map(full_rates).fillna(global_rate)

    return train_out, test_out, feature_names


def add_multiclass_oof_encoding(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    y_train: pd.Series,
    cols: list[str],
    prefix: str,
    smoothing: float = 20.0,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    classes = sorted(pd.Series(y_train).unique().tolist())
    train_parts = []
    test_parts = []
    feature_names = []
    for class_label in classes:
        binary_y = (y_train == class_label).astype(int)
        safe_class = str(class_label).lower().replace(" ", "_")
        train_enc, test_enc, names = add_binary_oof_encoding(
            train_df,
            test_df,
            binary_y,
            cols,
            prefix=f"{prefix}_{safe_class}",
            smoothing=smoothing,
        )
        train_parts.append(train_enc)
        test_parts.append(test_enc)
        feature_names.extend(names)
    return pd.concat(train_parts, axis=1), pd.concat(test_parts, axis=1), feature_names


def add_frequency_features(train_df: pd.DataFrame, test_df: pd.DataFrame, cols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    train_out = pd.DataFrame(index=train_df.index)
    test_out = pd.DataFrame(index=test_df.index)
    feature_names = []
    for col in cols:
        out_col = f"{col}_freq"
        feature_names.append(out_col)
        values = train_df[col].fillna("__MISSING__").astype(str)
        freqs = values.value_counts(normalize=True).to_dict()
        train_out[out_col] = values.map(freqs).fillna(0.0)
        test_out[out_col] = test_df[col].fillna("__MISSING__").astype(str).map(freqs).fillna(0.0)
    return train_out, test_out, feature_names


def add_station_load(train_df: pd.DataFrame, test_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    counts = train_df["police_station"].fillna("__MISSING__").astype(str).value_counts().to_dict()
    train_out = pd.DataFrame(index=train_df.index)
    test_out = pd.DataFrame(index=test_df.index)
    train_out["station_load"] = train_df["police_station"].fillna("__MISSING__").astype(str).map(counts).fillna(0)
    test_out["station_load"] = test_df["police_station"].fillna("__MISSING__").astype(str).map(counts).fillna(0)
    return train_out, test_out, ["station_load"]


def build_encoded_incident_features(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    y_train: pd.Series,
    task_name: str,
    multiclass: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], dict]:
    train_parts = [train_df[BASE_NUMERIC_COLS].apply(pd.to_numeric, errors="coerce").fillna(0.0)]
    test_parts = [test_df[BASE_NUMERIC_COLS].apply(pd.to_numeric, errors="coerce").fillna(0.0)]
    feature_names = BASE_NUMERIC_COLS.copy()

    freq_train, freq_test, freq_names = add_frequency_features(train_df, test_df, FREQUENCY_COLS)
    load_train, load_test, load_names = add_station_load(train_df, test_df)
    train_parts.extend([freq_train, load_train])
    test_parts.extend([freq_test, load_test])
    feature_names.extend(freq_names + load_names)

    if multiclass:
        target_train, target_test, target_names = add_multiclass_oof_encoding(
            train_df,
            test_df,
            y_train,
            TARGET_ENCODING_COLS,
            prefix=f"{task_name}_target",
        )
    else:
        target_train, target_test, target_names = add_binary_oof_encoding(
            train_df,
            test_df,
            y_train.astype(int),
            TARGET_ENCODING_COLS,
            prefix=f"{task_name}_target",
        )
    train_parts.append(target_train)
    test_parts.append(target_test)
    feature_names.extend(target_names)

    closure_train, closure_test, closure_names = add_binary_oof_encoding(
        train_df,
        test_df,
        train_df["requires_road_closure"].astype(int),
        ["police_station", "zone"],
        prefix="closure",
    )
    closure_train = closure_train.rename(columns={
        "police_station_closure_rate": "station_closure_rate",
    })
    closure_test = closure_test.rename(columns={
        "police_station_closure_rate": "station_closure_rate",
    })
    closure_names = ["station_closure_rate" if name == "police_station_closure_rate" else name for name in closure_names]
    train_parts.append(closure_train)
    test_parts.append(closure_test)
    feature_names.extend(closure_names)

    X_train = pd.concat(train_parts, axis=1).apply(pd.to_numeric, errors="coerce").fillna(0.0)
    X_test = pd.concat(test_parts, axis=1).apply(pd.to_numeric, errors="coerce").fillna(0.0)
    metadata = {
        "cross_fold_target_encoding": TARGET_ENCODING_COLS,
        "frequency_encoding": FREQUENCY_COLS,
        "interactions": ["cause_corridor_key", "cause_station_key"],
        "station_load": "incident count per police station from training split",
        "station_closure_rate": "cross-fold closure target encoding by police station",
        "zone_closure_rate": "cross-fold closure target encoding by zone",
    }
    return X_train, X_test, feature_names, metadata


def candidate_models(num_classes: int, class_weight: Any = "balanced") -> dict[str, Any]:
    models = {
        "random_forest": RandomForestClassifier(
            n_estimators=350,
            max_depth=16,
            min_samples_leaf=3,
            class_weight=class_weight,
            random_state=42,
            n_jobs=-1,
        )
    }
    if XGBClassifier is not None:
        if num_classes == 2:
            models["xgboost"] = XGBClassifier(
                n_estimators=300,
                max_depth=6,
                learning_rate=0.04,
                subsample=0.85,
                colsample_bytree=0.85,
                eval_metric="logloss",
                random_state=42,
                verbosity=0,
            )
        else:
            models["xgboost"] = XGBClassifier(
                n_estimators=300,
                max_depth=6,
                learning_rate=0.04,
                subsample=0.85,
                colsample_bytree=0.85,
                objective="multi:softprob",
                num_class=num_classes,
                eval_metric="mlogloss",
                random_state=42,
                verbosity=0,
            )
    if LGBMClassifier is not None:
        models["lightgbm"] = LGBMClassifier(
            n_estimators=300,
            max_depth=8,
            learning_rate=0.04,
            class_weight=class_weight,
            random_state=42,
            verbose=-1,
        )
    return models


def feature_importance(model: Any, feature_names: list[str]) -> list[dict]:
    if not hasattr(model, "feature_importances_"):
        return []
    ranked = sorted(
        zip(feature_names, model.feature_importances_),
        key=lambda item: -float(item[1]),
    )
    total = sum(float(v) for _, v in ranked) or 1.0
    cumulative = 0.0
    rows = []
    for rank, (feature, importance) in enumerate(ranked, start=1):
        importance = float(importance)
        cumulative += importance
        rows.append({
            "rank": rank,
            "feature": feature,
            "importance": importance,
            "importance_pct": importance / total * 100.0,
            "cumulative_importance_pct": cumulative / total * 100.0,
        })
    return rows


def binary_threshold_analysis(y_true: np.ndarray, proba: np.ndarray, auc: float) -> list[dict]:
    rows = []
    for threshold in BINARY_THRESHOLD_SWEEP:
        preds = (proba >= threshold).astype(int)
        cm = confusion_matrix(y_true, preds, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
        rows.append({
            "threshold": threshold,
            "accuracy": float(accuracy_score(y_true, preds)),
            "precision": float(precision_score(y_true, preds, zero_division=0)),
            "recall": float(recall_score(y_true, preds, zero_division=0)),
            "f1": float(f1_score(y_true, preds, zero_division=0)),
            "roc_auc": float(auc),
            "fpr": float(fp / max(fp + tn, 1)),
            "fnr": float(fn / max(fn + tp, 1)),
            "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        })
    return rows


def evaluate_binary_model(model: Any, X_test: pd.DataFrame, y_test: np.ndarray) -> dict:
    preds = model.predict(X_test)
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(X_test)[:, 1]
    else:
        proba = preds
    auc = roc_auc_score(y_test, proba)
    cm = confusion_matrix(y_test, preds, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    thresholds = binary_threshold_analysis(y_test, proba, auc)
    best_f1_threshold = max(thresholds, key=lambda row: (row["f1"], row["precision"], row["recall"]))
    return {
        "accuracy": float(accuracy_score(y_test, preds)),
        "precision": float(precision_score(y_test, preds, zero_division=0)),
        "recall": float(recall_score(y_test, preds, zero_division=0)),
        "f1": float(f1_score(y_test, preds, zero_division=0)),
        "roc_auc": float(auc),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "threshold_analysis": thresholds,
        "best_f1_threshold": best_f1_threshold,
    }


def evaluate_multiclass_model(model: Any, X_test: pd.DataFrame, y_test: np.ndarray, labels: list[str]) -> dict:
    preds = model.predict(X_test)
    cm = confusion_matrix(y_test, preds, labels=list(range(len(labels))))
    return {
        "accuracy": float(accuracy_score(y_test, preds)),
        "macro_precision": float(precision_score(y_test, preds, average="macro", zero_division=0)),
        "macro_recall": float(recall_score(y_test, preds, average="macro", zero_division=0)),
        "macro_f1": float(f1_score(y_test, preds, average="macro", zero_division=0)),
        "labels": labels,
        "confusion_matrix": cm.astype(int).tolist(),
    }


def select_best_binary(results: dict[str, dict]) -> str:
    return max(
        results,
        key=lambda name: (
            results[name]["metrics"]["best_f1_threshold"]["f1"],
            results[name]["metrics"]["best_f1_threshold"]["precision"],
            results[name]["metrics"]["best_f1_threshold"]["recall"],
            results[name]["metrics"]["roc_auc"],
        ),
    )


def select_best_multiclass(results: dict[str, dict]) -> str:
    return max(
        results,
        key=lambda name: (
            results[name]["metrics"].get("macro_f1", results[name]["metrics"].get("f1", 0.0)),
            results[name]["metrics"].get("accuracy", 0.0),
        ),
    )


def train_high_priority(df: pd.DataFrame) -> dict:
    print("\n[gateway_a] Training High Priority Incident Prediction")
    model_df = df.dropna(subset=["priority"]).copy()
    y = model_df["priority"].astype(str).str.strip().str.lower().eq("high").astype(int)
    train_df, test_df, y_train, y_test = train_test_split(
        model_df,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )
    X_train, X_test, feature_names, feature_metadata = build_encoded_incident_features(
        train_df,
        test_df,
        y_train,
        task_name="priority",
        multiclass=False,
    )
    results = {}
    for name, model in candidate_models(num_classes=2).items():
        print(f"  Training {name}...")
        model.fit(X_train, y_train)
        metrics = evaluate_binary_model(model, X_test, y_test.values)
        results[name] = {
            "metrics": metrics,
            "feature_importance": feature_importance(model, feature_names),
        }
        joblib.dump(model, MODEL_DIR / f"high_priority_{name}.pkl")
        print(
            f"    Accuracy={metrics['accuracy']:.4f} Precision={metrics['precision']:.4f} "
            f"Recall={metrics['recall']:.4f} F1={metrics['f1']:.4f} ROC-AUC={metrics['roc_auc']:.4f}"
        )
    best_model = select_best_binary(results)
    payload = {
        "task": "high_priority_incident_prediction",
        "target": "priority == High",
        "rows": int(len(model_df)),
        "positive_rate": float(y.mean()),
        "feature_metadata": feature_metadata,
        "candidate_models": results,
        "best_model": best_model,
        "selection_metric": "best threshold F1, then precision, recall, ROC-AUC",
    }
    save_json(EVAL_DIR / "high_priority_incident_gateway_a_evaluation.json", payload)
    return payload


def duration_bucket(duration: float) -> str:
    if duration <= 30:
        return "Short"
    if duration <= 90:
        return "Medium"
    return "Long"


def train_duration_bucket(df: pd.DataFrame) -> dict:
    print("\n[gateway_a] Training Duration Bucket Prediction")
    model_df = df[df["duration_mins"].between(0, 5000)].copy()
    model_df["duration_bucket"] = model_df["duration_mins"].apply(duration_bucket)
    y_raw = model_df["duration_bucket"]
    label_encoder = LabelEncoder()
    y = pd.Series(label_encoder.fit_transform(y_raw), index=model_df.index)
    labels = label_encoder.classes_.tolist()
    train_df, test_df, y_train, y_test = train_test_split(
        model_df,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )
    X_train, X_test, feature_names, feature_metadata = build_encoded_incident_features(
        train_df,
        test_df,
        y_train,
        task_name="duration",
        multiclass=True,
    )
    results = {}
    for name, model in candidate_models(num_classes=len(labels)).items():
        print(f"  Training {name}...")
        model.fit(X_train, y_train)
        metrics = evaluate_multiclass_model(model, X_test, y_test.values, labels)
        results[name] = {
            "metrics": metrics,
            "feature_importance": feature_importance(model, feature_names),
        }
        joblib.dump({"model": model, "label_encoder": label_encoder}, MODEL_DIR / f"duration_bucket_{name}.pkl")
        print(
            f"    Accuracy={metrics['accuracy']:.4f} MacroPrecision={metrics['macro_precision']:.4f} "
            f"MacroRecall={metrics['macro_recall']:.4f} MacroF1={metrics['macro_f1']:.4f}"
        )
    best_model = select_best_multiclass(results)
    payload = {
        "task": "duration_bucket_prediction",
        "target": "Short=0-30 mins, Medium=30-90 mins, Long=90+ mins",
        "rows": int(len(model_df)),
        "class_distribution": {label: int(count) for label, count in y_raw.value_counts().to_dict().items()},
        "feature_metadata": feature_metadata,
        "candidate_models": results,
        "best_model": best_model,
        "selection_metric": "macro F1, then accuracy",
    }
    save_json(EVAL_DIR / "duration_bucket_gateway_a_evaluation.json", payload)
    return payload


def minmax(series: pd.Series) -> pd.Series:
    if series.max() == series.min():
        return pd.Series(0.0, index=series.index)
    return (series - series.min()) / (series.max() - series.min())


def build_corridor_risk_table(df: pd.DataFrame) -> pd.DataFrame:
    parsed_time = pd.to_datetime(df["start_datetime"], errors="coerce")
    observed_days = max(1, (parsed_time.max() - parsed_time.min()).days + 1)
    table_df = df[df["corridor"].notna()].copy()
    table_df["priority_high"] = table_df["priority"].astype(str).str.strip().str.lower().eq("high").astype(int)
    table = table_df.groupby("corridor").agg(
        incident_count=("id", "count"),
        closure_rate=("requires_road_closure", "mean"),
        priority_frequency=("priority_high", "mean"),
        average_duration=("duration_mins", "mean"),
        station_count=("police_station", "nunique"),
        zone_count=("zone", "nunique"),
    ).reset_index()
    table["incident_frequency"] = table["incident_count"] / observed_days
    table["average_duration"] = table["average_duration"].fillna(table["average_duration"].median())
    table["risk_score"] = (
        0.30 * minmax(table["incident_frequency"])
        + 0.30 * table["closure_rate"].fillna(0)
        + 0.25 * table["priority_frequency"].fillna(0)
        + 0.15 * minmax(table["average_duration"])
    )
    labels = ["Low", "Medium", "High", "Critical"]
    table["risk_label"] = pd.qcut(table["risk_score"], q=4, labels=labels, duplicates="drop").astype(str)
    return table


def train_corridor_risk(df: pd.DataFrame) -> dict:
    print("\n[gateway_a] Training Corridor Risk Classification")
    table = build_corridor_risk_table(df)
    feature_cols = [
        "closure_rate",
        "incident_frequency",
        "priority_frequency",
        "average_duration",
        "station_count",
        "zone_count",
    ]
    X = table[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    label_encoder = LabelEncoder()
    y = pd.Series(label_encoder.fit_transform(table["risk_label"]), index=table.index)
    labels = label_encoder.classes_.tolist()
    stratify = y if y.value_counts().min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.35,
        random_state=42,
        stratify=stratify,
    )
    results = {}
    for name, model in candidate_models(num_classes=len(labels)).items():
        print(f"  Training {name}...")
        model.fit(X_train, y_train)
        metrics = evaluate_multiclass_model(model, X_test, y_test.values, labels)
        results[name] = {
            "metrics": {
                "accuracy": metrics["accuracy"],
                "precision": metrics["macro_precision"],
                "recall": metrics["macro_recall"],
                "f1": metrics["macro_f1"],
                "labels": metrics["labels"],
                "confusion_matrix": metrics["confusion_matrix"],
            },
            "feature_importance": feature_importance(model, feature_cols),
        }
        joblib.dump({"model": model, "label_encoder": label_encoder}, MODEL_DIR / f"corridor_risk_{name}.pkl")
        print(
            f"    Accuracy={metrics['accuracy']:.4f} Precision={metrics['macro_precision']:.4f} "
            f"Recall={metrics['macro_recall']:.4f} F1={metrics['macro_f1']:.4f}"
        )
    best_model = select_best_multiclass(results)
    table.to_csv(ARTIFACT_DIR / "corridor_risk_training_table.csv", index=False)
    payload = {
        "task": "corridor_risk_classification",
        "target": "Historical corridor risk label: Low, Medium, High, Critical",
        "rows": int(len(table)),
        "class_distribution": {label: int(count) for label, count in table["risk_label"].value_counts().to_dict().items()},
        "feature_columns": feature_cols,
        "candidate_models": results,
        "best_model": best_model,
        "selection_metric": "macro F1, then accuracy",
        "note": "Risk labels are generated from historical aggregate statistics.",
    }
    save_json(EVAL_DIR / "corridor_risk_gateway_a_evaluation.json", payload)
    return payload


def summarize_task(payload: dict) -> dict:
    best = payload["best_model"]
    metrics = payload["candidate_models"][best]["metrics"]
    return {
        "best_model": best,
        "metrics": {
            key: value
            for key, value in metrics.items()
            if key in {
                "accuracy",
                "precision",
                "recall",
                "f1",
                "roc_auc",
                "macro_precision",
                "macro_recall",
                "macro_f1",
            }
        },
    }


def main() -> None:
    print("=" * 60)
    print("Gateway A - Operational AI")
    print("=" * 60)
    df = load_incidents()
    report = {
        "gateway": "A",
        "name": "Operational AI",
        "goal": "Maximize precision, recall, and F1 using current datasets only.",
        "implemented": [
            "cross-fold target encoding",
            "frequency encoding",
            "cause-corridor interactions",
            "cause-station interactions",
            "station load",
            "station closure rate",
            "zone closure rate",
            "Random Forest",
            "XGBoost",
            "LightGBM",
            "automatic best model selection",
            "feature importance",
            "confusion matrix",
            "threshold analysis for binary tasks",
        ],
        "tasks": {
            "high_priority_incident_prediction": train_high_priority(df),
            "duration_bucket_prediction": train_duration_bucket(df),
            "corridor_risk_classification": train_corridor_risk(df),
        },
    }
    report["summary"] = {task: summarize_task(payload) for task, payload in report["tasks"].items()}
    report["outputs"] = {
        "models": str(MODEL_DIR),
        "evaluations": str(EVAL_DIR),
        "artifacts": str(ARTIFACT_DIR),
        "global_report": str(GLOBAL_REPORT_PATH),
    }
    save_json(GLOBAL_REPORT_PATH, report)
    save_json(LOCAL_REPORT_PATH, report)
    save_json(ARTIFACT_DIR / "gateway_a_manifest.json", {
        "gateway": report["gateway"],
        "name": report["name"],
        "summary": report["summary"],
        "outputs": report["outputs"],
    })
    print(f"\n[gateway_a] Global report saved -> {GLOBAL_REPORT_PATH}")
    print(f"[gateway_a] Local report saved -> {LOCAL_REPORT_PATH}")


if __name__ == "__main__":
    main()
