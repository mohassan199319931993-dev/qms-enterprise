"""
Model Service — QMS AI Module
Real-time defect probability prediction using trained models.
"""
import logging
import pandas as pd
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import joblib
    JOBLIB_AVAILABLE = True
except ImportError:
    JOBLIB_AVAILABLE = False

from ai.model_registry import ModelRegistry
from ai.feature_engineering import prepare_features, get_feature_columns


class ModelService:

    @staticmethod
    def predict_defect(factory_id: int, input_data: dict) -> dict:
        """
        Predict defect probability for a single production record.
        Returns probability, risk level, and recommendation.
        """
        if not JOBLIB_AVAILABLE:
            return ModelService._mock_prediction()

        model, meta = ModelRegistry.load(factory_id, "defect")
        if model is None:
            return {
                "status":  "no_model",
                "error":   "No trained model found. Run POST /api/ai/train first.",
                "factory": factory_id,
            }

        feature_cols = meta.get("feature_cols", [])
        enc_path     = meta.get("encoders_path", "")

        encoders = {}
        if enc_path:
            try:
                enc_data = joblib.load(enc_path)
                encoders = enc_data.get("encoders", {})
            except Exception as e:
                logger.warning(f"Could not load encoders: {e}")

        # Build single-row dataframe
        df = pd.DataFrame([input_data])
        df, _ = prepare_features(df, fit=False, encoders=encoders)

        # Align columns
        for col in feature_cols:
            if col not in df.columns:
                df[col] = 0

        X = df[feature_cols].fillna(0)

        try:
            prob = float(model.predict_proba(X)[0][1])
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {"status": "error", "error": str(e)}

        risk_level = (
            "critical" if prob > 0.75 else
            "high"     if prob > 0.55 else
            "medium"   if prob > 0.30 else
            "low"
        )

        return {
            "defect_probability": round(prob, 4),
            "defect_predicted":   prob > 0.50,
            "risk_level":         risk_level,
            "confidence_pct":     round(prob * 100, 1),
            "recommendation":     ModelService._recommendation(prob),
            "source":             "model",
            "model_accuracy":     meta.get("metrics", {}).get("accuracy"),
        }

    @staticmethod
    def _recommendation(prob: float) -> str:
        if prob > 0.75:
            return "🔴 STOP production. Inspect machine & material batch immediately."
        elif prob > 0.55:
            return "🟠 HIGH RISK — Increase sampling rate. Alert supervisor now."
        elif prob > 0.30:
            return "🟡 MEDIUM — Monitor closely. Review calibration & operator logs."
        else:
            return "🟢 LOW — Conditions acceptable. Continue standard monitoring."

    @staticmethod
    def _mock_prediction() -> dict:
        import random
        prob = random.uniform(0.05, 0.45)
        return {
            "defect_probability": round(prob, 4),
            "defect_predicted":   prob > 0.35,
            "risk_level":         "medium" if prob > 0.25 else "low",
            "confidence_pct":     round(prob * 100, 1),
            "recommendation":     ModelService._recommendation(prob),
            "source":             "mock",
        }

    @staticmethod
    def get_model_info(factory_id: int) -> dict:
        """Return metadata for current active model."""
        if not ModelRegistry.exists(factory_id, "defect"):
            return {"trained": False, "factory_id": factory_id}

        _, meta = ModelRegistry.load(factory_id, "defect")
        return {
            "trained":         True,
            "factory_id":      factory_id,
            "metrics":         meta.get("metrics", {}),
            "samples_trained": meta.get("samples_train", 0),
            "feature_cols":    meta.get("feature_cols", []),
            "saved_at":        meta.get("saved_at"),
            "versions":        ModelRegistry.list_versions(factory_id, "defect"),
        }
