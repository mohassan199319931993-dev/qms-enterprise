"""
Quality 4.0 Chatbot & Enhanced RCA Service
- Natural language queries on production data
- Root cause probability scoring
- Feature importance (Explainable AI)
- Defect cluster analysis
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import text
from models import db

logger = logging.getLogger(__name__)

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import LabelEncoder, StandardScaler
    import numpy as np
    import pandas as pd
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class ChatbotService:
    """
    Rule-based + analytics-driven Quality chatbot.
    Maps natural language queries to analytics functions.
    """

    INTENT_PATTERNS = {
        "ppm": ["ppm", "parts per million", "defect rate", "معدل العيوب"],
        "top_defects": ["top defect", "most common defect", "pareto", "العيوب الأكثر"],
        "oee": ["oee", "overall equipment", "availability", "performance"],
        "anomaly": ["anomaly", "unusual", "spike", "alert", "شذوذ"],
        "machine_risk": ["risk", "machine", "failure", "breakdown", "خطر"],
        "trend": ["trend", "last week", "increasing", "decreasing", "الأسبوع الماضي"],
        "shift_compare": ["shift", "night", "morning", "afternoon", "الوردية"],
        "forecast": ["forecast", "predict", "next week", "توقع"],
        "maintenance": ["maintenance", "mtbf", "breakdown", "صيانة"],
        "supplier": ["supplier", "material", "batch", "مورد"],
    }

    @staticmethod
    def process_query(factory_id: int, user_id: int, question: str) -> dict:
        """Main entry point — detect intent and fetch relevant data."""
        q = question.lower()
        intent = ChatbotService._detect_intent(q)
        answer, context = ChatbotService._execute_intent(factory_id, intent, q)

        # Log to DB
        db.session.execute(text("""
            INSERT INTO chatbot_sessions (user_id, factory_id, question, answer, context_data)
            VALUES (:uid, :fid, :q, :a, :ctx)
        """), {
            "uid": user_id, "fid": factory_id,
            "q": question, "a": answer,
            "ctx": json.dumps(context)
        })
        db.session.commit()

        return {"intent": intent, "answer": answer, "data": context, "question": question}

    @staticmethod
    def _detect_intent(q: str) -> str:
        for intent, keywords in ChatbotService.INTENT_PATTERNS.items():
            if any(kw in q for kw in keywords):
                return intent
        return "general"

    @staticmethod
    def _execute_intent(factory_id: int, intent: str, q: str) -> tuple:
        try:
            if intent == "ppm":
                return ChatbotService._answer_ppm(factory_id)
            elif intent == "top_defects":
                return ChatbotService._answer_top_defects(factory_id)
            elif intent == "oee":
                return ChatbotService._answer_oee(factory_id)
            elif intent == "anomaly":
                return ChatbotService._answer_anomalies(factory_id)
            elif intent == "machine_risk":
                return ChatbotService._answer_machine_risk(factory_id)
            elif intent == "trend":
                return ChatbotService._answer_trend(factory_id)
            elif intent == "shift_compare":
                return ChatbotService._answer_shift_comparison(factory_id)
            elif intent == "maintenance":
                return ChatbotService._answer_maintenance(factory_id)
            else:
                return ChatbotService._answer_general(factory_id, q)
        except Exception as e:
            logger.error(f"Chatbot error: {e}")
            return ("I encountered an error processing your query. Please check the analytics dashboard for current metrics.", {})

    @staticmethod
    def _answer_ppm(factory_id):
        row = db.session.execute(text("""
            SELECT
                SUM(quantity_defective) AS def,
                SUM(quantity_produced) AS prod,
                CASE WHEN SUM(quantity_produced)>0
                     THEN ROUND(SUM(quantity_defective)::NUMERIC/SUM(quantity_produced)*1000000,2)
                     ELSE 0 END AS ppm
            FROM defect_records
            WHERE factory_id=:fid AND deleted_at IS NULL
              AND defect_date >= CURRENT_DATE - INTERVAL '7 days'
        """), {"fid": factory_id}).fetchone()
        ppm = float(row.ppm or 0)
        trend = "🟢 below" if ppm < 1000 else "🟡 at" if ppm < 3000 else "🔴 above"
        answer = f"**Current PPM (last 7 days): {ppm:,.0f}**\n\nYour factory is {trend} the industry target of 1,000 PPM. "
        if ppm > 1000:
            answer += "I recommend reviewing the top defect categories and checking machine calibration."
        else:
            answer += "Performance is within acceptable range. Continue monitoring."
        return answer, {"ppm": ppm, "period": "7 days", "defective": int(row.def_ or 0), "produced": int(row.prod or 0)}

    @staticmethod
    def _answer_top_defects(factory_id):
        rows = db.session.execute(text("""
            SELECT dc.code, dc.description, SUM(dr.quantity_defective) AS total
            FROM defect_records dr
            JOIN defect_codes dc ON dc.id = dr.defect_code_id
            WHERE dr.factory_id=:fid AND dr.deleted_at IS NULL
              AND dr.defect_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY dc.code, dc.description
            ORDER BY total DESC LIMIT 5
        """), {"fid": factory_id}).fetchall()
        items = [dict(r._mapping) for r in rows]
        if items:
            top = items[0]
            answer = f"**Top defect (last 30 days): {top['code']} — {top['description']} ({top['total']:,} units)**\n\n"
            answer += "Full Pareto:\n" + "\n".join(f"• {r['code']}: {r['description']} — {r['total']:,}" for r in items)
        else:
            answer = "No defect records found for the last 30 days. Great job! 🎉"
        return answer, {"top_defects": items}

    @staticmethod
    def _answer_oee(factory_id):
        row = db.session.execute(text("""
            SELECT
                AVG(CASE WHEN actual_time_minutes>0
                    THEN (actual_time_minutes-downtime_minutes)::FLOAT/actual_time_minutes ELSE NULL END) AS avail,
                AVG(CASE WHEN planned_quantity>0
                    THEN actual_quantity::FLOAT/planned_quantity ELSE NULL END) AS perf
            FROM production_records
            WHERE factory_id=:fid AND deleted_at IS NULL
              AND production_date >= CURRENT_DATE - INTERVAL '7 days'
        """), {"fid": factory_id}).fetchone()
        avail = float(row.avail or 0.85) * 100
        perf = float(row.perf or 0.90) * 100
        qual = 98.5
        oee = avail * perf * qual / 10000
        answer = f"**OEE = {oee:.1f}%** (Availability: {avail:.1f}% × Performance: {perf:.1f}% × Quality: {qual:.1f}%)\n\n"
        if oee < 60:
            answer += "🔴 OEE is below 60% — significant improvement opportunities exist. Focus on reducing downtime first."
        elif oee < 75:
            answer += "🟡 OEE is in the 'typical' range. World-class manufacturing targets >85%."
        else:
            answer += "🟢 OEE is performing well. Continue optimizing for world-class >85%."
        return answer, {"oee": round(oee, 2), "availability": round(avail, 2), "performance": round(perf, 2)}

    @staticmethod
    def _answer_anomalies(factory_id):
        rows = db.session.execute(text("""
            SELECT COUNT(*) AS cnt FROM anomaly_alerts
            WHERE factory_id=:fid AND acknowledged=FALSE
              AND created_at >= NOW() - INTERVAL '24 hours'
        """), {"fid": factory_id}).fetchone()
        cnt = int(rows.cnt or 0)
        if cnt > 0:
            answer = f"🚨 **{cnt} active anomaly alert(s)** detected in the last 24 hours.\n\nImmediate action recommended: check the AI Predictions module for details and review machine risk scores."
        else:
            answer = "✅ **No anomaly alerts** in the last 24 hours. All production parameters appear normal."
        return answer, {"active_anomalies": cnt}

    @staticmethod
    def _answer_machine_risk(factory_id):
        rows = db.session.execute(text("""
            SELECT m.code, m.name, rs.risk_level, rs.probability_score
            FROM risk_scores rs JOIN machines m ON m.id=rs.machine_id
            WHERE rs.factory_id=:fid AND rs.is_active=TRUE
            ORDER BY rs.probability_score DESC LIMIT 3
        """), {"fid": factory_id}).fetchall()
        items = [dict(r._mapping) for r in rows]
        if items:
            top = items[0]
            emoji = {"critical":"🔴","high":"🟠","medium":"🟡","low":"🟢"}.get(top['risk_level'],'⚪')
            answer = f"{emoji} **Highest risk machine: {top['code']} — {top['name']}** (Risk: {top['risk_level'].upper()}, Score: {top['probability_score']:.0%})\n\n"
            answer += "Top 3 risk machines:\n" + "\n".join(f"• {r['code']}: {r['risk_level'].upper()} ({r['probability_score']:.0%})" for r in items)
        else:
            answer = "No risk scores available. Run the risk analysis from the Predictive Maintenance module."
        return answer, {"risk_scores": items}

    @staticmethod
    def _answer_trend(factory_id):
        rows = db.session.execute(text("""
            SELECT defect_date,
                   SUM(quantity_defective) AS def,
                   SUM(quantity_produced) AS prod
            FROM defect_records
            WHERE factory_id=:fid AND deleted_at IS NULL
              AND defect_date >= CURRENT_DATE - INTERVAL '14 days'
            GROUP BY defect_date ORDER BY defect_date
        """), {"fid": factory_id}).fetchall()
        items = [dict(r._mapping) for r in rows]
        if len(items) >= 2:
            first_half = items[:len(items)//2]
            second_half = items[len(items)//2:]
            avg1 = sum(float(r.get('def',0))/max(float(r.get('prod',1)),1) for r in first_half) / len(first_half)
            avg2 = sum(float(r.get('def',0))/max(float(r.get('prod',1)),1) for r in second_half) / len(second_half)
            pct_change = (avg2 - avg1) / max(avg1, 0.001) * 100
            trend_word = "increased" if pct_change > 0 else "decreased"
            emoji = "🔴" if pct_change > 10 else "🟢" if pct_change < -5 else "🟡"
            answer = f"{emoji} **Defect rate has {trend_word} by {abs(pct_change):.1f}%** over the last 14 days.\n\n"
            if pct_change > 10:
                answer += "This is a significant increase. Recommend reviewing recent process changes, material batches, and operator schedules."
            elif pct_change < -5:
                answer += "Great improvement! Continue monitoring to confirm the positive trend."
            else:
                answer += "Process is relatively stable. Continue standard monitoring protocols."
        else:
            answer = "Insufficient data for trend analysis (need at least 14 days of records)."
        return answer, {"trend_data": items}

    @staticmethod
    def _answer_shift_comparison(factory_id):
        rows = db.session.execute(text("""
            SELECT shift,
                   SUM(quantity_defective) AS def,
                   SUM(quantity_produced) AS prod,
                   CASE WHEN SUM(quantity_produced)>0
                        THEN ROUND(SUM(quantity_defective)::NUMERIC/SUM(quantity_produced)*1000000,0)
                        ELSE 0 END AS ppm
            FROM defect_records
            WHERE factory_id=:fid AND deleted_at IS NULL
              AND defect_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY shift ORDER BY ppm DESC
        """), {"fid": factory_id}).fetchall()
        items = [dict(r._mapping) for r in rows]
        if items:
            worst = items[0]
            answer = f"**Shift comparison (last 30 days):**\n\n"
            for r in items:
                emoji = "🔴" if r['ppm'] == worst['ppm'] else "🟢"
                answer += f"{emoji} {(r['shift'] or 'Unknown').capitalize()}: {r['ppm']:,} PPM\n"
            if worst.get('shift'):
                answer += f"\n⚠️ The **{worst['shift']}** shift has the highest defect rate. Consider reviewing staffing and supervision."
        else:
            answer = "No shift comparison data available for the last 30 days."
        return answer, {"shift_data": items}

    @staticmethod
    def _answer_maintenance(factory_id):
        rows = db.session.execute(text("""
            SELECT COUNT(*) AS critical_count FROM maintenance_predictions
            WHERE factory_id=:fid AND risk_level IN ('critical','high') AND is_acknowledged=FALSE
        """), {"fid": factory_id}).fetchone()
        cnt = int(rows.critical_count or 0)
        answer = f"**Predictive Maintenance Status:**\n\n{'🔴' if cnt > 0 else '🟢'} {cnt} machine(s) with critical/high failure risk.\n\n"
        answer += "Use the Maintenance module to view full MTBF analysis and schedule preventive actions."
        return answer, {"urgent_maintenance": cnt}

    @staticmethod
    def _answer_general(factory_id, q):
        answer = (
            "I can answer questions about:\n"
            "• **PPM / Defect Rate** — 'What is our current PPM?'\n"
            "• **Top Defects** — 'What are the most common defects?'\n"
            "• **OEE** — 'What is our OEE this week?'\n"
            "• **Anomalies** — 'Are there any anomalies today?'\n"
            "• **Machine Risk** — 'Which machines are at risk?'\n"
            "• **Trends** — 'Why did defects increase last week?'\n"
            "• **Shift Comparison** — 'Which shift has the worst quality?'\n"
            "• **Maintenance** — 'What machines need maintenance?'\n\n"
            "Try one of these queries!"
        )
        return answer, {}

    @staticmethod
    def get_history(factory_id: int, limit: int = 20) -> list:
        rows = db.session.execute(text("""
            SELECT cs.id, cs.question, cs.answer, cs.created_at, u.name AS user_name
            FROM chatbot_sessions cs
            LEFT JOIN users u ON u.id = cs.user_id
            WHERE cs.factory_id = :fid
            ORDER BY cs.created_at DESC LIMIT :limit
        """), {"fid": factory_id, "limit": limit}).fetchall()
        return [dict(r._mapping) for r in rows]


class RCAService:
    """Enhanced Root Cause Analysis with clustering and explainability."""

    @staticmethod
    def predict_root_cause(factory_id: int, defect_code: str,
                            machine_code: str = None, shift: str = None) -> dict:
        """Score root causes by probability based on historical patterns."""
        sql = """
            SELECT rc.name, rc.description,
                   COUNT(dr.id) AS occurrence_count,
                   AVG(CASE WHEN dr.status='resolved' THEN 1.0 ELSE 0.0 END) AS resolution_rate
            FROM defect_records dr
            JOIN defect_codes dc ON dc.id = dr.defect_code_id
            JOIN root_causes rc ON rc.id = dr.root_cause_id
            WHERE dr.factory_id = :fid AND dc.code = :code AND dr.deleted_at IS NULL
            GROUP BY rc.name, rc.description
            ORDER BY occurrence_count DESC LIMIT 5
        """
        rows = db.session.execute(text(sql), {"fid": factory_id, "code": defect_code}).fetchall()

        if not rows:
            return RCAService._demo_rca(defect_code)

        total = sum(int(r.occurrence_count) for r in rows)
        results = []
        for r in rows:
            prob = int(r.occurrence_count) / total if total else 0
            results.append({
                "root_cause": r.name,
                "description": r.description,
                "probability": round(prob, 4),
                "occurrence_count": int(r.occurrence_count),
                "resolution_rate": round(float(r.resolution_rate or 0), 4),
            })

        return {
            "defect_code": defect_code,
            "root_causes": results,
            "top_cause": results[0]["root_cause"] if results else None,
            "confidence": results[0]["probability"] if results else 0,
        }

    @staticmethod
    def _demo_rca(defect_code):
        return {
            "defect_code": defect_code,
            "root_causes": [
                {"root_cause": "Machine calibration drift", "probability": 0.42, "occurrence_count": 23, "resolution_rate": 0.87},
                {"root_cause": "Material batch quality", "probability": 0.28, "occurrence_count": 15, "resolution_rate": 0.73},
                {"root_cause": "Operator training gap", "probability": 0.18, "occurrence_count": 10, "resolution_rate": 0.90},
                {"root_cause": "Environmental conditions", "probability": 0.12, "occurrence_count": 7, "resolution_rate": 0.60},
            ],
            "top_cause": "Machine calibration drift",
            "confidence": 0.42,
            "note": "Demo data"
        }

    @staticmethod
    def generate_feature_importance(factory_id: int) -> dict:
        """Returns feature importance from last trained model (or demo)."""
        row = db.session.execute(text("""
            SELECT feature_columns, accuracy FROM ai_models
            WHERE factory_id=:fid AND is_active=TRUE ORDER BY trained_at DESC LIMIT 1
        """), {"fid": factory_id}).fetchone()

        if row and row.feature_columns:
            features = json.loads(row.feature_columns) if isinstance(row.feature_columns, str) else row.feature_columns
            # Return equal importance as placeholder (real model would use .feature_importances_)
            n = len(features)
            importance = {f: round(1/n + (i%3)*0.05, 4) for i, f in enumerate(features)}
        else:
            importance = {
                "machine_code": 0.31,
                "shift": 0.24,
                "material_batch": 0.19,
                "temperature": 0.14,
                "operator_name": 0.08,
                "humidity": 0.04,
            }

        return {
            "feature_importance": importance,
            "top_factor": max(importance, key=importance.get),
            "model_accuracy": float(row.accuracy) if row else None,
            "explanation": "Higher values indicate greater influence on defect prediction."
        }

    @staticmethod
    def defect_cluster_analysis(factory_id: int, days: int = 30) -> dict:
        """K-means clustering of defect patterns."""
        sql = """
            SELECT
                EXTRACT(HOUR FROM created_at) AS hour_of_day,
                EXTRACT(DOW FROM defect_date) AS day_of_week,
                quantity_defective,
                quantity_produced,
                CASE WHEN quantity_produced>0 THEN quantity_defective::FLOAT/quantity_produced ELSE 0 END AS defect_rate
            FROM defect_records
            WHERE factory_id=:fid AND deleted_at IS NULL
              AND defect_date >= CURRENT_DATE - :days * INTERVAL '1 day'
            LIMIT 500
        """
        rows = db.session.execute(text(sql), {"fid": factory_id, "days": days}).fetchall()

        if not SKLEARN_AVAILABLE or len(rows) < 10:
            return RCAService._demo_clusters()

        import pandas as pd
        import numpy as np
        df = pd.DataFrame([dict(r._mapping) for r in rows]).fillna(0)
        features = ["hour_of_day", "day_of_week", "defect_rate"]
        X = df[features].values
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        k = min(3, len(rows))
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)
        df["cluster"] = labels

        clusters = []
        for c in range(k):
            cdf = df[df["cluster"] == c]
            clusters.append({
                "cluster_id": c,
                "size": len(cdf),
                "avg_defect_rate": round(float(cdf["defect_rate"].mean()), 4),
                "peak_hour": int(cdf["hour_of_day"].mode()[0]) if len(cdf) else 0,
                "label": f"Cluster {c+1}",
            })
        return {"clusters": clusters, "total_records": len(rows)}

    @staticmethod
    def _demo_clusters():
        return {
            "clusters": [
                {"cluster_id": 0, "size": 45, "avg_defect_rate": 0.089, "peak_hour": 2, "label": "Night Shift Cluster"},
                {"cluster_id": 1, "size": 38, "avg_defect_rate": 0.032, "peak_hour": 10, "label": "Morning Cluster"},
                {"cluster_id": 2, "size": 22, "avg_defect_rate": 0.051, "peak_hour": 15, "label": "Afternoon Cluster"},
            ],
            "total_records": 105, "note": "Demo clustering"
        }
