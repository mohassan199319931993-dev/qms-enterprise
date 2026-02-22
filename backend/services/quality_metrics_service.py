"""
Quality Metrics Service
Computes PPM, Defect Rate, First Pass Yield, OEE, Trends, and Distribution
"""
from datetime import datetime, timedelta
from typing import Optional
from models import db
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


class QualityMetricsService:

    @staticmethod
    def calculate_ppm(factory_id: int, start_date=None, end_date=None,
                      machine_id: Optional[int] = None) -> dict:
        """
        PPM = (Total Defective / Total Produced) * 1,000,000
        """
        filters = ["dr.factory_id = :factory_id", "dr.deleted_at IS NULL"]
        params = {"factory_id": factory_id}

        if start_date:
            filters.append("dr.defect_date >= :start_date")
            params["start_date"] = start_date
        if end_date:
            filters.append("dr.defect_date <= :end_date")
            params["end_date"] = end_date
        if machine_id:
            filters.append("dr.machine_id = :machine_id")
            params["machine_id"] = machine_id

        where = " AND ".join(filters)
        sql = f"""
            SELECT
                SUM(dr.quantity_defective) AS total_defective,
                SUM(dr.quantity_produced) AS total_produced,
                CASE
                    WHEN SUM(dr.quantity_produced) > 0
                    THEN ROUND(SUM(dr.quantity_defective)::NUMERIC / SUM(dr.quantity_produced) * 1000000, 2)
                    ELSE 0
                END AS ppm
            FROM defect_records dr
            WHERE {where}
        """
        result = db.session.execute(text(sql), params).fetchone()
        return {
            "ppm": float(result.ppm or 0),
            "total_defective": int(result.total_defective or 0),
            "total_produced": int(result.total_produced or 0),
        }

    @staticmethod
    def calculate_defect_rate(factory_id: int, start_date=None, end_date=None,
                              machine_id: Optional[int] = None) -> dict:
        """
        Defect Rate % = (Total Defective / Total Produced) * 100
        """
        ppm_data = QualityMetricsService.calculate_ppm(
            factory_id, start_date, end_date, machine_id)
        total_produced = ppm_data["total_produced"]
        total_defective = ppm_data["total_defective"]
        defect_rate = round((total_defective / total_produced * 100), 4) if total_produced else 0
        return {
            "defect_rate_pct": defect_rate,
            "total_defective": total_defective,
            "total_produced": total_produced,
        }

    @staticmethod
    def calculate_first_pass_yield(factory_id: int, start_date=None, end_date=None) -> dict:
        """
        FPY = (Total Produced - Total Defective) / Total Produced * 100
        """
        filters = ["pr.factory_id = :factory_id", "pr.deleted_at IS NULL"]
        params = {"factory_id": factory_id}
        if start_date:
            filters.append("pr.production_date >= :start_date")
            params["start_date"] = start_date
        if end_date:
            filters.append("pr.production_date <= :end_date")
            params["end_date"] = end_date

        where = " AND ".join(filters)
        sql = f"""
            SELECT
                SUM(pr.actual_quantity) AS total_produced,
                COALESCE(SUM(dr.defective_sum), 0) AS total_defective
            FROM production_records pr
            LEFT JOIN (
                SELECT production_record_id, SUM(quantity_defective) AS defective_sum
                FROM defect_records
                WHERE deleted_at IS NULL
                GROUP BY production_record_id
            ) dr ON dr.production_record_id = pr.id
            WHERE {where}
        """
        result = db.session.execute(text(sql), params).fetchone()
        total_produced = int(result.total_produced or 0)
        total_defective = int(result.total_defective or 0)
        good = total_produced - total_defective
        fpy = round((good / total_produced * 100), 4) if total_produced else 0
        return {
            "first_pass_yield_pct": fpy,
            "good_units": good,
            "total_produced": total_produced,
            "total_defective": total_defective,
        }

    @staticmethod
    def calculate_oee(factory_id: int, start_date=None, end_date=None,
                      machine_id: Optional[int] = None) -> dict:
        """
        OEE = Availability × Performance × Quality
        Availability = (Actual Time - Downtime) / Actual Time
        Performance = Actual Quantity / Planned Quantity
        Quality = Good Units / Actual Quantity
        """
        filters = ["pr.factory_id = :factory_id", "pr.deleted_at IS NULL"]
        params = {"factory_id": factory_id}
        if start_date:
            filters.append("pr.production_date >= :start_date")
            params["start_date"] = start_date
        if end_date:
            filters.append("pr.production_date <= :end_date")
            params["end_date"] = end_date
        if machine_id:
            filters.append("pr.machine_id = :machine_id")
            params["machine_id"] = machine_id

        where = " AND ".join(filters)
        sql = f"""
            SELECT
                SUM(pr.actual_time_minutes) AS total_time,
                SUM(pr.downtime_minutes) AS total_downtime,
                SUM(pr.planned_quantity) AS total_planned,
                SUM(pr.actual_quantity) AS total_actual,
                COALESCE(SUM(dr.defective_sum), 0) AS total_defective
            FROM production_records pr
            LEFT JOIN (
                SELECT production_record_id, SUM(quantity_defective) AS defective_sum
                FROM defect_records WHERE deleted_at IS NULL
                GROUP BY production_record_id
            ) dr ON dr.production_record_id = pr.id
            WHERE {where}
        """
        row = db.session.execute(text(sql), params).fetchone()

        total_time = float(row.total_time or 0)
        total_downtime = float(row.total_downtime or 0)
        total_planned = float(row.total_planned or 0)
        total_actual = float(row.total_actual or 0)
        total_defective = float(row.total_defective or 0)

        availability = round((total_time - total_downtime) / total_time, 4) if total_time else 0
        performance = round(total_actual / total_planned, 4) if total_planned else 0
        good_units = total_actual - total_defective
        quality = round(good_units / total_actual, 4) if total_actual else 0
        oee = round(availability * performance * quality, 4)

        return {
            "oee": oee,
            "oee_pct": round(oee * 100, 2),
            "availability": availability,
            "availability_pct": round(availability * 100, 2),
            "performance": performance,
            "performance_pct": round(performance * 100, 2),
            "quality": quality,
            "quality_pct": round(quality * 100, 2),
        }

    @staticmethod
    def calculate_trend(factory_id: int, metric: str = "ppm",
                        period: str = "daily", days: int = 30) -> list:
        """
        Returns time-series data for a given metric.
        period: daily | weekly | monthly
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        if period == "daily":
            trunc = "day"
        elif period == "weekly":
            trunc = "week"
        else:
            trunc = "month"

        sql = """
            SELECT
                DATE_TRUNC(:trunc, dr.defect_date::TIMESTAMP)::DATE AS period_start,
                SUM(dr.quantity_defective) AS total_defective,
                SUM(dr.quantity_produced) AS total_produced,
                CASE
                    WHEN SUM(dr.quantity_produced) > 0
                    THEN ROUND(SUM(dr.quantity_defective)::NUMERIC / SUM(dr.quantity_produced) * 1000000, 2)
                    ELSE 0
                END AS ppm,
                CASE
                    WHEN SUM(dr.quantity_produced) > 0
                    THEN ROUND(SUM(dr.quantity_defective)::NUMERIC / SUM(dr.quantity_produced) * 100, 4)
                    ELSE 0
                END AS defect_rate
            FROM defect_records dr
            WHERE dr.factory_id = :factory_id
              AND dr.deleted_at IS NULL
              AND dr.defect_date BETWEEN :start_date AND :end_date
            GROUP BY 1
            ORDER BY 1
        """
        rows = db.session.execute(text(sql), {
            "factory_id": factory_id,
            "trunc": trunc,
            "start_date": start_date,
            "end_date": end_date,
        }).fetchall()

        return [
            {
                "period": str(r.period_start),
                "ppm": float(r.ppm or 0),
                "defect_rate": float(r.defect_rate or 0),
                "total_defective": int(r.total_defective or 0),
                "total_produced": int(r.total_produced or 0),
            }
            for r in rows
        ]

    @staticmethod
    def calculate_defect_distribution(factory_id: int, start_date=None,
                                      end_date=None, limit: int = 10) -> list:
        """
        Pareto distribution of defects by code/category.
        """
        filters = ["dr.factory_id = :factory_id", "dr.deleted_at IS NULL"]
        params = {"factory_id": factory_id, "limit": limit}
        if start_date:
            filters.append("dr.defect_date >= :start_date")
            params["start_date"] = start_date
        if end_date:
            filters.append("dr.defect_date <= :end_date")
            params["end_date"] = end_date

        where = " AND ".join(filters)
        sql = f"""
            SELECT
                dc.code,
                dc.description,
                cat.name AS category,
                cat.severity_level,
                SUM(dr.quantity_defective) AS total_defective,
                COUNT(dr.id) AS occurrence_count
            FROM defect_records dr
            JOIN defect_codes dc ON dc.id = dr.defect_code_id
            LEFT JOIN defect_categories cat ON cat.id = dc.category_id
            WHERE {where}
            GROUP BY dc.code, dc.description, cat.name, cat.severity_level
            ORDER BY total_defective DESC
            LIMIT :limit
        """
        rows = db.session.execute(text(sql), params).fetchall()
        total = sum(int(r.total_defective or 0) for r in rows)
        result = []
        cumulative = 0
        for r in rows:
            count = int(r.total_defective or 0)
            cumulative += count
            result.append({
                "code": r.code,
                "description": r.description,
                "category": r.category,
                "severity_level": r.severity_level,
                "total_defective": count,
                "occurrence_count": int(r.occurrence_count),
                "percentage": round(count / total * 100, 2) if total else 0,
                "cumulative_pct": round(cumulative / total * 100, 2) if total else 0,
            })
        return result

    @staticmethod
    def get_machine_heatmap(factory_id: int, start_date=None, end_date=None) -> list:
        """Returns defect counts by machine and shift for heatmap visualization."""
        filters = ["dr.factory_id = :factory_id", "dr.deleted_at IS NULL"]
        params = {"factory_id": factory_id}
        if start_date:
            filters.append("dr.defect_date >= :start_date")
            params["start_date"] = start_date
        if end_date:
            filters.append("dr.defect_date <= :end_date")
            params["end_date"] = end_date

        where = " AND ".join(filters)
        sql = f"""
            SELECT
                m.code AS machine_code,
                m.name AS machine_name,
                dr.shift,
                SUM(dr.quantity_defective) AS total_defective,
                CASE
                    WHEN SUM(dr.quantity_produced) > 0
                    THEN ROUND(SUM(dr.quantity_defective)::NUMERIC / SUM(dr.quantity_produced) * 1000000, 2)
                    ELSE 0
                END AS ppm
            FROM defect_records dr
            JOIN machines m ON m.id = dr.machine_id
            WHERE {where}
            GROUP BY m.code, m.name, dr.shift
            ORDER BY total_defective DESC
        """
        rows = db.session.execute(text(sql), params).fetchall()
        return [
            {
                "machine_code": r.machine_code,
                "machine_name": r.machine_name,
                "shift": r.shift,
                "total_defective": int(r.total_defective or 0),
                "ppm": float(r.ppm or 0),
            }
            for r in rows
        ]

    @staticmethod
    def get_comprehensive_metrics(factory_id: int, start_date=None, end_date=None) -> dict:
        """Returns all quality metrics in a single call."""
        return {
            "ppm": QualityMetricsService.calculate_ppm(factory_id, start_date, end_date),
            "defect_rate": QualityMetricsService.calculate_defect_rate(factory_id, start_date, end_date),
            "first_pass_yield": QualityMetricsService.calculate_first_pass_yield(factory_id, start_date, end_date),
            "oee": QualityMetricsService.calculate_oee(factory_id, start_date, end_date),
            "trend": QualityMetricsService.calculate_trend(factory_id, days=30),
            "pareto": QualityMetricsService.calculate_defect_distribution(factory_id, start_date, end_date),
            "heatmap": QualityMetricsService.get_machine_heatmap(factory_id, start_date, end_date),
        }
