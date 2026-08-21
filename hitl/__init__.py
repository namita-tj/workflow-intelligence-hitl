"""HITL project package."""

# Expose the anomaly detector from the package using a relative import so
# importing `hitl` or `hitl.anomaly_detector` works regardless of how pytest
# or consumers set up sys.path.
from .anomaly_detector import detect_anomalies

__all__ = ["detect_anomalies"]
