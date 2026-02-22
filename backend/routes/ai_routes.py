"""
AI Routes — QMS Enterprise
POST /api/ai/train         — Train defect model
POST /api/ai/predict       — Predict defect probability
GET  /api/ai/anomalies     — Detect anomalies
POST /api/ai/recommend     — Corrective action recommendations
GET  /api/ai/forecast      — Quality forecast
GET  /api/ai/model-info    — Current model metadata
GET  /api/ai/versions      — Model version history
POST /api/ai/retrain-all   — Admin: retrain all factories
GET  /api/ai/rca/clusters  — Defect cluster analysis
POST /api/ai/rca/predict   — Root cause prediction
"""
import logging
from flask import Blueprint, request, jsonify, current_app
from middleware.auth_middleware import token_required
from services.ai_service import AIService

logger = logging.getLogger(__name__)
ai_bp = Blueprint('ai', __name__)


# ═══════════════════════════════════════════════════════
# MODEL MANAGEMENT
# ═══════════════════════════════════════════════════════

@ai_bp.route('/train', methods=['POST'])
@token_required
def train(current_user):
    """Train defect prediction model for this factory."""
    factory_id = current_user["factory_id"]
    result = AIService.train_defect_model(factory_id)

    # Broadcast updated model info via WebSocket
    try:
        broadcast = getattr(current_app, 'broadcast_kpi', None)
        if broadcast and result.get("status") == "success":
            broadcast(factory_id, {
                "event":    "model_trained",
                "accuracy": result.get("metrics", {}).get("accuracy"),
            })
    except Exception:
        pass

    status_code = 200 if result.get("status") == "success" else 400
    return jsonify(result), status_code


@ai_bp.route('/model-info', methods=['GET'])
@token_required
def model_info(current_user):
    """Get metadata for current active model."""
    from ai.model_service import ModelService
    info = ModelService.get_model_info(current_user["factory_id"])
    return jsonify(info)


@ai_bp.route('/versions', methods=['GET'])
@token_required
def model_versions(current_user):
    """List all model versions for this factory."""
    from ai.model_registry import ModelRegistry
    versions = ModelRegistry.list_versions(current_user["factory_id"], "defect")
    return jsonify({"versions": versions, "count": len(versions)})


# ═══════════════════════════════════════════════════════
# PREDICTION
# ═══════════════════════════════════════════════════════

@ai_bp.route('/predict', methods=['POST'])
@token_required
def predict(current_user):
    """Predict defect probability for given production conditions."""
    data       = request.get_json() or {}
    factory_id = current_user["factory_id"]

    result = AIService.predict_defect_probability(factory_id, data)

    # Store prediction in DB + broadcast if high risk
    try:
        broadcast = getattr(current_app, 'broadcast_kpi', None)
        if broadcast and result.get("risk_level") in ("critical", "high"):
            broadcast(factory_id, {
                "event":      "high_risk_prediction",
                "risk_level": result["risk_level"],
                "probability": result.get("defect_probability"),
            })
    except Exception:
        pass

    return jsonify(result)


# ═══════════════════════════════════════════════════════
# ANOMALY DETECTION
# ═══════════════════════════════════════════════════════

@ai_bp.route('/anomalies', methods=['GET'])
@token_required
def get_anomalies(current_user):
    """Detect anomalies in recent production data."""
    days      = int(request.args.get('days', 30))
    anomalies = AIService.detect_anomaly(current_user["factory_id"], days)
    return jsonify({
        "count":     len(anomalies),
        "anomalies": anomalies,
        "days":      days,
    })


# ═══════════════════════════════════════════════════════
# CORRECTIVE ACTION RECOMMENDATIONS
# ═══════════════════════════════════════════════════════

@ai_bp.route('/recommend', methods=['POST'])
@token_required
def recommend(current_user):
    """Recommend corrective actions for a defect code."""
    data         = request.get_json() or {}
    defect_code  = data.get("defect_code")
    machine_code = data.get("machine_code")

    if not defect_code:
        return jsonify({"error": "defect_code is required"}), 400

    actions = AIService.recommend_corrective_action(
        current_user["factory_id"], defect_code, machine_code
    )
    return jsonify({"recommendations": actions})


# ═══════════════════════════════════════════════════════
# QUALITY FORECAST
# ═══════════════════════════════════════════════════════

@ai_bp.route('/forecast', methods=['GET'])
@token_required
def forecast(current_user):
    """Quality forecast for upcoming days."""
    days_ahead = int(request.args.get('days', 7))
    data       = AIService.get_quality_forecast(current_user["factory_id"], days_ahead)
    return jsonify({"forecast": data, "days_ahead": days_ahead})


# ═══════════════════════════════════════════════════════
# ROOT CAUSE ANALYSIS
# ═══════════════════════════════════════════════════════

@ai_bp.route('/rca/predict', methods=['POST'])
@token_required
def rca_predict(current_user):
    """Predict root cause for a defect pattern."""
    from services.chatbot_service import RCAService
    data = request.get_json() or {}
    result = RCAService.predict_root_cause(
        current_user["factory_id"],
        data.get("defect_code", ""),
        data.get("machine_code"),
        data.get("shift"),
    )
    return jsonify(result)


@ai_bp.route('/rca/clusters', methods=['GET'])
@token_required
def rca_clusters(current_user):
    """Cluster analysis of defect patterns."""
    from services.chatbot_service import RCAService
    days = int(request.args.get('days', 30))
    data = RCAService.defect_cluster_analysis(current_user["factory_id"], days)
    return jsonify(data)


@ai_bp.route('/rca/feature-importance', methods=['GET'])
@token_required
def rca_feature_importance(current_user):
    """Feature importance for root cause analysis."""
    from services.chatbot_service import RCAService
    data = RCAService.generate_feature_importance(current_user["factory_id"])
    return jsonify(data)


# ═══════════════════════════════════════════════════════
# ADMIN — BATCH OPERATIONS
# ═══════════════════════════════════════════════════════

@ai_bp.route('/retrain-all', methods=['POST'])
@token_required
def retrain_all(current_user):
    """Admin: trigger retraining for all factories."""
    # Only admin role
    if current_user.get("role_name") not in ("admin", "super_admin"):
        return jsonify({"error": "Admin access required"}), 403

    from models import db
    from sqlalchemy import text

    rows = db.session.execute(
        text("SELECT id FROM factories WHERE is_active = TRUE")
    ).fetchall()

    results = []
    for row in rows:
        fid = row[0]
        try:
            r = AIService.train_defect_model(fid)
            results.append({"factory_id": fid, "status": r.get("status"), "accuracy": r.get("metrics", {}).get("accuracy")})
        except Exception as e:
            results.append({"factory_id": fid, "status": "error", "error": str(e)})

    return jsonify({"retrained": len(results), "results": results})
