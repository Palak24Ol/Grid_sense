import pandas as pd
import joblib
import numpy as np
import json
import warnings
import requests
warnings.filterwarnings('ignore')

print("\n=== TEST 1: Priority Model ===")
model_priority = joblib.load('ml/artifacts/priority_model.pkl')

df = pd.read_csv('data/processed/feature_matrix.csv')
sample = df.sample(10, random_state=42)

# Fixed: Explicitly select the exact feature columns the pipeline expects
X = sample[model_priority.feature_names_in_]
preds = model_priority.predict(X)

print("Junction                  | Actual Priority | Predicted | Match?")
print("-" * 65)
for i, (_, row) in enumerate(sample.iterrows()):
    actual = row['y_priority'] # Actual column name in your CSV
    pred = preds[i]
    print(f"{row.get('junction','?')[:25]:25s} | {str(actual):15s} | {str(pred):9s} | {'✅' if str(actual)==str(pred) else '❌'}")


print("\n=== TEST 2: Closure Model ===")
model_closure = joblib.load('ml/artifacts/closure_model.pkl')

closures = df[df['y_closure'] == 1].sample(5, random_state=1)
no_closures = df[df['y_closure'] == 0].sample(5, random_state=1)
sample_closure = pd.concat([closures, no_closures])

X_closure = sample_closure[model_closure.feature_names_in_]
probs = model_closure.predict_proba(X_closure)[:, 1]

print("Cause                | Actual Closure | Pred Prob | Correct?")
print("-" * 60)
for i, (_, row) in enumerate(sample_closure.iterrows()):
    actual = int(row['y_closure'])
    prob = round(probs[i], 2)
    pred = 1 if prob >= 0.5 else 0
    print(f"{row.get('event_cause','?')[:20]:20s} | {actual:14d} | {prob:.2f}      | {'✅' if pred==actual else '❌'}")


print("\n=== TEST 3: Prophet Forecast ===")
payload = joblib.load('ml/artifacts/prophet_models/MekhriCircle.pkl')

model_prophet = payload['model']
mae = payload.get('mae')
future = model_prophet.make_future_dataframe(periods=24, freq='h', include_history=False)
forecast = model_prophet.predict(future)

print(f"MAE: {mae}")
print(f"\nMekhriCircle — next 24h forecast:")
print(f"{'Hour':>5} | {'Predicted':>10} | {'Lower':>7} | {'Upper':>7} | Peak?")
print("-" * 55)
for _, row in forecast.iterrows():
    h = row['ds'].hour
    y = round(row['yhat'], 3)
    lo = round(row['yhat_lower'], 3)
    hi = round(row['yhat_upper'], 3)
    peak = "⚠️ PEAK" if y > 1.5 else ""
    print(f"{h:>5} | {y:>10} | {lo:>7} | {hi:>7} | {peak}")


print("\n=== TEST 4: Cascade Multiplier ===")
with open('ml/artifacts/cascade_multipliers.json') as f:
    data_cascade = json.load(f)

print("Event Cause               | Cascade Multiplier | Makes sense?")
print("-" * 65)
for cause, details in sorted(data_cascade.items(), key=lambda x: -x[1]['cascade_multiplier']):
    mult = details['cascade_multiplier']
    sense = "✅" if (
        (cause in ['protest', 'public_event', 'vip_movement'] and mult > 1.5) or
        (cause in ['vehicle_breakdown', 'pot_holes', 'procession'] and mult < 1.5)
    ) else "⚠️ CHECK"
    print(f"{cause:25s} | {mult:>18.2f}x | {sense}")


print("\n=== TEST 5: Blackspot Scores ===")
with open('ml/artifacts/blackspot_scores.json') as f:
    data_bs = json.load(f)

ranked = sorted(data_bs, key=lambda x: -x['total_incidents'])
print(f"{'Rank':>4} | {'Junction':30s} | {'Incidents':>9} | {'Corridor':20s} | {'Top Cause'}")
print("-" * 90)
for i, j in enumerate(ranked[:10], 1):
    flag = "⭐" if i == 1 else ""
    print(f"{i:>4} | {j['junction']:30s} | {j['total_incidents']:>9} | {j['corridor']:20s} | {j['top_cause']} {flag}")


print("\n=== TEST 6: End-to-End API ===")
try:
    response = requests.post(
        "http://localhost:8000/api/v1/predict/triage",
        json={
            "corridor": "Bellary Road 1",
            "junction": "MekhriCircle",
            "event_cause": "protest",
            "vehicle_type": "none",
            "hour_of_day": 23,
            "day_of_week": 5,
            "duration_mins": 90
        }
    )
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"API Error (Is the backend running?): {e}")