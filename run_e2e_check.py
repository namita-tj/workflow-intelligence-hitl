from hitl.rule_based_detector import find_metric_breaches, THRESHOLDS
from hitl.ledger import process_finding
import pandas as pd

t023 = pd.Series({
    "Teammate ID": "T-023", "ETA Achievement": 0.1125, "Rework Rate": 0.0,
    "Req. Understanding Ratio": 0.0, "Meeting Overhead Ratio": 0.028125,
    "Idle Rate": 0.359375, "Effective Utilisation": 0.1125, "Avg Time Per Task": 20.0,
})
breaches = find_metric_breaches(t023, THRESHOLDS)
idle_breach = next(b for b in breaches if b["metric"] == "Idle Rate")

result = process_finding(idle_breach, backend="ollama")
print("\n--- RESULT ---")
print(result)