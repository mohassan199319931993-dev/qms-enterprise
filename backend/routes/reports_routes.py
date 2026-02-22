"""
Reports Routes
GET /api/reports/daily, /monthly, /supplier, /export
"""
from datetime import date
from flask import Blueprint, request, jsonify, send_file
from middleware.auth_middleware import token_required
from services.report_service import ReportService
from io import BytesIO

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/daily', methods=['GET'])
@token_required
def daily_report(current_user):
    date_str = request.args.get('date')
    report_date = date.fromisoformat(date_str) if date_str else date.today()
    data = ReportService.get_daily_report(current_user["factory_id"], report_date)
    return jsonify(data)


@reports_bp.route('/monthly', methods=['GET'])
@token_required
def monthly_report(current_user):
    now = date.today()
    year = int(request.args.get('year', now.year))
    month = int(request.args.get('month', now.month))
    data = ReportService.get_monthly_report(current_user["factory_id"], year, month)
    return jsonify(data)


@reports_bp.route('/supplier', methods=['GET'])
@token_required
def supplier_report(current_user):
    start = request.args.get('start_date')
    end = request.args.get('end_date')
    data = ReportService.get_supplier_quality(
        current_user["factory_id"],
        date.fromisoformat(start) if start else None,
        date.fromisoformat(end) if end else None,
    )
    return jsonify(data)


@reports_bp.route('/export', methods=['GET'])
@token_required
def export_report(current_user):
    report_type = request.args.get('type', 'daily')
    fmt = request.args.get('format', 'excel')

    if fmt == 'excel':
        try:
            data = ReportService.generate_excel_report(
                current_user["factory_id"], report_type)
            return send_file(
                BytesIO(data),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f"qms_report_{report_type}_{date.today()}.xlsx"
            )
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 400
    else:
        return jsonify({"error": "Unsupported format. Use format=excel"}), 400
