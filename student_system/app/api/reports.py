"""
Reports API blueprint using standard Flask routes.
"""

from flask import Blueprint, request
from app.services.report_service import ReportService
from app.utils.responses import api_response

reports_bp = Blueprint("reports", __name__, url_prefix="/api/v1/reports")


@reports_bp.route("/students/<int:student_id>/transcript", methods=["GET"])
def get_transcript(student_id: int):
    """Generate comprehensive student transcript including semester GPAs, CGPA, and attendance."""
    transcript = ReportService.get_student_transcript(student_id)
    return api_response(data=transcript, message="Student academic transcript generated successfully")


@reports_bp.route("/attendance/low", methods=["GET"])
def get_low_attendance():
    """Identify students whose overall attendance is below threshold (default 75%)."""
    threshold_raw = request.args.get("threshold", 75.0)
    try:
        threshold = float(threshold_raw)
    except (ValueError, TypeError):
        threshold = 75.0

    at_risk = ReportService.get_low_attendance_report(threshold=threshold)
    return api_response(
        data=at_risk,
        message=f"Found {len(at_risk)} student(s) with attendance below {threshold}%",
        meta={"threshold": threshold, "count": len(at_risk)},
    )
