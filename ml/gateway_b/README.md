# Gateway B - Traffic Intelligence

Simulation, forecasting, and decision-support layer.

Kept features:
- Road Stress
- Shockwave
- Vehicle Surge
- Domino
- Congestion Cost

These should not be positioned as high-accuracy production ML without live
traffic labels.

Run:

```bash
python ml/gateway_b/package_traffic_intelligence.py
```

Outputs:
- `simulation_outputs/`
- `feature_importance/`
- `risk_profiles/`
- `evaluations/`
