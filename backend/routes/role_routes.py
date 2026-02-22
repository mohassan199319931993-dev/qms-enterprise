"""
Role Routes Blueprint
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db
from models.user_model import User, AuditLog
from models.role_model import Role, Permission
from middleware.auth_middleware import require_permission

role_bp = Blueprint('roles', __name__)


@role_bp.route('/', methods=['GET'])
@jwt_required()
def list_roles():
    """GET /api/roles/ — Factory-scoped"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(int(current_user_id))
    roles = Role.query.filter_by(factory_id=current_user.factory_id).all()
    return jsonify([r.to_dict(include_permissions=True) for r in roles]), 200


@role_bp.route('/', methods=['POST'])
@jwt_required()
@require_permission('roles.create')
def create_role():
    """POST /api/roles/"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(int(current_user_id))
    data = request.get_json()

    if not data or not data.get('name'):
        return jsonify({'error': 'Role name is required'}), 400

    # Check uniqueness within factory
    existing = Role.query.filter_by(name=data['name'], factory_id=current_user.factory_id).first()
    if existing:
        return jsonify({'error': 'Role name already exists in this factory'}), 400

    role = Role(
        name=data['name'].strip(),
        description=data.get('description', ''),
        factory_id=current_user.factory_id
    )

    # Assign permissions
    if 'permission_ids' in data:
        perms = Permission.query.filter(Permission.id.in_(data['permission_ids'])).all()
        role.permissions = perms

    db.session.add(role)
    db.session.commit()

    # Log
    log = AuditLog(user_id=current_user.id, action='role_created', module='roles',
                   details={'role_name': role.name}, factory_id=current_user.factory_id)
    db.session.add(log)
    db.session.commit()

    return jsonify(role.to_dict(include_permissions=True)), 201


@role_bp.route('/<int:role_id>', methods=['PUT'])
@jwt_required()
@require_permission('roles.edit')
def update_role(role_id):
    """PUT /api/roles/<id>"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(int(current_user_id))
    role = Role.query.filter_by(id=role_id, factory_id=current_user.factory_id).first()

    if not role:
        return jsonify({'error': 'Role not found'}), 404
    if role.is_system_role:
        return jsonify({'error': 'Cannot modify system roles'}), 403

    data = request.get_json()
    if 'name' in data:
        role.name = data['name'].strip()
    if 'description' in data:
        role.description = data['description']
    if 'permission_ids' in data:
        perms = Permission.query.filter(Permission.id.in_(data['permission_ids'])).all()
        role.permissions = perms

    db.session.commit()
    return jsonify(role.to_dict(include_permissions=True)), 200


@role_bp.route('/<int:role_id>', methods=['DELETE'])
@jwt_required()
@require_permission('roles.delete')
def delete_role(role_id):
    """DELETE /api/roles/<id>"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(int(current_user_id))
    role = Role.query.filter_by(id=role_id, factory_id=current_user.factory_id).first()

    if not role:
        return jsonify({'error': 'Role not found'}), 404
    if role.is_system_role:
        return jsonify({'error': 'Cannot delete system roles'}), 403
    if role.users.count() > 0:
        return jsonify({'error': 'Cannot delete role with assigned users'}), 400

    db.session.delete(role)
    db.session.commit()
    return jsonify({'message': 'Role deleted successfully'}), 200


@role_bp.route('/permissions', methods=['GET'])
@jwt_required()
def list_permissions():
    """GET /api/roles/permissions — All available permissions"""
    permissions = Permission.query.all()
    # Group by module
    modules = {}
    for p in permissions:
        if p.module not in modules:
            modules[p.module] = []
        modules[p.module].append(p.to_dict())
    return jsonify({'permissions': permissions, 'by_module': modules}), 200
