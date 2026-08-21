import numpy as np
from sklearn.cluster import DBSCAN


def detect_anomalies(X: np.ndarray, teammate_ids: list[str],
                      eps: float = 4.0, min_samples: int = 3) -> list[dict]:
    """
    Run DBSCAN on standardized teammate behavioral profiles.

    Parameters
    ----------
    X : np.ndarray — standardized feature matrix (output of StandardScaler)
    teammate_ids : list[str] — IDs aligned with each row in X
    eps, min_samples : DBSCAN parameters

    Returns
    -------
    list[dict], one per teammate: teammate_id, cluster_label, is_noise (bool)

    Design decisions:
        - Parameter sensitivity: for the real 22-teammate standardized matrix,
          eps=4.0 and min_samples=3 produced a real, non-trivial noise set.
          That setting is validated on this dataset but should still be treated as
          a data-dependent tuning choice rather than a guaranteed-stable default.
    """
    X = np.asarray(X, dtype=float)

    if X.ndim != 2:
        raise ValueError("X must be a 2D array with shape (n_samples, n_features).")
    if X.shape[0] == 0:
        if len(teammate_ids) == 0:
            return []
        raise ValueError("X is empty; teammate_ids must also be empty.")
    if len(teammate_ids) != X.shape[0]:
        raise ValueError("teammate_ids must have the same length as the number of rows in X.")
    if eps <= 0:
        raise ValueError("eps must be positive.")
    if min_samples < 1:
        raise ValueError("min_samples must be at least 1.")

    dbscan = DBSCAN(eps=eps, min_samples=min_samples)
    labels = dbscan.fit_predict(X)

    return [
        {
            "teammate_id": teammate_id,
            "cluster_label": int(label),
            "is_noise": bool(label == -1),
        }
        for teammate_id, label in zip(teammate_ids, labels)
    ]
