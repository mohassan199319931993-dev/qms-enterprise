"""
SPC — Statistical Process Control Engine
X-bar charts, R-charts, Cp/Cpk, Nelson rules, process stability
"""
import math
import logging
from typing import List, Optional, Dict
from sqlalchemy import text
from models import db

logger = logging.getLogger(__name__)

# Western Electric / Nelson rule constants
A2 = {2:1.880,3:1.023,4:0.729,5:0.577,6:0.483,7:0.419,8:0.373,9:0.337,10:0.308}
D3 = {2:0,3:0,4:0,5:0,6:0,7:0.076,8:0.136,9:0.184,10:0.223}
D4 = {2:3.267,3:2.574,4:2.282,5:2.114,6:2.004,7:1.924,8:1.864,9:1.816,10:1.777}
d2 = {2:1.128,3:1.693,4:2.059,5:2.326,6:2.534,7:2.704,8:2.847,9:2.970,10:3.078}


class SPCService:

    @staticmethod
    def calculate_cpk(factory_id: int, machine_id: int, metric: str,
                      usl: float, lsl: float, days: int = 30) -> dict:
        """
        Cp = (USL - LSL) / (6σ)
        Cpk = min((USL - μ)/(3σ), (μ - LSL)/(3σ))
        """
        sql = """
            SELECT metric_value FROM sensor_data
            WHERE factory_id = :fid
              AND device_id IN (SELECT id FROM iot_devices WHERE machine_id = :mid AND factory_id = :fid)
              AND metric_name = :metric
              AND recorded_at >= NOW() - INTERVAL ':days days'
              AND quality_flag = 'good'
            ORDER BY recorded_at DESC
            LIMIT 500
        """
        rows = db.session.execute(text(sql), {
            "fid": factory_id, "mid": machine_id,
            "metric": metric, "days": days
        }).fetchall()

        values = [float(r.metric_value) for r in rows]
        if len(values) < 10:
            # Return demo values if insufficient data
            return SPCService._demo_cpk(usl, lsl)

        n = len(values)
        mean = sum(values) / n
        variance = sum((x - mean)**2 for x in values) / (n - 1)
        sigma = math.sqrt(variance)

        if sigma == 0:
            return {"error": "Zero variance in data"}

        cp = (usl - lsl) / (6 * sigma)
        cpu = (usl - mean) / (3 * sigma)
        cpl = (mean - lsl) / (3 * sigma)
        cpk = min(cpu, cpl)

        return {
            "cp": round(cp, 4),
            "cpk": round(cpk, 4),
            "cpu": round(cpu, 4),
            "cpl": round(cpl, 4),
            "mean": round(mean, 4),
            "sigma": round(sigma, 4),
            "usl": usl,
            "lsl": lsl,
            "n": n,
            "process_capable": cpk >= 1.33,
            "interpretation": SPCService._interpret_cpk(cpk),
        }

    @staticmethod
    def _demo_cpk(usl, lsl):
        """Returns realistic demo Cp/Cpk when insufficient sensor data."""
        sigma = (usl - lsl) / 8
        mean = (usl + lsl) / 2
        cp = (usl - lsl) / (6 * sigma)
        cpk = 1.24
        return {
            "cp": round(cp, 4), "cpk": cpk, "cpu": 1.31, "cpl": 1.17,
            "mean": round(mean, 4), "sigma": round(sigma, 4),
            "usl": usl, "lsl": lsl, "n": 0,
            "process_capable": False,
            "interpretation": SPCService._interpret_cpk(cpk),
            "note": "Demo data — insufficient sensor readings"
        }

    @staticmethod
    def _interpret_cpk(cpk: float) -> str:
        if cpk >= 2.0:   return "World-class process (Six Sigma)"
        if cpk >= 1.67:  return "Excellent — meets Six Sigma targets"
        if cpk >= 1.33:  return "Capable — meets quality requirements"
        if cpk >= 1.0:   return "Marginally capable — improvement recommended"
        if cpk >= 0.67:  return "Incapable — process needs correction"
        return "Critically incapable — immediate action required"

    @staticmethod
    def generate_control_chart(factory_id: int, machine_id: int,
                               metric: str, sample_size: int = 5,
                               days: int = 14) -> dict:
        """
        Generates X-bar and R chart data with control limits.
        """
        sql = """
            SELECT metric_value, recorded_at
            FROM sensor_data
            WHERE factory_id = :fid
              AND device_id IN (SELECT id FROM iot_devices WHERE machine_id = :mid AND factory_id = :fid)
              AND metric_name = :metric
              AND recorded_at >= NOW() - INTERVAL ':days days'
              AND quality_flag = 'good'
            ORDER BY recorded_at ASC
            LIMIT 1000
        """
        rows = db.session.execute(text(sql), {
            "fid": factory_id, "mid": machine_id,
            "metric": metric, "days": days
        }).fetchall()

        values = [float(r.metric_value) for r in rows]

        if len(values) < sample_size * 3:
            return SPCService._demo_control_chart(sample_size)

        # Group into subgroups
        n = sample_size
        subgroups = []
        for i in range(0, len(values) - n + 1, n):
            group = values[i:i+n]
            subgroups.append({
                "mean": sum(group)/n,
                "range": max(group) - min(group),
                "values": group
            })

        if not subgroups:
            return SPCService._demo_control_chart(sample_size)

        xbar_bar = sum(s["mean"] for s in subgroups) / len(subgroups)
        r_bar = sum(s["range"] for s in subgroups) / len(subgroups)

        a2 = A2.get(n, 0.577)
        d3 = D3.get(n, 0)
        d4 = D4.get(n, 2.114)

        xbar_ucl = xbar_bar + a2 * r_bar
        xbar_lcl = xbar_bar - a2 * r_bar
        r_ucl = d4 * r_bar
        r_lcl = d3 * r_bar

        xbar_points = []
        r_points = []
        for i, s in enumerate(subgroups):
            out_xbar = s["mean"] > xbar_ucl or s["mean"] < xbar_lcl
            out_r = s["range"] > r_ucl or s["range"] < r_lcl
            xbar_points.append({
                "x": i, "y": round(s["mean"], 4),
                "out_of_control": out_xbar,
                "violation": "Beyond control limits" if out_xbar else None
            })
            r_points.append({
                "x": i, "y": round(s["range"], 4),
                "out_of_control": out_r
            })

        ooc_count = sum(1 for p in xbar_points if p["out_of_control"])

        return {
            "metric": metric,
            "sample_size": n,
            "subgroup_count": len(subgroups),
            "xbar_chart": {
                "ucl": round(xbar_ucl, 4),
                "lcl": round(xbar_lcl, 4),
                "center": round(xbar_bar, 4),
                "points": xbar_points
            },
            "r_chart": {
                "ucl": round(r_ucl, 4),
                "lcl": round(r_lcl, 4),
                "center": round(r_bar, 4),
                "points": r_points
            },
            "process_stable": ooc_count == 0,
            "out_of_control_points": ooc_count,
        }

    @staticmethod
    def _demo_control_chart(sample_size=5):
        import random
        random.seed(42)
        center = 50.0
        sigma = 1.5
        ucl = center + 3 * sigma
        lcl = center - 3 * sigma
        points = []
        for i in range(20):
            val = center + random.gauss(0, sigma * 0.8)
            if i in [5, 13]:
                val = ucl + random.uniform(0.2, 0.8)
            points.append({"x": i, "y": round(val, 3), "out_of_control": val > ucl or val < lcl, "violation": "Beyond limits" if val > ucl or val < lcl else None})
        return {
            "metric": "demo_metric", "sample_size": sample_size, "subgroup_count": 20,
            "xbar_chart": {"ucl": round(ucl,3), "lcl": round(lcl,3), "center": center, "points": points},
            "r_chart": {"ucl": round(3.6,3), "lcl": 0, "center": round(1.8,3),
                        "points": [{"x":i,"y":round(abs(random.gauss(1.8,0.4)),3),"out_of_control":False} for i in range(20)]},
            "process_stable": False, "out_of_control_points": 2, "note": "Demo data"
        }

    @staticmethod
    def detect_process_shift(factory_id: int, machine_id: int,
                              metric: str, days: int = 14) -> dict:
        """
        Nelson rule 2: 9 consecutive points on same side of center line.
        Nelson rule 3: 6 points in a row steadily increasing/decreasing.
        """
        sql = """
            SELECT metric_value FROM sensor_data
            WHERE factory_id = :fid
              AND device_id IN (SELECT id FROM iot_devices WHERE machine_id = :mid AND factory_id = :fid)
              AND metric_name = :metric
              AND recorded_at >= NOW() - INTERVAL ':days days'
              AND quality_flag = 'good'
            ORDER BY recorded_at ASC LIMIT 200
        """
        rows = db.session.execute(text(sql), {
            "fid": factory_id, "mid": machine_id,
            "metric": metric, "days": days
        }).fetchall()
        values = [float(r.metric_value) for r in rows]

        if len(values) < 9:
            return {"shift_detected": False, "message": "Insufficient data"}

        mean = sum(values) / len(values)
        violations = []

        # Nelson Rule 2: 9 consecutive same side
        for i in range(len(values) - 8):
            window = values[i:i+9]
            above = all(v > mean for v in window)
            below = all(v < mean for v in window)
            if above:
                violations.append({"rule": 2, "position": i, "type": "9 points above mean", "severity": "high"})
            elif below:
                violations.append({"rule": 2, "position": i, "type": "9 points below mean", "severity": "high"})

        # Nelson Rule 3: 6 monotonically increasing/decreasing
        for i in range(len(values) - 5):
            window = values[i:i+6]
            increasing = all(window[j] < window[j+1] for j in range(5))
            decreasing = all(window[j] > window[j+1] for j in range(5))
            if increasing:
                violations.append({"rule": 3, "position": i, "type": "6 points trending up", "severity": "medium"})
            elif decreasing:
                violations.append({"rule": 3, "position": i, "type": "6 points trending down", "severity": "medium"})

        return {
            "shift_detected": len(violations) > 0,
            "violations": violations[:5],
            "mean": round(mean, 4),
            "n": len(values),
            "message": f"{len(violations)} pattern violation(s) detected" if violations else "Process is stable"
        }

    @staticmethod
    def get_process_stability_score(factory_id: int, days: int = 30) -> float:
        """Returns a 0-100 stability score based on OOC rate."""
        sql = """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN is_out_of_control THEN 1 ELSE 0 END) AS ooc
            FROM spc_samples ss
            JOIN spc_control_charts cc ON cc.id = ss.chart_id
            WHERE cc.factory_id = :fid
              AND ss.sampled_at >= NOW() - INTERVAL ':days days'
        """
        row = db.session.execute(text(sql), {"fid": factory_id, "days": days}).fetchone()
        total = int(row.total or 1)
        ooc = int(row.ooc or 0)
        ooc_rate = ooc / total
        score = max(0, 100 * (1 - ooc_rate * 10))
        return round(score, 2)
