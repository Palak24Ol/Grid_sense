import pandas as pd
import joblib
import warnings
warnings.filterwarnings('ignore')

print("\n=== CHECK 1: Priority Class Imbalance ===")
df = pd.read_csv('data/processed/feature_matrix.csv')
print("Counts:")
print(df['y_priority'].value_counts())
print("\nPercentages:")
print(df['y_priority'].value_counts(normalize=True) * 100)

print("\n=== CHECK 2: Prophet Training Data (MekhriCircle) ===")
try:
    df_clean = pd.read_csv('data/processed/events_clean.csv')
    mekhri_rows = df_clean[df_clean['junction'] == 'MekhriCircle']
    print("Event Causes at MekhriCircle:")
    print(mekhri_rows['event_cause'].value_counts())
    print(f"\nTotal MekhriCircle rows: {len(mekhri_rows)}")
except Exception as e:
    print(f"Could not load events_clean.csv: {e}")

print("\n=== CHECK 3: Closure Model Features Expected ===")
model = joblib.load('ml/artifacts/closure_model.pkl')
print('Features the API needs to match EXACTLY:')
for i, f in enumerate(model.feature_names_in_, 1):
    print(f"{i:>2}. {f}")
