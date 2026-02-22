"""
Quality 4.0 Routes — IoT, SPC, Maintenance, Chatbot, Traceability, KPIs
"""
from datetime import date
from flask import Blueprint, request, jsonify
from middleware.auth_middleware import token_required
from services.iot_service import IoTService, MaintenanceService
from services.spc_service import SPCService
from services.chatbot_service import ChatbotService, RCAService
from models import db
from sqlalchemy import text
import json

q40_bp = Blueprint('q40', __name__)


def fid(cu): return cu["factory_id"]


# ═══════════════════════════════════════════════════════
# IOT DEVICES
# ═══════════════════════════════════════════════════════

@q40_bp.route('/iot/devices', methods=['GET'])
@token_required
def get_devices(current_user):
    machine_id = request.args.get('machine_id', type=int)
    data = IoTService.get_devices(fid(current_user), machine_id)
    return jsonify(data)


@q40_bp.route('/iot/devices', methods=['POST'])
@token_required
def create_device(current_user):
    data = request.get_json()
    result = IoTService.create_device(fid(current_user), data)
    return jsonify(result), 201


@q40_bp.route('/iot/ingest', methods=['POST'])
@token_required
def ingest_sensor(current_user):
    data = request.get_json()
    device_id = data.get('device_id')
    readings = data.get('readings', [])
    if not device_id or not readings:
        return jsonify({"error": "device_id and readings required"}), 400
    result = IoTService.ingest_sensor_data(fid(current_user), device_id, readings)
    return jsonify(result), 201


@q40_bp.route('/iot/summary', methods=['GET'])
@token_required
def sensor_summary(current_user):
    hours = int(request.args.get('hours', 1))
    data = IoTService.get_sensor_summary(fid(current_user), hours)
    return jsonify(data)


@q40_bp.route('/iot/timeseries', methods=['GET'])
@token_required
def sensor_timeseries(current_user):
    device_id = request.args.get('device_id', type=int)
    metric = request.args.get('metric', 'temperature')
    hours = int(request.args.get('hours', 24))
    if not device_id:
        return jsonify({"error": "device_id required"}), 400
    data = IoTService.get_sensor_timeseries(fid(current_user), device_id, metric, hours)
    return jsonify(data)


# ═══════════════════════════════════════════════════════
# SPC — Statistical Process Control
# ═══════════════════════════════════════════════════════

@q40_bp.route('/spc/cpk', methods=['GET'])
@token_required
def get_cpk(current_user):
    machine_id = request.args.get('machine_id', type=int)
    metric = request.args.get('metric', 'temperature')
    usl = float(request.args.get('usl', 55.0))
    lsl = float(request.args.get('lsl', 45.0))
    days = int(request.args.get('days', 30))
    if not machine_id:
        return jsonify({"error": "machine_id required"}), 400
    data = SPCService.calculate_cpk(fid(current_user), machine_id, metric, usl, lsl, days)
    return jsonify(data)


@q40_bp.route('/spc/control-chart', methods=['GET'])
@token_required
def control_chart(current_user):
    machine_id = request.args.get('machine_id', type=int)
    metric = request.args.get('metric', 'temperature')
    sample_size = int(request.args.get('sample_size', 5))
    days = int(request.args.get('days', 14))
    data = SPCService.generate_control_chart(
        fid(current_user), machine_id or 1, metric, sample_size, days)
    return jsonify(data)


@q40_bp.route('/spc/shift-detect', methods=['GET'])
@token_required
def detect_shift(current_user):
    machine_id = request.args.get('machine_id', type=int)
    metric = request.args.get('metric', 'temperature')
    days = int(request.args.get('days', 14))
    data = SPCService.detect_process_shift(
        fid(current_user), machine_id or 1, metric, days)
    return jsonify(data)


@q40_bp.route('/spc/stability', methods=['GET'])
@token_required
def process_stability(current_user):
    days = int(request.args.get('days', 30))
    score = SPCService.get_process_stability_score(fid(current_user), days)
    return jsonify({"process_stability_score": score})


# ═══════════════════════════════════════════════════════
# PREDICTIVE MAINTENANCE
# ═══════════════════════════════════════════════════════

@q40_bp.route('/maintenance/mtbf', methods=['GET'])
@token_required
def get_mtbf(current_user):
    machine_id = request.args.get('machine_id', type=int)
    if not machine_id:
        return jsonify({"error": "machine_id required"}), 400
    data = MaintenanceService.calculate_mtbf(fid(current_user), machine_id)
    return jsonify(data)


@q40_bp.route('/maintenance/predict', methods=['GET'])
@token_required
def predict_failure(current_user):
    machine_id = request.args.get('machine_id', type=int)
    if not machine_id:
        return jsonify({"error": "machine_id required"}), 400
    data = MaintenanceService.predict_failure(fid(current_user), machine_id)
    return jsonify(data)


@q40_bp.route('/maintenance/schedule', methods=['GET'])
@token_required
def maintenance_schedule(current_user):
    data = MaintenanceService.get_maintenance_schedule(fid(current_user))
    return jsonify(data)


@q40_bp.route('/maintenance/risk-scores', methods=['GET'])
@token_required
def get_risk_scores(current_user):
    data = MaintenanceService.get_risk_scores(fid(current_user))
    return jsonify(data)


@q40_bp.route('/maintenance/risk-scores/generate', methods=['POST'])
@token_required
def generate_risk_scores(current_user):
    data = MaintenanceService.generate_risk_scores(fid(current_user))
    return jsonify({"generated": len(data), "scores": data})


@q40_bp.route('/maintenance/events', methods=['GET'])
@token_required
def get_maintenance_events(current_user):
    machine_id = request.args.get('machine_id', type=int)
    filters = ["factory_id = :fid"]
    params = {"fid": fid(current_user)}
    if machine_id:
        filters.append("machine_id = :mid")
        params["mid"] = machine_id
    where = " AND ".join(filters)
    rows = db.session.execute(text(f"""
        SELECT me.*, m.code AS machine_code, u.name AS technician_name
        FROM maintenance_events me
        LEFT JOIN machines m ON m.id = me.machine_id
        LEFT JOIN users u ON u.id = me.technician_id
        WHERE me.{where}
        ORDER BY me.started_at DESC LIMIT 50
    """), params).fetchall()
    return jsonify([dict(r._mapping) for r in rows])


@q40_bp.route('/maintenance/events', methods=['POST'])
@token_required
def create_maintenance_event(current_user):
    data = request.get_json()
    row = db.session.execute(text("""
        INSERT INTO maintenance_events
            (machine_id, event_type, started_at, ended_at, duration_hours,
             technician_id, description, cost, factory_id)
        VALUES (:mid, :etype, :started, :ended, :dur, :tech, :desc, :cost, :fid)
        RETURNING id, started_at
    """), {
        "mid": data["machine_id"], "etype": data.get("event_type", "planned"),
        "started": data["started_at"], "ended": data.get("ended_at"),
        "dur": data.get("duration_hours"), "tech": data.get("technician_id"),
        "desc": data.get("description"), "cost": data.get("cost"),
        "fid": fid(current_user)
    }).fetchone()
    db.session.commit()
    return jsonify({"id": row.id}), 201


# ═══════════════════════════════════════════════════════
# CHATBOT
# ═══════════════════════════════════════════════════════

@q40_bp.route('/chatbot/query', methods=['POST'])
@token_required
def chatbot_query(current_user):
    data = request.get_json()
    question = data.get('question', '').strip()
    if not question:
        return jsonify({"error": "question is required"}), 400
    result = ChatbotService.process_query(
        fid(current_user), current_user["id"], question)
    return jsonify(result)


@q40_bp.route('/chatbot/history', methods=['GET'])
@token_required
def chatbot_history(current_user):
    limit = int(request.args.get('limit', 20))
    data = ChatbotService.get_history(fid(current_user), limit)
    return jsonify(data)


# ═══════════════════════════════════════════════════════
# RCA — Root Cause Analysis 4.0
# ═══════════════════════════════════════════════════════

@q40_bp.route('/rca/predict', methods=['POST'])
@token_required
def rca_predict(current_user):
    data = request.get_json()
    result = RCAService.predict_root_cause(
        fid(current_user),
        data.get('defect_code', ''),
        data.get('machine_code'),
        data.get('shift')
    )
    return jsonify(result)


@q40_bp.route('/rca/feature-importance', methods=['GET'])
@token_required
def feature_importance(current_user):
    data = RCAService.generate_feature_importance(fid(current_user))
    return jsonify(data)


@q40_bp.route('/rca/clusters', methods=['GET'])
@token_required
def defect_clusters(current_user):
    days = int(request.args.get('days', 30))
    data = RCAService.defect_cluster_analysis(fid(current_user), days)
    return jsonify(data)


# ═══════════════════════════════════════════════════════
# PRODUCTION BATCHES (Traceability)
# ═══════════════════════════════════════════════════════

@q40_bp.route('/batches', methods=['GET'])
@token_required
def get_batches(current_user):
    status = request.args.get('status')
    filters = ["pb.factory_id = :fid", "pb.deleted_at IS NULL"]
    params = {"fid": fid(current_user)}
    if status:
        filters.append("pb.status = :status")
        params["status"] = status
    where = " AND ".join(filters)
    rows = db.session.execute(text(f"""
        SELECT pb.*, COUNT(btl.id) AS trace_count
        FROM production_batches pb
        LEFT JOIN batch_trace_links btl ON btl.batch_id = pb.id
        WHERE {where}
        GROUP BY pb.id ORDER BY pb.production_date DESC LIMIT 100
    """), params).fetchall()
    return jsonify([dict(r._mapping) for r in rows])


@q40_bp.route('/batches', methods=['POST'])
@token_required
def create_batch(current_user):
    data = request.get_json()
    try:
        row = db.session.execute(text("""
            INSERT INTO production_batches
                (batch_number, material_supplier, material_type, production_date,
                 quantity, status, notes, factory_id)
            VALUES (:bn, :supplier, :mtype, :pdate, :qty, :status, :notes, :fid)
            RETURNING id, batch_number, created_at
        """), {
            "bn": data["batch_number"], "supplier": data.get("material_supplier"),
            "mtype": data.get("material_type"), "pdate": data.get("production_date", str(date.today())),
            "qty": data.get("quantity"), "status": data.get("status", "in_production"),
            "notes": data.get("notes"), "fid": fid(current_user)
        }).fetchone()
        db.session.commit()
        return jsonify(dict(row._mapping)), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@q40_bp.route('/batches/<int:batch_id>/trace', methods=['GET'])
@token_required
def get_batch_trace(current_user, batch_id):
    rows = db.session.execute(text("""
        SELECT btl.*,
               m.code AS machine_code, u.name AS operator_name,
               dr.quantity_defective, dc.code AS defect_code,
               ca.description AS corrective_action
        FROM batch_trace_links btl
        LEFT JOIN machines m ON m.id = btl.machine_id
        LEFT JOIN users u ON u.id = btl.operator_id
        LEFT JOIN defect_records dr ON dr.id = btl.defect_record_id
        LEFT JOIN defect_codes dc ON dc.id = dr.defect_code_id
        LEFT JOIN corrective_actions ca ON ca.id = btl.corrective_action_id
        WHERE btl.batch_id = :bid AND btl.factory_id = :fid
        ORDER BY btl.linked_at
    """), {"bid": batch_id, "fid": fid(current_user)}).fetchall()
    return jsonify([dict(r._mapping) for r in rows])


# ═══════════════════════════════════════════════════════
# QUALITY 4.0 KPIs
# ═══════════════════════════════════════════════════════

@q40_bp.route('/kpis', methods=['GET'])
@token_required
def get_kpis(current_user):
    factory_id = fid(current_user)
    days = int(request.args.get('days', 30))

    # PPM
    ppm_row = db.session.execute(text("""
        SELECT CASE WHEN SUM(quantity_produced)>0
               THEN SUM(quantity_defective)::FLOAT/SUM(quantity_produced)*1000000 ELSE 0 END AS ppm,
               SUM(quantity_defective) AS qty_def, SUM(quantity_produced) AS qty_prod
        FROM defect_records WHERE factory_id=:fid AND deleted_at IS NULL
          AND defect_date >= CURRENT_DATE - :days * INTERVAL '1 day'
    """), {"fid": factory_id, "days": days}).fetchone()

    # Anomalies
    anomaly_count = db.session.execute(text("""
        SELECT COUNT(*) FROM anomaly_alerts
        WHERE factory_id=:fid AND created_at >= NOW() - (:days * INTERVAL '1 day')
    """), {"fid": factory_id, "days": days}).scalar() or 0

    # SPC stability
    stability = SPCService.get_process_stability_score(factory_id, days)

    # Risk index
    risk_row = db.session.execute(text("""
        SELECT AVG(probability_score) AS avg_risk FROM risk_scores
        WHERE factory_id=:fid AND is_active=TRUE
    """), {"fid": factory_id}).fetchone()
    risk_index = float(risk_row.avg_risk or 0.15)

    # COPQ estimate: $50 per defective unit
    copq = float(ppm_row.qty_def or 0) * 50

    ppm = float(ppm_row.ppm or 0)
    fpy = max(0, 100 - ppm / 10000)

    # OEE calculation
    try:
        oee_row = db.session.execute(text("""
            SELECT AVG(COALESCE(availability_pct,88)) AS avail,
                   AVG(COALESCE(performance_pct,93))  AS perf,
                   AVG(COALESCE(quality_pct,99.8))    AS qual
            FROM oee_records
            WHERE factory_id=:fid
              AND record_date >= CURRENT_DATE - :days * INTERVAL '1 day'
        """), {"fid": factory_id, "days": days}).fetchone()
        avail = float(oee_row.avail or 88)
        perf  = float(oee_row.perf  or 93)
        qual  = float(oee_row.qual  or 99.8)
        oee_pct = round(avail * perf * qual / 10000, 2)
    except Exception:
        avail, perf, qual, oee_pct = 88.0, 93.0, 99.8, 81.3

    # AI model accuracy
    try:
        ai_row = db.session.execute(text("""
            SELECT accuracy FROM ai_models
            WHERE factory_id=:fid AND is_active=TRUE
            ORDER BY trained_at DESC LIMIT 1
        """), {"fid": factory_id}).fetchone()
        ai_confidence = float(ai_row.accuracy) if ai_row and ai_row.accuracy else 0.0
    except Exception:
        ai_confidence = 0.0

    return jsonify({
        "period_days":              days,
        "ppm":                      round(ppm, 2),
        "first_pass_yield_pct":     round(fpy, 2),
        "oee_pct":                  oee_pct,
        "availability_pct":         round(avail, 2),
        "performance_pct":          round(perf,  2),
        "quality_pct":              round(qual,  2),
        "process_stability_score":  stability,
        "risk_index":               round(risk_index, 4),
        "copq_usd":                 round(copq, 2),
        "ai_confidence_score":      ai_confidence,
        "anomaly_count":            int(anomaly_count),
        "smart_compliance_index":   round(min(100, stability * 0.4 + fpy * 0.4 + (1 - risk_index) * 20), 2),
        "predictive_accuracy_pct":  round(ai_confidence * 100, 1),
    })


# ═══════════════════════════════════════════════════════
# DIGITAL TWIN
# ═══════════════════════════════════════════════════════

@q40_bp.route('/digital-twin/assets', methods=['GET'])
@token_required
def get_digital_assets(current_user):
    rows = db.session.execute(text("""
        SELECT da.*, m.code AS machine_code, m.name AS machine_name
        FROM digital_assets da
        LEFT JOIN machines m ON m.id = da.machine_id
        WHERE da.factory_id=:fid AND da.deleted_at IS NULL
        ORDER BY da.name
    """), {"fid": fid(current_user)}).fetchall()
    return jsonify([dict(r._mapping) for r in rows])


@q40_bp.route('/digital-twin/assets', methods=['POST'])
@token_required
def create_digital_asset(current_user):
    data = request.get_json()
    row = db.session.execute(text("""
        INSERT INTO digital_assets (machine_id, name, virtual_model_reference, status, parameters, factory_id)
        VALUES (:mid, :name, :ref, :status, :params, :fid)
        RETURNING id, name, created_at
    """), {
        "mid": data.get("machine_id"), "name": data["name"],
        "ref": data.get("virtual_model_reference", ""),
        "status": data.get("status", "active"),
        "params": json.dumps(data.get("parameters", {})),
        "fid": fid(current_user)
    }).fetchone()
    db.session.commit()
    return jsonify(dict(row._mapping)), 201


# ═══════════════════════════════════════════════════════
# OPERATOR PERFORMANCE
# ═══════════════════════════════════════════════════════

@q40_bp.route('/operators/performance', methods=['GET'])
@token_required
def operator_performance(current_user):
    days = int(request.args.get('days', 30))
    rows = db.session.execute(text("""
        SELECT u.id, u.name,
               SUM(dr.quantity_produced) AS total_produced,
               SUM(dr.quantity_defective) AS total_defective,
               CASE WHEN SUM(dr.quantity_produced)>0
                    THEN ROUND(SUM(dr.quantity_defective)::NUMERIC/SUM(dr.quantity_produced)*100,4)
                    ELSE 0 END AS defect_rate_pct,
               COUNT(DISTINCT dr.defect_date) AS active_days,
               CASE WHEN SUM(dr.quantity_produced)>0
                    THEN ROUND(100-SUM(dr.quantity_defective)::NUMERIC/SUM(dr.quantity_produced)*100,2)
                    ELSE 100 END AS quality_score
        FROM defect_records dr
        JOIN users u ON u.id = dr.operator_id
        WHERE dr.factory_id=:fid AND dr.deleted_at IS NULL
          AND dr.defect_date >= CURRENT_DATE - :days * INTERVAL '1 day'
        GROUP BY u.id, u.name
        ORDER BY defect_rate_pct ASC
        LIMIT 20
    """), {"fid": fid(current_user), "days": days}).fetchall()
    return jsonify([dict(r._mapping) for r in rows])
