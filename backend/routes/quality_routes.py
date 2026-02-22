"""
Quality Metrics Routes
GET /api/quality/metrics, /oee, /ppm, /trend, defect CRUD
"""
from datetime import date
from flask import Blueprint, request, jsonify
from middleware.auth_middleware import token_required
from services.quality_metrics_service import QualityMetricsService
from models import db
from sqlalchemy import text
import json

quality_bp = Blueprint('quality', __name__)


def _parse_dates(req):
    start = req.args.get('start_date')
    end = req.args.get('end_date')
    try:
        if start:
            start = date.fromisoformat(start)
        if end:
            end = date.fromisoformat(end)
    except ValueError:
        pass
    return start, end


# ── Aggregate Metrics ─────────────────────────────────────────────────────────

@quality_bp.route('/metrics', methods=['GET'])
@token_required
def get_metrics(current_user):
    start, end = _parse_dates(request)
    data = QualityMetricsService.get_comprehensive_metrics(
        current_user["factory_id"], start, end)
    return jsonify(data)


@quality_bp.route('/oee', methods=['GET'])
@token_required
def get_oee(current_user):
    start, end = _parse_dates(request)
    machine_id = request.args.get('machine_id', type=int)
    data = QualityMetricsService.calculate_oee(
        current_user["factory_id"], start, end, machine_id)
    return jsonify(data)


@quality_bp.route('/ppm', methods=['GET'])
@token_required
def get_ppm(current_user):
    start, end = _parse_dates(request)
    machine_id = request.args.get('machine_id', type=int)
    data = QualityMetricsService.calculate_ppm(
        current_user["factory_id"], start, end, machine_id)
    return jsonify(data)


@quality_bp.route('/trend', methods=['GET'])
@token_required
def get_trend(current_user):
    period = request.args.get('period', 'daily')
    days = int(request.args.get('days', 30))
    data = QualityMetricsService.calculate_trend(
        current_user["factory_id"], period=period, days=days)
    return jsonify(data)


@quality_bp.route('/heatmap', methods=['GET'])
@token_required
def get_heatmap(current_user):
    start, end = _parse_dates(request)
    data = QualityMetricsService.get_machine_heatmap(
        current_user["factory_id"], start, end)
    return jsonify(data)


@quality_bp.route('/pareto', methods=['GET'])
@token_required
def get_pareto(current_user):
    start, end = _parse_dates(request)
    limit = int(request.args.get('limit', 10))
    data = QualityMetricsService.calculate_defect_distribution(
        current_user["factory_id"], start, end, limit)
    return jsonify(data)


# ── Defect Records CRUD ───────────────────────────────────────────────────────

@quality_bp.route('/defects', methods=['GET'])
@token_required
def get_defects(current_user):
    fid = current_user["factory_id"]
    start, end = _parse_dates(request)
    machine_id = request.args.get('machine_id', type=int)
    status = request.args.get('status')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))

    filters = ["dr.factory_id = :fid", "dr.deleted_at IS NULL"]
    params = {"fid": fid, "limit": limit, "offset": offset}

    if start:
        filters.append("dr.defect_date >= :start")
        params["start"] = start
    if end:
        filters.append("dr.defect_date <= :end")
        params["end"] = end
    if machine_id:
        filters.append("dr.machine_id = :machine_id")
        params["machine_id"] = machine_id
    if status:
        filters.append("dr.status = :status")
        params["status"] = status

    where = " AND ".join(filters)
    sql = f"""
        SELECT
            dr.id, dr.defect_date, dr.shift, dr.quantity_defective, dr.quantity_produced,
            dr.severity, dr.status, dr.notes,
            m.code AS machine_code, m.name AS machine_name,
            dc.code AS defect_code, dc.description AS defect_description,
            rc.name AS root_cause,
            ca.description AS corrective_action,
            u.name AS operator_name
        FROM defect_records dr
        LEFT JOIN machines m ON m.id = dr.machine_id
        LEFT JOIN defect_codes dc ON dc.id = dr.defect_code_id
        LEFT JOIN root_causes rc ON rc.id = dr.root_cause_id
        LEFT JOIN corrective_actions ca ON ca.id = dr.corrective_action_id
        LEFT JOIN users u ON u.id = dr.operator_id
        WHERE {where}
        ORDER BY dr.defect_date DESC, dr.created_at DESC
        LIMIT :limit OFFSET :offset
    """
    rows = db.session.execute(text(sql), params).fetchall()
    total = db.session.execute(text(f"SELECT COUNT(*) FROM defect_records dr WHERE {where}"),
                                params).scalar()

    return jsonify({
        "total": total,
        "limit": limit,
        "offset": offset,
        "defects": [dict(r._mapping) for r in rows],
    })


@quality_bp.route('/defects', methods=['POST'])
@token_required
def create_defect(current_user):
    data = request.get_json()
    fid = current_user["factory_id"]

    try:
        row = db.session.execute(text("""
            INSERT INTO defect_records
                (factory_id, machine_id, defect_code_id, root_cause_id, corrective_action_id,
                 operator_id, shift, defect_date, quantity_defective, quantity_produced,
                 severity, status, notes, form_response_id)
            VALUES
                (:fid, :machine_id, :defect_code_id, :root_cause_id, :corrective_action_id,
                 :operator_id, :shift, :defect_date, :qty_def, :qty_prod,
                 :severity, :status, :notes, :form_response_id)
            RETURNING id, created_at
        """), {
            "fid": fid,
            "machine_id": data.get("machine_id"),
            "defect_code_id": data.get("defect_code_id"),
            "root_cause_id": data.get("root_cause_id"),
            "corrective_action_id": data.get("corrective_action_id"),
            "operator_id": data.get("operator_id", current_user["id"]),
            "shift": data.get("shift"),
            "defect_date": data.get("defect_date", str(date.today())),
            "qty_def": data["quantity_defective"],
            "qty_prod": data.get("quantity_produced"),
            "severity": data.get("severity", "medium"),
            "status": data.get("status", "open"),
            "notes": data.get("notes"),
            "form_response_id": data.get("form_response_id"),
        }).fetchone()
        db.session.commit()
        return jsonify({"id": row.id, "created_at": str(row.created_at)}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@quality_bp.route('/defects/<int:defect_id>', methods=['PATCH'])
@token_required
def update_defect(current_user, defect_id):
    data = request.get_json()
    fid = current_user["factory_id"]

    # Get old values for audit trail
    old = db.session.execute(text("""
        SELECT status, severity, notes, root_cause_id, corrective_action_id
        FROM defect_records WHERE id = :id AND factory_id = :fid AND deleted_at IS NULL
    """), {"id": defect_id, "fid": fid}).fetchone()

    if not old:
        return jsonify({"error": "Defect not found"}), 404

    allowed = ["status", "severity", "notes", "root_cause_id", "corrective_action_id"]
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = defect_id
    updates["fid"] = fid
    db.session.execute(text(f"""
        UPDATE defect_records SET {set_clause}, updated_at = NOW()
        WHERE id = :id AND factory_id = :fid
    """), updates)

    # Audit trail
    old_dict = dict(old._mapping)
    new_dict = {k: updates[k] for k in updates if k in allowed}
    db.session.execute(text("""
        INSERT INTO defect_record_history (defect_record_id, user_id, changed_fields, old_values, new_values)
        VALUES (:dr_id, :user_id, :fields, :old_vals, :new_vals)
    """), {
        "dr_id": defect_id,
        "user_id": current_user["id"],
        "fields": json.dumps(list(new_dict.keys())),
        "old_vals": json.dumps(old_dict),
        "new_vals": json.dumps(new_dict),
    })
    db.session.commit()
    return jsonify({"message": "Updated"})


@quality_bp.route('/defects/<int:defect_id>', methods=['DELETE'])
@token_required
def delete_defect(current_user, defect_id):
    db.session.execute(text("""
        UPDATE defect_records SET deleted_at = NOW()
        WHERE id = :id AND factory_id = :fid
    """), {"id": defect_id, "fid": current_user["factory_id"]})
    db.session.commit()
    return jsonify({"message": "Deleted"})


# ── Machines ──────────────────────────────────────────────────────────────────

@quality_bp.route('/machines', methods=['GET'])
@token_required
def get_machines(current_user):
    rows = db.session.execute(text("""
        SELECT id, code, name, location, is_active, created_at
        FROM machines WHERE factory_id = :fid AND deleted_at IS NULL ORDER BY code
    """), {"fid": current_user["factory_id"]}).fetchall()
    return jsonify([dict(r._mapping) for r in rows])


@quality_bp.route('/machines', methods=['POST'])
@token_required
def create_machine(current_user):
    data = request.get_json()
    try:
        row = db.session.execute(text("""
            INSERT INTO machines (code, name, location, factory_id)
            VALUES (:code, :name, :location, :fid) RETURNING id, code, name, created_at
        """), {"code": data["code"], "name": data["name"],
               "location": data.get("location"), "fid": current_user["factory_id"]}).fetchone()
        db.session.commit()
        return jsonify(dict(row._mapping)), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


# ── KPIs (Dashboard Aggregate) ────────────────────────────────────────────────

@quality_bp.route('/kpis', methods=['GET'])
@token_required
def get_kpis(current_user):
    """GET /api/quality/kpis?days=30 — Aggregate KPIs for dashboard."""
    days = int(request.args.get('days', 30))
    fid  = current_user["factory_id"]

    ppm_row = db.session.execute(text("""
        SELECT
            CASE WHEN SUM(quantity_produced) > 0
                 THEN SUM(quantity_defective)::FLOAT / SUM(quantity_produced) * 1000000
                 ELSE 0 END AS ppm,
            SUM(quantity_defective)  AS total_defective,
            SUM(quantity_produced)   AS total_produced,
            COUNT(*)                 AS record_count
        FROM defect_records
        WHERE factory_id = :fid
          AND deleted_at IS NULL
          AND defect_date >= CURRENT_DATE - :days * INTERVAL '1 day'
    """), {"fid": fid, "days": days}).fetchone()

    ppm = float(ppm_row.ppm or 0)
    fpy = round(max(0, 100 - ppm / 10000), 2)

    # Try OEE table, fallback to defaults
    try:
        oee_row = db.session.execute(text("""
            SELECT AVG(COALESCE(availability_pct,88)) AS availability,
                   AVG(COALESCE(performance_pct,93))  AS performance,
                   AVG(COALESCE(quality_pct,99.8))    AS quality_pct
            FROM oee_records
            WHERE factory_id = :fid
              AND record_date >= CURRENT_DATE - :days * INTERVAL '1 day'
        """), {"fid": fid, "days": days}).fetchone()
        avail = float(oee_row.availability or 88)
        perf  = float(oee_row.performance  or 93)
        qual  = float(oee_row.quality_pct  or 99.8)
    except Exception:
        avail, perf, qual = 88.0, 93.0, 99.8

    oee = round(avail * perf * qual / 10000, 2)

    return jsonify({
        "period_days":          days,
        "ppm":                  round(ppm, 2),
        "first_pass_yield_pct": fpy,
        "oee_pct":              oee,
        "availability_pct":     round(avail, 2),
        "performance_pct":      round(perf, 2),
        "quality_pct":          round(qual, 2),
        "total_defective":      int(ppm_row.total_defective or 0),
        "total_produced":       int(ppm_row.total_produced  or 0),
        "record_count":         int(ppm_row.record_count    or 0),
        "copq_usd":             round(float(ppm_row.total_defective or 0) * 50, 2),
    })
