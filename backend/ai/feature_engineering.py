"""
Feature Engineering — QMS AI Module
Prepare, encode, and normalize features for ML models.
"""
import pandas as pd
import numpy as np
from typing import List, Optional


CATEGORICAL_COLS = ["machine_code", "shift", "operator_name", "material_batch", "defect_code"]
NUMERIC_COLS     = ["temperature", "humidity", "quantity_produced", "quantity_defective",
                    "defect_rate", "vibration", "pressure"]


def prepare_features(df: pd.DataFrame, fit: bool = True, encoders: Optional[dict] = None):
    """
    Full feature pipeline:
      1. Compute derived metrics (defect_rate, etc.)
      2. Fill nulls
      3. Label-encode categoricals
      4. Return (processed_df, encoders)
    """
    from sklearn.preprocessing import LabelEncoder

    df = df.copy()

    # --- Derived features ---
    if "quantity_defective" in df.columns and "quantity_produced" in df.columns:
        df["defect_rate"] = df.apply(
            lambda r: r["quantity_defective"] / r["quantity_produced"]
            if r["quantity_produced"] and r["quantity_produced"] > 0 else 0,
            axis=1
        )
        df["defect_rate_log"] = np.log1p(df["defect_rate"])

    if "temperature" in df.columns and "humidity" in df.columns:
        df["heat_index"] = df["temperature"].fillna(0) * 0.6 + df["humidity"].fillna(0) * 0.4

    # --- Fill nulls ---
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    for col in CATEGORICAL_COLS:
        if col in df.columns:
            df[col] = df[col].fillna("unknown").astype(str)

    # --- Encode categoricals ---
    if encoders is None:
        encoders = {}

    for col in CATEGORICAL_COLS:
        if col not in df.columns:
            continue
        if fit:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col])
            encoders[col] = le
        else:
            le = encoders.get(col)
            if le:
                known = set(le.classes_)
                df[col] = df[col].apply(lambda v: v if v in known else "unknown")
                # Ensure "unknown" is in classes
                if "unknown" not in known:
                    le.classes_ = np.append(le.classes_, "unknown")
                df[col] = le.transform(df[col])
            else:
                df[col] = 0

    return df, encoders


def get_feature_columns(df: pd.DataFrame) -> List[str]:
    """Return available feature columns from the dataframe."""
    candidates = NUMERIC_COLS + CATEGORICAL_COLS + [
        "defect_rate_log", "heat_index", "defect_rate"
    ]
    return [c for c in candidates if c in df.columns]
