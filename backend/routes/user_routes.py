"""
User Routes Blueprint
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db, bcrypt
from models.user_model import User, AuditLog
from middleware.auth_middleware import require_permission

user_bp = Blueprint('users', __name__)


@user_bp.route('/me', methods=['GET'])
@jwt_required()
def get_me():
    """GET /api/users/me"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict()), 200


@user_bp.route('/me', methods=['PUT'])
@jwt_required()
def update_me():
    """PUT /api/users/me"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Update name
    if 'name' in data:
        name = data['name'].strip()
        if len(name) < 2:
            return jsonify({'error': 'Name must be at least 2 characters'}), 400
        user.name = name

    # Change password
    if 'current_password' in data and 'new_password' in data:
        if not bcrypt.check_password_hash(user.password_hash, data['current_password']):
            return jsonify({'error': 'Current password is incorrect'}), 400
        new_pass = data['new_password']
        if len(new_pass) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        user.password_hash = bcrypt.generate_password_hash(new_pass).decode('utf-8')

    db.session.commit()

    # Log
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    log = AuditLog(user_id=user.id, action='profile_updated', module='users',
                   ip_address=ip, factory_id=user.factory_id)
    db.session.add(log)
    db.session.commit()

    return jsonify(user.to_dict()), 200


@user_bp.route('/', methods=['GET'])
@jwt_required()
@require_permission('users.view')
def list_users():
    """GET /api/users/ — Factory-scoped"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(int(current_user_id))

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = User.query.filter_by(factory_id=current_user.factory_id)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'users': [u.to_dict() for u in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    }), 200


@user_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
@require_permission('users.view')
def get_user(user_id):
    """GET /api/users/<id>"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(int(current_user_id))
    user = User.query.filter_by(id=user_id, factory_id=current_user.factory_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict()), 200


@user_bp.route('/<int:user_id>/toggle-active', methods=['PUT'])
@jwt_required()
@require_permission('users.edit')
def toggle_user_active(user_id):
    """Toggle user active status."""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(int(current_user_id))
    user = User.query.filter_by(id=user_id, factory_id=current_user.factory_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot deactivate yourself'}), 400

    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({'message': f'User {"activated" if user.is_active else "deactivated"}', 'user': user.to_dict()}), 200


@user_bp.route('/me/password', methods=['PUT'])
@jwt_required()
def change_password():
    """PUT /api/users/me/password"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json() or {}
    current_pw = data.get('current_password', '')
    new_pw     = data.get('new_password', '')

    if not bcrypt.check_password_hash(user.password_hash, current_pw):
        return jsonify({'error': 'Current password is incorrect'}), 400
    if len(new_pw) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    user.password_hash  = bcrypt.generate_password_hash(new_pw).decode('utf-8')
    user.login_attempts = 0
    db.session.commit()

    return jsonify({'message': 'Password updated successfully'}), 200
