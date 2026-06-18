import joblib

print("\n=== CHECK 4: Encoder Class Mappings ===")
# Check what the encoders actually map
encoders = joblib.load('ml/artifacts/encoders.pkl')

if isinstance(encoders, dict):
    for name, enc in encoders.items():
        print(f"\n--- {name.upper()} ---")
        if hasattr(enc, 'classes_'):
            for i, c in enumerate(enc.classes_):
                print(f"  {i} = {c}")
        else:
            print("  (Not a LabelEncoder or missing classes_)")
else:
    print("Encoders object is not a dictionary. Type:", type(encoders))
