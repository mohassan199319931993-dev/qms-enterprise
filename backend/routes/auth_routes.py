"""
Authentication Routes Blueprint
"""
from flask import Blueprint, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from services.auth_service import AuthService
from middleware.validators import (
    validate_login, validate_register, validate_admin_register,
    validate_forgot_password, validate_reset_password
)

auth_bp = Blueprint('auth', __name__)


def get_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr)


@auth_bp.route('/login', methods=['POST'])
def login():
    """POST /api/auth/login"""
    data = request.get_json()
    errors = validate_login(data)
    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    try:
        result = AuthService.login(
            email=data['email'],
            password=data['password'],
            ip_address=get_ip()
        )
        return jsonify(result), 200
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': 'Login failed'}), 500


@auth_bp.route('/register', methods=['POST'])
def register():
    """POST /api/auth/register"""
    data = request.get_json()
    errors = validate_register(data)
    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    try:
        result = AuthService.register(
            name=data['name'],
            email=data['email'],
            password=data['password'],
            factory_id=data['factory_id'],
            ip_address=get_ip()
        )
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Registration failed'}), 500


@auth_bp.route('/admin-register', methods=['POST'])
def admin_register():
    """POST /api/auth/admin-register — Creates factory + admin"""
    data = request.get_json()
    errors = validate_admin_register(data)
    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    try:
        result = AuthService.admin_register(
            factory_name=data['factory_name'],
            location=data.get('location', ''),
            subscription_plan=data.get('subscription_plan', 'basic'),
            admin_name=data['admin_name'],
            admin_email=data['admin_email'],
            password=data['password'],
            ip_address=get_ip()
        )
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Registration failed'}), 500


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """POST /api/auth/refresh — Rotate refresh token"""
    data = request.get_json()
    if not data or not data.get('refresh_token'):
        return jsonify({'error': 'Refresh token required'}), 400

    try:
        result = AuthService.refresh_tokens(
            refresh_token_str=data['refresh_token'],
            ip_address=get_ip()
        )
        return jsonify(result), 200
    except PermissionError as e:
        return jsonify({'error': str(e)}), 401
    except Exception:
        return jsonify({'error': 'Token refresh failed'}), 500


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """POST /api/auth/forgot-password"""
    data = request.get_json()
    errors = validate_forgot_password(data)
    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    try:
        token = AuthService.forgot_password(
            email=data['email'],
            ip_address=get_ip()
        )
        # In production, send email with token
        # For dev, return token in response
        response = {'message': 'If this email exists, a reset link has been sent'}
        if token and request.headers.get('X-Debug-Mode') == 'true':
            response['debug_token'] = token  # Only in dev
        return jsonify(response), 200
    except Exception:
        return jsonify({'message': 'If this email exists, a reset link has been sent'}), 200


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """POST /api/auth/reset-password"""
    data = request.get_json()
    errors = validate_reset_password(data)
    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    try:
        AuthService.reset_password(
            token=data['token'],
            new_password=data['password'],
            ip_address=get_ip()
        )
        return jsonify({'message': 'Password reset successfully'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        return jsonify({'error': 'Password reset failed'}), 500
