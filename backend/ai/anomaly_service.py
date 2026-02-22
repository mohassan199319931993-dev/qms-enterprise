"""
Anomaly Service — QMS AI Module
Isolation Forest-based anomaly detection on production data.
"""
import logging
import pandas as pd
import numpy as np
from typing import List

logger = logging.getLogger(__name__)

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class AnomalyService:

    NUMERIC_FEATURES = [
        "quantity_defective", "quantity_produced", "defect_rate",
        "temperature", "humidity", "vibration", "pressure",
    ]

    @staticmethod
    def detect(df: pd.DataFrame, contamination: float = 0.08) -> pd.DataFrame:
        """
        Detect anomalous rows using Isolation Forest.
        Returns dataframe with 'anomaly_score' and 'is_anomaly' columns.
        """
        if not SKLEARN_AVAILABLE or df.empty:
            return pd.DataFrame()

        # Compute defect_rate if missing
        if "defect_rate" not in df.columns:
            df["defect_rate"] = df.apply(
                lambda r: r["quantity_defective"] / r["quantity_produced"]
                if r.get("quantity_produced", 0) > 0 else 0, axis=1
            )

        available = [c for c in AnomalyService.NUMERIC_FEATURES if c in df.columns]
        if len(available) < 2:
            return pd.DataFrame()

        X = df[available].fillna(0)

        # Scale first
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        iso = IsolationForest(
            contamination=contamination,
            n_estimators=200,
            random_state=42,
            n_jobs=-1,
        )
        iso.fit(X_scaled)

        df = df.copy()
        df["anomaly_flag"]  = iso.predict(X_scaled)          # -1 = anomaly
        df["anomaly_score"] = iso.score_samples(X_scaled)    # lower = more anomalous
        df["is_anomaly"]    = df["anomaly_flag"] == -1

        return df

    @staticmethod
    def format_alerts(df: pd.DataFrame) -> List[dict]:
        """Convert anomaly dataframe to list of alert dicts."""
        alerts = []
        anomalies = df[df["is_anomaly"] == True].copy()

        for _, row in anomalies.iterrows():
            score = float(row.get("anomaly_score", -0.5))
            severity = "critical" if score < -0.6 else "high" if score < -0.4 else "medium"

            machine = row.get("machine_code") or row.get("machine") or "Unknown"
            alert = {
                "defect_record_id":  int(row["id"]) if "id" in row and not pd.isna(row.get("id")) else None,
                "date":              str(row.get("defect_date", "")),
                "machine":           str(machine),
                "shift":             str(row.get("shift", "Unknown")),
                "defect_rate":       round(float(row.get("defect_rate", 0)), 4),
                "quantity_defective": int(row.get("quantity_defective", 0)),
                "severity":          severity,
                "anomaly_score":     round(score, 4),
                "temperature":       float(row["temperature"]) if "temperature" in row and not pd.isna(row.get("temperature")) else None,
                "humidity":          float(row["humidity"])    if "humidity"    in row and not pd.isna(row.get("humidity"))    else None,
                "description":       f"Anomalous production pattern on machine {machine} — defect rate {round(float(row.get('defect_rate', 0))*100,2)}%",
            }
            alerts.append(alert)

        return sorted(alerts, key=lambda a: a["anomaly_score"])
