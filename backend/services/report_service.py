"""
Report Generation Service
Daily/Monthly reports, Excel and PDF export
"""
import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional
from sqlalchemy import text
from models import db
from services.quality_metrics_service import QualityMetricsService

logger = logging.getLogger(__name__)


class ReportService:

    @staticmethod
    def get_daily_report(factory_id: int, report_date: Optional[date] = None) -> dict:
        if not report_date:
            report_date = date.today()

        # Production summary
        prod_sql = """
            SELECT
                COUNT(DISTINCT pr.id) AS total_runs,
                SUM(pr.planned_quantity) AS planned,
                SUM(pr.actual_quantity) AS actual,
                SUM(pr.downtime_minutes) AS total_downtime,
                COUNT(DISTINCT pr.machine_id) AS machines_active
            FROM production_records pr
            WHERE pr.factory_id = :factory_id
              AND pr.production_date = :report_date
              AND pr.deleted_at IS NULL
        """
        prod = db.session.execute(text(prod_sql), {
            "factory_id": factory_id, "report_date": report_date
        }).fetchone()

        # Defect summary
        defect_sql = """
            SELECT
                SUM(dr.quantity_defective) AS total_defective,
                SUM(dr.quantity_produced) AS total_produced,
                COUNT(DISTINCT dr.id) AS defect_records,
                COUNT(DISTINCT dr.machine_id) AS machines_with_defects
            FROM defect_records dr
            WHERE dr.factory_id = :factory_id
              AND dr.defect_date = :report_date
              AND dr.deleted_at IS NULL
        """
        defects = db.session.execute(text(defect_sql), {
            "factory_id": factory_id, "report_date": report_date
        }).fetchone()

        # Top 5 defects
        top5 = QualityMetricsService.calculate_defect_distribution(
            factory_id, report_date, report_date, limit=5
        )

        # Machine performance
        machine_sql = """
            SELECT
                m.code, m.name,
                SUM(pr.actual_quantity) AS produced,
                SUM(pr.downtime_minutes) AS downtime,
                COALESCE(SUM(dr_sum.defective), 0) AS defective
            FROM production_records pr
            JOIN machines m ON m.id = pr.machine_id
            LEFT JOIN (
                SELECT machine_id, SUM(quantity_defective) AS defective
                FROM defect_records
                WHERE defect_date = :report_date AND factory_id = :factory_id AND deleted_at IS NULL
                GROUP BY machine_id
            ) dr_sum ON dr_sum.machine_id = pr.machine_id
            WHERE pr.factory_id = :factory_id
              AND pr.production_date = :report_date
              AND pr.deleted_at IS NULL
            GROUP BY m.code, m.name
            ORDER BY produced DESC
        """
        machines = db.session.execute(text(machine_sql), {
            "factory_id": factory_id, "report_date": report_date
        }).fetchall()

        total_defective = int(defects.total_defective or 0)
        total_produced = int(defects.total_produced or 0)
        ppm = round(total_defective / total_produced * 1_000_000, 2) if total_produced else 0
        defect_rate = round(total_defective / total_produced * 100, 4) if total_produced else 0

        return {
            "report_date": str(report_date),
            "report_type": "daily",
            "production_summary": {
                "total_runs": int(prod.total_runs or 0),
                "planned_quantity": int(prod.planned or 0),
                "actual_quantity": int(prod.actual or 0),
                "total_downtime_minutes": int(prod.total_downtime or 0),
                "machines_active": int(prod.machines_active or 0),
            },
            "quality_summary": {
                "total_defective": total_defective,
                "total_produced": total_produced,
                "defect_records": int(defects.defect_records or 0),
                "ppm": ppm,
                "defect_rate_pct": defect_rate,
            },
            "top_defects": top5,
            "machine_performance": [dict(r._mapping) for r in machines],
        }

    @staticmethod
    def get_monthly_report(factory_id: int, year: int, month: int) -> dict:
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        metrics = QualityMetricsService.calculate_ppm(factory_id, start_date, end_date)
        oee = QualityMetricsService.calculate_oee(factory_id, start_date, end_date)
        fpy = QualityMetricsService.calculate_first_pass_yield(factory_id, start_date, end_date)
        trend = QualityMetricsService.calculate_trend(factory_id, period="daily", days=30)
        pareto = QualityMetricsService.calculate_defect_distribution(factory_id, start_date, end_date, limit=10)

        # Shift comparison
        shift_sql = """
            SELECT
                dr.shift,
                SUM(dr.quantity_defective) AS defective,
                SUM(dr.quantity_produced) AS produced,
                CASE WHEN SUM(dr.quantity_produced) > 0
                     THEN ROUND(SUM(dr.quantity_defective)::NUMERIC / SUM(dr.quantity_produced) * 1000000, 2)
                     ELSE 0 END AS ppm
            FROM defect_records dr
            WHERE dr.factory_id = :factory_id
              AND dr.defect_date BETWEEN :start_date AND :end_date
              AND dr.deleted_at IS NULL
            GROUP BY dr.shift
            ORDER BY ppm DESC
        """
        shifts = db.session.execute(text(shift_sql), {
            "factory_id": factory_id, "start_date": start_date, "end_date": end_date
        }).fetchall()

        return {
            "period": f"{year}-{month:02d}",
            "report_type": "monthly",
            "date_range": {"start": str(start_date), "end": str(end_date)},
            "overall_metrics": {
                **metrics,
                "oee_pct": oee["oee_pct"],
                "fpy_pct": fpy["first_pass_yield_pct"],
            },
            "oee_breakdown": oee,
            "trend": trend,
            "pareto": pareto,
            "shift_comparison": [dict(r._mapping) for r in shifts],
        }

    @staticmethod
    def get_supplier_quality(factory_id: int, start_date=None, end_date=None) -> list:
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
                pr.material_batch,
                COUNT(DISTINCT dr.id) AS incident_count,
                SUM(dr.quantity_defective) AS total_defective,
                SUM(dr.quantity_produced) AS total_produced,
                CASE WHEN SUM(dr.quantity_produced) > 0
                     THEN ROUND(SUM(dr.quantity_defective)::NUMERIC / SUM(dr.quantity_produced) * 100, 4)
                     ELSE 0 END AS defect_rate_pct,
                CASE WHEN SUM(dr.quantity_produced) > 0
                     THEN ROUND(100 - SUM(dr.quantity_defective)::NUMERIC / SUM(dr.quantity_produced) * 100, 4)
                     ELSE 100 END AS quality_rating
            FROM defect_records dr
            LEFT JOIN production_records pr ON pr.id = dr.production_record_id
            WHERE {where} AND pr.material_batch IS NOT NULL
            GROUP BY pr.material_batch
            ORDER BY defect_rate_pct DESC
        """
        rows = db.session.execute(text(sql), params).fetchall()
        return [dict(r._mapping) for r in rows]

    @staticmethod
    def generate_excel_report(factory_id: int, report_type: str,
                               start_date=None, end_date=None) -> bytes:
        """Generate Excel report (requires openpyxl)."""
        try:
            import openpyxl
            from io import BytesIO

            wb = openpyxl.Workbook()

            if report_type == "daily":
                today = date.today()
                data = ReportService.get_daily_report(factory_id, today)
                ws = wb.active
                ws.title = "Daily Report"
                ws.append(["Daily Production & Quality Report", str(today)])
                ws.append([])
                ws.append(["Production Summary"])
                for k, v in data["production_summary"].items():
                    ws.append([k, v])
                ws.append([])
                ws.append(["Quality Summary"])
                for k, v in data["quality_summary"].items():
                    ws.append([k, v])
                ws.append([])
                ws.append(["Top Defects"])
                ws.append(["Code", "Description", "Total Defective", "Pct"])
                for d in data["top_defects"]:
                    ws.append([d["code"], d["description"], d["total_defective"], d["percentage"]])

            elif report_type == "monthly":
                now = date.today()
                data = ReportService.get_monthly_report(factory_id, now.year, now.month)
                ws = wb.active
                ws.title = "Monthly Report"
                ws.append([f"Monthly Quality Report - {data['period']}"])
                ws.append([])
                ws.append(["Metric", "Value"])
                for k, v in data["overall_metrics"].items():
                    ws.append([k, v])

            buf = BytesIO()
            wb.save(buf)
            buf.seek(0)
            return buf.read()

        except ImportError:
            raise RuntimeError("openpyxl not installed. Install it with: pip install openpyxl")
