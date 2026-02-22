"""
AI Quality Prediction Service — v3.1
Delegates to new ai/ module with graceful fallback.
"""
import os
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import text
from models import db

logger = logging.getLogger(__name__)

# ── New AI Module ────────────────────────────────────────────────
try:
    from ai.training_service import TrainingService as _Training
    from ai.model_service    import ModelService    as _Model
    from ai.anomaly_service  import AnomalyService  as _Anomaly
    from ai.model_registry   import ModelRegistry
    AI_MODULE = True
except ImportError:
    AI_MODULE = False
    logger.warning("ai/ module unavailable — using legacy sklearn path")

# ── Legacy sklearn ───────────────────────────────────────────────
try:
    from sklearn.ensemble import RandomForestClassifier, IsolationForest
    from sklearn.preprocessing import LabelEncoder
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, classification_report
    import joblib
    SKLEARN = True
except ImportError:
    SKLEARN = False

MODEL_DIR = os.environ.get("MODEL_DIR", "/app/models")
os.makedirs(MODEL_DIR, exist_ok=True)


class AIService:

    # ── Data Fetching ────────────────────────────────────────────
    @staticmethod
    def _get_training_data(factory_id: int) -> pd.DataFrame:
        sql = """
            SELECT
                dr.id, dr.defect_date,
                dr.quantity_defective, dr.quantity_produced,
                dr.shift,
                m.code AS machine_code,
                u.name AS operator_name,
                pr.material_batch, pr.temperature, pr.humidity,
                dc.code AS defect_code,
                CASE WHEN dr.quantity_defective > 0 THEN 1 ELSE 0 END AS has_defect,
                CASE WHEN pr.actual_quantity > 0
                     THEN dr.quantity_defective::FLOAT / NULLIF(pr.actual_quantity, 0)
                     ELSE 0 END AS defect_rate
            FROM defect_records dr
            LEFT JOIN machines m        ON m.id  = dr.machine_id
            LEFT JOIN users u           ON u.id  = dr.operator_id
            LEFT JOIN production_records pr ON pr.id = dr.production_record_id
            LEFT JOIN defect_codes dc   ON dc.id = dr.defect_code_id
            WHERE dr.factory_id = :fid
              AND dr.deleted_at IS NULL
            ORDER BY dr.defect_date DESC
            LIMIT 10000
        """
        rows = db.session.execute(text(sql), {"fid": factory_id}).fetchall()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r._mapping) for r in rows])

    # ── Train ────────────────────────────────────────────────────
    @staticmethod
    def train_defect_model(factory_id: int) -> dict:
        df = AIService._get_training_data(factory_id)
        if df.empty or len(df) < 50:
            return {"status": "error", "error": f"Insufficient data: {len(df)} rows (≥50 needed)"}

        if AI_MODULE:
            result = _Training.train_defect_model(df, factory_id)
        elif SKLEARN:
            result = AIService._legacy_train(df, factory_id)
        else:
            return {"status": "error", "error": "No ML library available"}

        # Persist metadata
        if result.get("status") == "success":
            try:
                acc = result.get("metrics", {}).get("accuracy") or result.get("accuracy", 0)
                db.session.execute(text("""
                    INSERT INTO ai_models
                        (factory_id, model_name, model_type, model_path, accuracy, trained_at, is_active)
                    VALUES
                        (:fid, 'defect_predictor', 'random_forest', :path, :acc, NOW(), TRUE)
                    ON CONFLICT DO NOTHING
                """), {"fid": factory_id, "path": result.get("model_path", ""), "acc": acc})
                db.session.commit()
            except Exception as e:
                logger.warning(f"Model metadata persist failed: {e}")
                db.session.rollback()

        return result

    # ── Predict ──────────────────────────────────────────────────
    @staticmethod
    def predict_defect_probability(factory_id: int, input_data: dict) -> dict:
        if AI_MODULE:
            result = _Model.predict_defect(factory_id, input_data)
        elif SKLEARN:
            result = AIService._legacy_predict(factory_id, input_data)
        else:
            import random
            prob = random.uniform(0.05, 0.45)
            result = {
                "defect_probability": round(prob, 4),
                "defect_predicted": prob > 0.35,
                "risk_level": "medium" if prob > 0.25 else "low",
                "recommendation": AIService._recommendation(prob),
                "source": "mock",
            }

        # Store prediction in DB
        try:
            db.session.execute(text("""
                INSERT INTO ai_predictions
                    (factory_id, prediction_type, input_data, prediction_result, confidence)
                VALUES (:fid, 'defect_probability', :inp, :res, :conf)
            """), {
                "fid":  factory_id,
                "inp":  json.dumps(input_data),
                "res":  json.dumps(result),
                "conf": result.get("defect_probability", 0),
            })
            db.session.commit()
        except Exception as e:
            logger.warning(f"Prediction persist failed: {e}")
            db.session.rollback()

        return result

    # ── Anomaly Detection ────────────────────────────────────────
    @staticmethod
    def detect_anomaly(factory_id: int, days: int = 30) -> list:
        sql = """
            SELECT
                dr.id, dr.defect_date, dr.shift,
                m.code AS machine_code,
                dr.quantity_defective, dr.quantity_produced,
                CASE WHEN dr.quantity_produced > 0
                     THEN dr.quantity_defective::FLOAT / dr.quantity_produced ELSE 0 END AS defect_rate,
                pr.temperature, pr.humidity
            FROM defect_records dr
            LEFT JOIN machines m ON m.id = dr.machine_id
            LEFT JOIN production_records pr ON pr.id = dr.production_record_id
            WHERE dr.factory_id = :fid
              AND dr.deleted_at IS NULL
              AND dr.defect_date >= CURRENT_DATE - :days * INTERVAL '1 day'
        """
        rows = db.session.execute(text(sql), {"fid": factory_id, "days": days}).fetchall()
        if len(rows) < 10:
            return []

        df = pd.DataFrame([dict(r._mapping) for r in rows])

        if AI_MODULE:
            df_result = _Anomaly.detect(df)
            if df_result.empty:
                return []
            alerts = _Anomaly.format_alerts(df_result)
        elif SKLEARN:
            alerts = AIService._legacy_anomaly(df, factory_id)
        else:
            return []

        # Persist alerts
        for alert in alerts:
            try:
                db.session.execute(text("""
                    INSERT INTO anomaly_alerts
                        (factory_id, machine_id, alert_type, severity, description, data_point, created_at)
                    SELECT :fid, m.id, 'production_anomaly', :sev, :desc, :data, NOW()
                    FROM machines m
                    WHERE m.code = :code AND m.factory_id = :fid
                    LIMIT 1
                """), {
                    "fid":  factory_id,
                    "sev":  alert["severity"],
                    "desc": alert["description"],
                    "data": json.dumps(alert),
                    "code": str(alert.get("machine", "")),
                })
            except Exception:
                pass
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        return alerts

    # ── Corrective Actions ───────────────────────────────────────
    @staticmethod
    def recommend_corrective_action(factory_id: int, defect_code: str,
                                    machine_code: Optional[str] = None) -> list:
        sql = """
            SELECT
                ca.description AS action,
                ca.effectiveness_rating,
                rc.name AS root_cause,
                COUNT(dr.id) AS usage_count
            FROM corrective_actions ca
            JOIN root_causes rc ON rc.id = ca.root_cause_id
            LEFT JOIN defect_records dr ON dr.corrective_action_id = ca.id
            LEFT JOIN defect_codes dc  ON dc.id = dr.defect_code_id
            WHERE ca.factory_id = :fid
              AND ca.deleted_at IS NULL
              AND (dc.code = :code OR :code IS NULL)
            GROUP BY ca.id, ca.description, ca.effectiveness_rating, rc.name
            ORDER BY ca.effectiveness_rating DESC NULLS LAST, usage_count DESC
            LIMIT 5
        """
        rows = db.session.execute(text(sql), {"fid": factory_id, "code": defect_code}).fetchall()
        if not rows:
            return [{"action": "Inspect machine calibration", "root_cause": "Unknown", "confidence": 0.5}]
        return [
            {
                "action":               r.action,
                "root_cause":           r.root_cause,
                "effectiveness_rating": r.effectiveness_rating,
                "usage_count":          int(r.usage_count),
                "confidence":           round((r.effectiveness_rating or 3) / 5.0, 2),
            }
            for r in rows
        ]

    # ── Forecast ─────────────────────────────────────────────────
    @staticmethod
    def get_quality_forecast(factory_id: int, days_ahead: int = 7) -> list:
        sql = """
            SELECT defect_date,
                   SUM(quantity_defective) AS defective,
                   SUM(quantity_produced)  AS produced
            FROM defect_records
            WHERE factory_id = :fid AND deleted_at IS NULL
              AND defect_date >= CURRENT_DATE - INTERVAL '60 days'
            GROUP BY defect_date ORDER BY defect_date
        """
        rows = db.session.execute(text(sql), {"fid": factory_id}).fetchall()
        if len(rows) < 7:
            return []

        df = pd.DataFrame([dict(r._mapping) for r in rows])
        df["defect_rate"] = df.apply(
            lambda r: r["defective"] / r["produced"] if r["produced"] else 0, axis=1)
        df["defect_date"] = pd.to_datetime(df["defect_date"])
        df = df.set_index("defect_date").sort_index()
        df["ma7"] = df["defect_rate"].rolling(7).mean()

        last_ma = float(df["ma7"].dropna().iloc[-1]) if not df["ma7"].dropna().empty else 0.02
        last_date = df.index.max()

        forecast = []
        for i in range(1, days_ahead + 1):
            forecast_date = last_date + timedelta(days=i)
            noise = float(np.random.normal(0, last_ma * 0.05))
            predicted = max(0.0, last_ma + noise)
            forecast.append({
                "date":                   forecast_date.strftime("%Y-%m-%d"),
                "predicted_defect_rate":  round(predicted, 4),
                "predicted_ppm":          round(predicted * 1_000_000, 0),
                "confidence_interval": {
                    "lower": round(max(0.0, predicted - last_ma * 0.1), 4),
                    "upper": round(predicted + last_ma * 0.1, 4),
                },
            })
        return forecast

    # ── Helpers ──────────────────────────────────────────────────
    @staticmethod
    def _recommendation(prob: float) -> str:
        if prob > 0.75: return "🔴 STOP production. Inspect machine & material immediately."
        if prob > 0.55: return "🟠 HIGH RISK — Increase sampling. Alert supervisor."
        if prob > 0.30: return "🟡 MEDIUM — Monitor closely. Review calibration logs."
        return "🟢 LOW — Acceptable. Continue standard monitoring."

    # ── Legacy Sklearn Implementations ───────────────────────────
    @staticmethod
    def _legacy_train(df: pd.DataFrame, factory_id: int) -> dict:
        if not SKLEARN:
            return {"status": "error", "error": "scikit-learn not installed"}

        from sklearn.preprocessing import LabelEncoder
        from sklearn.model_selection import train_test_split
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score, classification_report

        feature_cols = ["shift", "machine_code", "operator_name", "temperature", "humidity"]
        available    = [c for c in feature_cols if c in df.columns]
        df = df[available + ["has_defect"]].dropna(subset=["has_defect"])
        df[available] = df[available].fillna("unknown")

        encoders = {}
        for col in ["shift", "machine_code", "operator_name"]:
            if col in df.columns:
                le = LabelEncoder()
                df[col] = le.fit_transform(df[col].astype(str))
                encoders[col] = le

        X, y = df[available], df["has_defect"].astype(int)
        if len(y.unique()) < 2:
            return {"status": "error", "error": "Single class in data"}

        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
        model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, class_weight="balanced")
        model.fit(X_tr, y_tr)
        y_pred = model.predict(X_te)
        acc = float(accuracy_score(y_te, y_pred))

        model_path = os.path.join(MODEL_DIR, f"defect_model_{factory_id}.pkl")
        enc_path   = os.path.join(MODEL_DIR, f"encoders_{factory_id}.pkl")
        joblib.dump(model, model_path)
        joblib.dump({"encoders": encoders, "features": available}, enc_path)

        return {
            "status": "success", "model_path": model_path,
            "metrics": {"accuracy": round(acc, 4)},
            "samples_trained": len(X_tr), "samples_tested": len(X_te),
        }

    @staticmethod
    def _legacy_predict(factory_id: int, input_data: dict) -> dict:
        if not SKLEARN:
            import random; prob = random.uniform(0.1, 0.5)
            return {"defect_probability": prob, "risk_level": "medium", "source": "mock"}

        model_path = os.path.join(MODEL_DIR, f"defect_model_{factory_id}.pkl")
        enc_path   = os.path.join(MODEL_DIR, f"encoders_{factory_id}.pkl")

        if not os.path.exists(model_path):
            return {"status": "no_model", "error": "Model not trained yet"}

        model = joblib.load(model_path)
        meta  = joblib.load(enc_path)
        encoders, features = meta["encoders"], meta["features"]

        row = {}
        for feat in features:
            val = input_data.get(feat, "unknown")
            if feat in encoders:
                le = encoders[feat]
                row[feat] = le.transform([str(val)])[0] if str(val) in le.classes_ else -1
            else:
                row[feat] = float(val) if val != "unknown" else 0.0

        prob = float(model.predict_proba(pd.DataFrame([row]))[0][1])
        return {
            "defect_probability": round(prob, 4),
            "defect_predicted": prob > 0.5,
            "risk_level": "critical" if prob > 0.7 else "high" if prob > 0.5 else "medium" if prob > 0.3 else "low",
            "recommendation": AIService._recommendation(prob),
            "source": "model",
        }

    @staticmethod
    def _legacy_anomaly(df: pd.DataFrame, factory_id: int) -> list:
        from sklearn.ensemble import IsolationForest
        numeric = ["quantity_defective", "quantity_produced", "defect_rate", "temperature", "humidity"]
        avail   = [c for c in numeric if c in df.columns]
        X       = df[avail].fillna(0)
        iso     = IsolationForest(contamination=0.1, random_state=42)
        df["anomaly_score"] = iso.fit_predict(X)
        df["score_raw"]     = iso.score_samples(X)
        anomalies           = df[df["anomaly_score"] == -1]
        alerts = []
        for _, row in anomalies.iterrows():
            score    = float(row["score_raw"])
            severity = "critical" if score < -0.6 else "high"
            alerts.append({
                "defect_record_id":   int(row["id"]) if "id" in row else None,
                "date":               str(row.get("defect_date", "")),
                "machine":            str(row.get("machine_code", "Unknown")),
                "shift":              str(row.get("shift", "Unknown")),
                "defect_rate":        round(float(row.get("defect_rate", 0)), 4),
                "quantity_defective": int(row.get("quantity_defective", 0)),
                "severity":           severity,
                "anomaly_score":      round(score, 4),
                "description":        f"Anomaly on machine {row.get('machine_code', 'N/A')}",
            })
        return alerts
