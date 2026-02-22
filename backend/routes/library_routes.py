"""
Quality Library Routes
Manages standards, defect categories, codes, root causes, corrective actions
"""
from flask import Blueprint, request, jsonify
from middleware.auth_middleware import token_required
from models import db
from sqlalchemy import text

library_bp = Blueprint('library', __name__)


def _factory_id(current_user):
    return current_user["factory_id"]


# ── Quality Standards ──────────────────────────────────────────────────────────

@library_bp.route('/standards', methods=['GET'])
@token_required
def get_standards(current_user):
    fid = _factory_id(current_user)
    rows = db.session.execute(text("""
        SELECT id, name, description, is_active, created_at
        FROM quality_standards
        WHERE (factory_id = :fid OR factory_id IS NULL) AND deleted_at IS NULL
        ORDER BY name
    """), {"fid": fid}).fetchall()
    return jsonify([dict(r._mapping) for r in rows])


@library_bp.route('/standards', methods=['POST'])
@token_required
def create_standard(current_user):
    data = request.get_json()
    row = db.session.execute(text("""
        INSERT INTO quality_standards (name, description, factory_id)
        VALUES (:name, :desc, :fid) RETURNING id, name, description, created_at
    """), {"name": data["name"], "desc": data.get("description"), "fid": _factory_id(current_user)}).fetchone()
    db.session.commit()
    return jsonify(dict(row._mapping)), 201


# ── Defect Categories ─────────────────────────────────────────────────────────

@library_bp.route('/categories', methods=['GET'])
@token_required
def get_categories(current_user):
    fid = _factory_id(current_user)
    rows = db.session.execute(text("""
        SELECT id, name, severity_level, is_active, created_at
        FROM defect_categories
        WHERE factory_id = :fid AND deleted_at IS NULL
        ORDER BY severity_level, name
    """), {"fid": fid}).fetchall()
    return jsonify([dict(r._mapping) for r in rows])


@library_bp.route('/categories', methods=['POST'])
@token_required
def create_category(current_user):
    data = request.get_json()
    row = db.session.execute(text("""
        INSERT INTO defect_categories (name, severity_level, factory_id)
        VALUES (:name, :sev, :fid) RETURNING id, name, severity_level, created_at
    """), {"name": data["name"], "sev": data.get("severity_level", "medium"),
           "fid": _factory_id(current_user)}).fetchone()
    db.session.commit()
    return jsonify(dict(row._mapping)), 201


@library_bp.route('/categories/<int:cat_id>', methods=['DELETE'])
@token_required
def delete_category(current_user, cat_id):
    db.session.execute(text("""
        UPDATE defect_categories SET deleted_at = NOW()
        WHERE id = :id AND factory_id = :fid
    """), {"id": cat_id, "fid": _factory_id(current_user)})
    db.session.commit()
    return jsonify({"message": "Category deleted"}), 200


# ── Defect Codes ──────────────────────────────────────────────────────────────

@library_bp.route('/codes', methods=['GET'])
@token_required
def get_codes(current_user):
    fid = _factory_id(current_user)
    rows = db.session.execute(text("""
        SELECT dc.id, dc.code, dc.description, dc.is_active,
               cat.name AS category_name, cat.severity_level, dc.created_at
        FROM defect_codes dc
        LEFT JOIN defect_categories cat ON cat.id = dc.category_id
        WHERE dc.factory_id = :fid AND dc.deleted_at IS NULL
        ORDER BY dc.code
    """), {"fid": fid}).fetchall()
    return jsonify([dict(r._mapping) for r in rows])


@library_bp.route('/codes', methods=['POST'])
@token_required
def create_code(current_user):
    data = request.get_json()
    try:
        row = db.session.execute(text("""
            INSERT INTO defect_codes (code, description, category_id, factory_id)
            VALUES (:code, :desc, :cat_id, :fid) RETURNING id, code, description, created_at
        """), {"code": data["code"], "desc": data.get("description"),
               "cat_id": data.get("category_id"), "fid": _factory_id(current_user)}).fetchone()
        db.session.commit()
        return jsonify(dict(row._mapping)), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


# ── Root Causes ───────────────────────────────────────────────────────────────

@library_bp.route('/root-causes', methods=['GET'])
@token_required
def get_root_causes(current_user):
    rows = db.session.execute(text("""
        SELECT id, name, description, created_at
        FROM root_causes
        WHERE factory_id = :fid AND deleted_at IS NULL
        ORDER BY name
    """), {"fid": _factory_id(current_user)}).fetchall()
    return jsonify([dict(r._mapping) for r in rows])


@library_bp.route('/root-causes', methods=['POST'])
@token_required
def create_root_cause(current_user):
    data = request.get_json()
    row = db.session.execute(text("""
        INSERT INTO root_causes (name, description, factory_id)
        VALUES (:name, :desc, :fid) RETURNING id, name, description, created_at
    """), {"name": data["name"], "desc": data.get("description"),
           "fid": _factory_id(current_user)}).fetchone()
    db.session.commit()
    return jsonify(dict(row._mapping)), 201


# ── Corrective Actions ────────────────────────────────────────────────────────

@library_bp.route('/corrective-actions', methods=['GET'])
@token_required
def get_corrective_actions(current_user):
    rows = db.session.execute(text("""
        SELECT ca.id, ca.description, ca.effectiveness_rating,
               rc.name AS root_cause_name, ca.created_at
        FROM corrective_actions ca
        LEFT JOIN root_causes rc ON rc.id = ca.root_cause_id
        WHERE ca.factory_id = :fid AND ca.deleted_at IS NULL
        ORDER BY ca.effectiveness_rating DESC NULLS LAST
    """), {"fid": _factory_id(current_user)}).fetchall()
    return jsonify([dict(r._mapping) for r in rows])


@library_bp.route('/corrective-actions', methods=['POST'])
@token_required
def create_corrective_action(current_user):
    data = request.get_json()
    row = db.session.execute(text("""
        INSERT INTO corrective_actions (description, root_cause_id, effectiveness_rating, factory_id)
        VALUES (:desc, :rc_id, :rating, :fid) RETURNING id, description, created_at
    """), {"desc": data["description"], "rc_id": data.get("root_cause_id"),
           "rating": data.get("effectiveness_rating"), "fid": _factory_id(current_user)}).fetchone()
    db.session.commit()
    return jsonify(dict(row._mapping)), 201
