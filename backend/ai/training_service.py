"""
Training Service — QMS AI Module
Train defect prediction & anomaly models per factory.
Weekly retraining via APScheduler.
"""
import logging
import json
from typing import Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score,
        roc_auc_score, classification_report
    )
    from sklearn.calibration import CalibratedClassifierCV
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn unavailable — training disabled")

from ai.feature_engineering import prepare_features, get_feature_columns
from ai.model_registry import ModelRegistry


class TrainingService:

    @staticmethod
    def train_defect_model(df: pd.DataFrame, factory_id: int) -> dict:
        """
        Train RandomForest with calibration for defect probability.
        Returns detailed metrics dict.
        """
        if not SKLEARN_AVAILABLE:
            return {"status": "error", "error": "scikit-learn not installed"}

        if df.empty or len(df) < 50:
            return {"status": "error", "error": f"Insufficient data: {len(df)} rows (need ≥50)"}

        # Feature engineering
        df, encoders = prepare_features(df, fit=True)
        feature_cols = get_feature_columns(df)

        target = "has_defect"
        if target not in df.columns:
            if "quantity_defective" in df.columns:
                df[target] = (df["quantity_defective"] > 0).astype(int)
            else:
                return {"status": "error", "error": "Target column 'has_defect' not found"}

        df = df.dropna(subset=[target])
        X = df[feature_cols].fillna(0)
        y = df[target].astype(int)

        if len(y.unique()) < 2:
            return {"status": "error", "error": "Single class in training data — cannot train"}

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # Base model
        base = RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )

        # Calibrate for reliable probabilities
        model = CalibratedClassifierCV(base, cv=3, method="isotonic")
        model.fit(X_train, y_train)

        y_pred  = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]

        metrics = {
            "accuracy":  round(float(accuracy_score(y_test, y_pred)), 4),
            "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
            "recall":    round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
            "f1":        round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        }
        try:
            metrics["roc_auc"] = round(float(roc_auc_score(y_test, y_proba)), 4)
        except Exception:
            metrics["roc_auc"] = None

        # Feature importance from base estimator
        try:
            importances = dict(zip(
                feature_cols,
                base.fit(X_train, y_train).feature_importances_.tolist()
            ))
        except Exception:
            importances = {}

        meta = {
            "factory_id":         factory_id,
            "feature_cols":       feature_cols,
            "encoders_path":      "",  # set after save
            "metrics":            metrics,
            "samples_train":      len(X_train),
            "samples_test":       len(X_test),
            "feature_importance": importances,
            "class_distribution": y.value_counts().to_dict(),
            "report":             classification_report(y_test, y_pred, output_dict=True),
        }

        # Save model
        model_path = ModelRegistry.save(factory_id, "defect", model, meta)

        # Save encoders separately
        import joblib, os
        enc_path = model_path.replace(".pkl", ".encoders.pkl")
        joblib.dump({"encoders": encoders, "feature_cols": feature_cols}, enc_path)
        meta["encoders_path"] = enc_path

        return {
            "status":         "success",
            "model_path":     model_path,
            "metrics":        metrics,
            "samples_trained": len(X_train),
            "samples_tested":  len(X_test),
            "feature_importance": importances,
        }
