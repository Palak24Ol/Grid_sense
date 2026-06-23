"""
Print traffic-intelligence model metrics after training.

Run:
    python ml/evaluation/evaluate_traffic_intelligence.py

Requires:
    ml/pipeline/12_train_traffic_intelligence.py must have generated
    ml/artifacts/traffic_intelligence_evaluation.json
"""

import json
from pathlib import Path


ROOT = Path(__file__).parent.parent.parent
EVAL_PATH = ROOT / "ml" / "artifacts" / "traffic_intelligence_evaluation.json"


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def main():
    print("=" * 60)
    print("GridSense - Traffic Intelligence Evaluation")
    print("=" * 60)
    if not EVAL_PATH.exists():
        print(f"Missing {EVAL_PATH}")
        print("Run: python ml/pipeline/12_train_traffic_intelligence.py")
        return

    with open(EVAL_PATH) as f:
        payload = json.load(f)

    print(f"Rows: {payload['rows']:,}")
    print(f"Positive rate: {pct(payload['positive_rate'])}")
    print(f"Best model by F1: {payload['best_model_by_f1']}")
    print(f"Target: {payload['target_definition']}")
    print()

    for name, metrics in payload["models"].items():
        cm = metrics["aggregate_confusion_matrix"]
        print(f"{name}")
        print(f"  Precision: {metrics['mean_precision']:.4f}")
        print(f"  Recall:    {metrics['mean_recall']:.4f}")
        print(f"  F1:        {metrics['mean_f1']:.4f}")
        print(f"  ROC-AUC:   {metrics['mean_roc_auc']:.4f}")
        print(f"  FPR:       {metrics['mean_false_positive_rate']:.4f}")
        print(f"  FNR:       {metrics['mean_false_negative_rate']:.4f}")
        print(f"  Confusion: TN={cm['tn']} FP={cm['fp']} FN={cm['fn']} TP={cm['tp']}")
        importance = metrics.get("feature_importance") or {}
        if importance:
            top = list(importance.items())[:5]
            print("  Top features:")
            for feature, score in top:
                print(f"    {feature}: {score:.4f}")
        print()


if __name__ == "__main__":
    main()
