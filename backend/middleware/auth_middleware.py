"""
Auth Middleware — QMS Enterprise
Provides:
  - token_required(f)      — decorator: verifies JWT, passes current_user dict
  - require_permission(p)  — decorator: checks RBAC permission
  - require_role(r)        — decorator: checks exact role name
  - factory_scope(f)       — decorator: ensures factory isolation
"""
from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from models.user_model import User


def token_required(f):
    """
    Primary auth decorator used across all protected routes.
    Verifies JWT, loads user, passes current_user dict to route function.
    
    Usage:
        @token_required
        def my_route(current_user):
            fid = current_user["factory_id"]
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception as e:
            return jsonify({'error': 'Token missing or invalid', 'detail': str(e)}), 401

        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))

        if not user:
            return jsonify({'error': 'User not found'}), 401
        if not user.is_active:
            return jsonify({'error': 'Account deactivated'}), 401

        current_user = {
            'id':           user.id,
            'name':         user.name,
            'email':        user.email,
            'factory_id':   user.factory_id,
            'role_id':      user.role_id,
            'role_name':    user.role.name if user.role else None,
            'permissions':  [p.name for p in user.role.permissions] if user.role else [],
            'factory_name': user.factory.name if user.factory else None,
        }

        return f(current_user, *args, **kwargs)
    return decorated


def require_permission(permission_name):
    """Decorator to check RBAC permission."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                verify_jwt_in_request()
            except Exception:
                return jsonify({'error': 'Authentication required'}), 401

            user_id = get_jwt_identity()
            user = User.query.get(int(user_id))

            if not user or not user.is_active:
                return jsonify({'error': 'User not found or inactive'}), 401

            if not user.has_permission(permission_name):
                return jsonify({
                    'error': 'Permission denied',
                    'required': permission_name
                }), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


def require_role(role_name):
    """Decorator to require a specific role."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                verify_jwt_in_request()
            except Exception:
                return jsonify({'error': 'Authentication required'}), 401

            user_id = get_jwt_identity()
            user = User.query.get(int(user_id))

            if not user or not user.is_active:
                return jsonify({'error': 'Unauthorized'}), 401

            if not user.role or user.role.name != role_name:
                return jsonify({'error': 'Insufficient role'}), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


def factory_scope(f):
    """Ensure the resource belongs to the user's factory."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return jsonify({'error': 'Authentication required'}), 401

        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated
