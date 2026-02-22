"""
Factory Routes Blueprint
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db
from models.user_model import User
from models.factory_model import Factory

factory_bp = Blueprint('factories', __name__)


@factory_bp.route('/', methods=['GET'])
@jwt_required()
def list_factories():
    """GET /api/factories/ — Super admin only in production"""
    factories = Factory.query.filter_by(is_active=True).all()
    return jsonify([f.to_dict() for f in factories]), 200


@factory_bp.route('/mine', methods=['GET'])
@jwt_required()
def get_my_factory():
    """GET /api/factories/mine"""
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    if not user or not user.factory:
        return jsonify({'error': 'Factory not found'}), 404
    return jsonify(user.factory.to_dict()), 200


@factory_bp.route('/', methods=['POST'])
@jwt_required()
def create_factory():
    """POST /api/factories/ — Public: creates factory (use admin-register instead)"""
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Factory name is required'}), 400

    factory = Factory(
        name=data['name'].strip(),
        location=data.get('location', ''),
        subscription_plan=data.get('subscription_plan', 'basic')
    )
    db.session.add(factory)
    db.session.commit()
    return jsonify(factory.to_dict()), 201
