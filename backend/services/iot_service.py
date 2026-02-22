"""
IoT Service — Sensor data ingestion, retrieval, and aggregation
Predictive Maintenance — MTBF, MTTR, failure probability
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import text
from models import db

logger = logging.getLogger(__name__)


class IoTService:

    @staticmethod
    def ingest_sensor_data(factory_id: int, device_id: int, readings: list) -> dict:
        """
        Bulk ingest sensor readings.
        readings = [{"metric_name": str, "metric_value": float, "unit": str}]
        """
        inserted = 0
        for r in readings:
            db.session.execute(text("""
                INSERT INTO sensor_data (device_id, metric_name, metric_value, unit, factory_id, recorded_at)
                VALUES (:did, :name, :val, :unit, :fid, NOW())
            """), {
                "did": device_id, "name": r["metric_name"],
                "val": r["metric_value"], "unit": r.get("unit", ""),
                "fid": factory_id
            })
            inserted += 1
        db.session.commit()
        return {"inserted": inserted}

    @staticmethod
    def get_sensor_summary(factory_id: int, hours: int = 1) -> list:
        """Latest sensor reading per device/metric."""
        sql = """
            SELECT
                d.id AS device_id, d.name AS device_name, d.device_type,
                m.code AS machine_code, m.name AS machine_name,
                sd.metric_name, sd.metric_value, sd.unit, sd.recorded_at, sd.quality_flag
            FROM iot_devices d
            JOIN machines m ON m.id = d.machine_id
            JOIN LATERAL (
                SELECT metric_name, metric_value, unit, recorded_at, quality_flag
                FROM sensor_data
                WHERE device_id = d.id AND factory_id = :fid
                  AND recorded_at >= NOW() - (:hours * INTERVAL '1 hour')
                ORDER BY recorded_at DESC
                LIMIT 1
            ) sd ON TRUE
            WHERE d.factory_id = :fid AND d.deleted_at IS NULL AND d.is_active = TRUE
            ORDER BY d.machine_id, d.device_type
        """
        rows = db.session.execute(text(sql), {"fid": factory_id, "hours": hours}).fetchall()
        return [dict(r._mapping) for r in rows]

    @staticmethod
    def get_sensor_timeseries(factory_id: int, device_id: int,
                              metric: str, hours: int = 24) -> list:
        sql = """
            SELECT metric_value, unit, recorded_at, quality_flag
            FROM sensor_data
            WHERE factory_id = :fid AND device_id = :did AND metric_name = :metric
              AND recorded_at >= NOW() - (:hours * INTERVAL '1 hour')
            ORDER BY recorded_at ASC
            LIMIT 1000
        """
        rows = db.session.execute(text(sql), {
            "fid": factory_id, "did": device_id,
            "metric": metric, "hours": hours
        }).fetchall()
        return [dict(r._mapping) for r in rows]

    @staticmethod
    def get_devices(factory_id: int, machine_id: Optional[int] = None) -> list:
        filters = ["d.factory_id = :fid", "d.deleted_at IS NULL"]
        params = {"fid": factory_id}
        if machine_id:
            filters.append("d.machine_id = :mid")
            params["mid"] = machine_id
        where = " AND ".join(filters)
        sql = f"""
            SELECT d.id, d.name, d.device_type, d.serial_number, d.location, d.is_active,
                   m.code AS machine_code, m.name AS machine_name
            FROM iot_devices d
            LEFT JOIN machines m ON m.id = d.machine_id
            WHERE {where}
            ORDER BY d.machine_id, d.name
        """
        rows = db.session.execute(text(sql), params).fetchall()
        return [dict(r._mapping) for r in rows]

    @staticmethod
    def create_device(factory_id: int, data: dict) -> dict:
        row = db.session.execute(text("""
            INSERT INTO iot_devices (name, machine_id, device_type, serial_number, location, factory_id)
            VALUES (:name, :mid, :dtype, :sn, :loc, :fid)
            RETURNING id, name, device_type, created_at
        """), {
            "name": data["name"], "mid": data.get("machine_id"),
            "dtype": data.get("device_type", "custom"),
            "sn": data.get("serial_number"), "loc": data.get("location"),
            "fid": factory_id
        }).fetchone()
        db.session.commit()
        return dict(row._mapping)


class MaintenanceService:

    @staticmethod
    def calculate_mtbf(factory_id: int, machine_id: int) -> dict:
        """
        MTBF = Total Operating Time / Number of Failures
        """
        sql = """
            SELECT
                COUNT(*) FILTER (WHERE event_type = 'unplanned') AS failures,
                SUM(duration_hours) FILTER (WHERE event_type = 'unplanned') AS total_downtime,
                MIN(started_at) AS first_event,
                MAX(COALESCE(ended_at, NOW())) AS last_event
            FROM maintenance_events
            WHERE factory_id = :fid AND machine_id = :mid
        """
        row = db.session.execute(text(sql), {"fid": factory_id, "mid": machine_id}).fetchone()

        failures = int(row.failures or 0)
        if failures == 0:
            return {"mtbf_hours": None, "message": "No failure events recorded", "failures": 0}

        if row.first_event and row.last_event:
            total_hours = (row.last_event - row.first_event).total_seconds() / 3600
        else:
            total_hours = 720

        downtime = float(row.total_downtime or 0)
        operating = max(0, total_hours - downtime)
        mtbf = operating / failures if failures else 0

        return {
            "mtbf_hours": round(mtbf, 2),
            "mttr_hours": round(downtime / failures, 2) if failures else 0,
            "failures": failures,
            "total_operating_hours": round(operating, 2),
            "total_downtime_hours": round(downtime, 2),
            "availability_pct": round(operating / total_hours * 100, 2) if total_hours else 0,
        }

    @staticmethod
    def predict_failure(factory_id: int, machine_id: int) -> dict:
        """
        Simple failure prediction based on MTBF + last maintenance.
        """
        mtbf_data = MaintenanceService.calculate_mtbf(factory_id, machine_id)

        last_event = db.session.execute(text("""
            SELECT MAX(ended_at) AS last_maintenance
            FROM maintenance_events
            WHERE factory_id = :fid AND machine_id = :mid
        """), {"fid": factory_id, "mid": machine_id}).fetchone()

        last_maintenance = last_event.last_maintenance if last_event else None
        mtbf = mtbf_data.get("mtbf_hours")

        if not mtbf or not last_maintenance:
            # Return estimated prediction
            predicted_date = datetime.now() + timedelta(days=30)
            confidence = 0.35
        else:
            hours_since = (datetime.now() - last_maintenance).total_seconds() / 3600
            remaining = max(0, mtbf - hours_since)
            predicted_date = datetime.now() + timedelta(hours=remaining)
            # Confidence decreases as we approach predicted failure
            confidence = max(0.1, min(0.95, 1 - (hours_since / mtbf)))

        risk_level = "critical" if confidence < 0.3 else "high" if confidence < 0.5 else "medium" if confidence < 0.7 else "low"

        return {
            "machine_id": machine_id,
            "predicted_failure_date": predicted_date.strftime("%Y-%m-%d"),
            "confidence_score": round(confidence, 4),
            "risk_level": risk_level,
            "mtbf_hours": mtbf,
            "recommended_action": MaintenanceService._maintenance_recommendation(risk_level),
        }

    @staticmethod
    def _maintenance_recommendation(risk_level: str) -> str:
        return {
            "critical": "Schedule immediate inspection. Do not wait for scheduled maintenance.",
            "high": "Plan maintenance within 48 hours. Increase monitoring frequency.",
            "medium": "Schedule maintenance within next planned window. Monitor closely.",
            "low": "Continue normal monitoring. Next scheduled maintenance sufficient."
        }.get(risk_level, "Continue monitoring.")

    @staticmethod
    def get_maintenance_schedule(factory_id: int) -> list:
        sql = """
            SELECT
                mp.id, mp.predicted_failure_date, mp.confidence_score, mp.risk_level,
                mp.recommended_action, mp.failure_type, mp.is_acknowledged, mp.generated_at,
                m.code AS machine_code, m.name AS machine_name
            FROM maintenance_predictions mp
            JOIN machines m ON m.id = mp.machine_id
            WHERE mp.factory_id = :fid
            ORDER BY mp.risk_level DESC, mp.predicted_failure_date ASC
            LIMIT 20
        """
        rows = db.session.execute(text(sql), {"fid": factory_id}).fetchall()
        return [dict(r._mapping) for r in rows]

    @staticmethod
    def get_risk_scores(factory_id: int) -> list:
        sql = """
            SELECT
                rs.id, rs.risk_level, rs.probability_score, rs.predicted_defect_type,
                rs.recommendation, rs.generated_at,
                m.code AS machine_code, m.name AS machine_name
            FROM risk_scores rs
            JOIN machines m ON m.id = rs.machine_id
            WHERE rs.factory_id = :fid AND rs.is_active = TRUE
              AND (rs.expires_at IS NULL OR rs.expires_at > NOW())
            ORDER BY rs.probability_score DESC
        """
        rows = db.session.execute(text(sql), {"fid": factory_id}).fetchall()
        return [dict(r._mapping) for r in rows]

    @staticmethod
    def generate_risk_scores(factory_id: int) -> list:
        """Generate risk scores for all machines based on recent defect patterns."""
        machines = db.session.execute(text("""
            SELECT id, code, name FROM machines
            WHERE factory_id = :fid AND deleted_at IS NULL
        """), {"fid": factory_id}).fetchall()

        scores = []
        for m in machines:
            defect_rate = db.session.execute(text("""
                SELECT
                    COALESCE(SUM(quantity_defective)::FLOAT / NULLIF(SUM(quantity_produced),0), 0) AS dr,
                    COUNT(*) AS events
                FROM defect_records
                WHERE machine_id = :mid AND factory_id = :fid
                  AND defect_date >= CURRENT_DATE - INTERVAL '7 days'
                  AND deleted_at IS NULL
            """), {"mid": m.id, "fid": factory_id}).fetchone()

            dr = float(defect_rate.dr or 0)
            events = int(defect_rate.events or 0)
            prob = min(0.99, dr * 5 + events * 0.02)
            level = "critical" if prob > 0.7 else "high" if prob > 0.4 else "medium" if prob > 0.2 else "low"

            # Upsert risk score
            db.session.execute(text("""
                INSERT INTO risk_scores
                    (machine_id, risk_level, probability_score, predicted_defect_type,
                     recommendation, generated_at, expires_at, factory_id)
                VALUES (:mid, :level, :prob, :deftype, :rec, NOW(), NOW() + INTERVAL '24 hours', :fid)
                ON CONFLICT DO NOTHING
            """), {
                "mid": m.id, "level": level, "prob": round(prob, 4),
                "deftype": "Surface/Dimensional" if prob > 0.3 else "Normal variation",
                "rec": MaintenanceService._maintenance_recommendation(level),
                "fid": factory_id
            })
            scores.append({
                "machine_code": m.code, "machine_name": m.name,
                "risk_level": level, "probability_score": round(prob, 4)
            })

        db.session.commit()
        return scores
