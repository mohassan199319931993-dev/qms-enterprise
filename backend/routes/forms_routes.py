"""
Dynamic Form Routes
POST /api/forms, GET /api/forms, POST /api/forms/<id>/submit, GET /api/forms/<id>/responses
"""
from flask import Blueprint, request, jsonify
from middleware.auth_middleware import token_required
from services.form_service import FormService

forms_bp = Blueprint('forms', __name__)


@forms_bp.route('', methods=['GET'])
@token_required
def get_forms(current_user):
    module = request.args.get('module')
    forms = FormService.get_forms(current_user["factory_id"], module)
    return jsonify(forms)


@forms_bp.route('', methods=['POST'])
@token_required
def create_form(current_user):
    data = request.get_json()
    if not data.get("name"):
        return jsonify({"error": "Form name is required"}), 400
    try:
        form = FormService.create_form(
            current_user["factory_id"], current_user["id"], data
        )
        return jsonify(form), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@forms_bp.route('/<int:form_id>', methods=['GET'])
@token_required
def get_form(current_user, form_id):
    form = FormService.get_form(form_id, current_user["factory_id"])
    if not form:
        return jsonify({"error": "Form not found"}), 404
    return jsonify(form)


@forms_bp.route('/<int:form_id>', methods=['DELETE'])
@token_required
def delete_form(current_user, form_id):
    ok = FormService.delete_form(form_id, current_user["factory_id"])
    if not ok:
        return jsonify({"error": "Form not found"}), 404
    return jsonify({"message": "Form deleted"})


@forms_bp.route('/<int:form_id>/submit', methods=['POST'])
@token_required
def submit_form(current_user, form_id):
    data = request.get_json()
    try:
        response = FormService.submit_response(
            form_id, current_user["factory_id"], current_user["id"], data
        )
        return jsonify(response), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Submission failed", "details": str(e)}), 500


@forms_bp.route('/<int:form_id>/responses', methods=['GET'])
@token_required
def get_responses(current_user, form_id):
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    result = FormService.get_responses(
        form_id, current_user["factory_id"], limit, offset
    )
    return jsonify(result)
