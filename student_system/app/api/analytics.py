"""
Analytics API Blueprint for student, faculty, and administrator dashboards.
"""

from flask import Blueprint, request
from app.services.analytics_service import AnalyticsService
from app.utils.auth import get_current_user, login_required, roles_required, check_student_scope
from app.utils.exceptions import ForbiddenError, ValidationError
from app.utils.responses import api_response

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/v1/analytics")


@analytics_bp.route("/student/<int:student_id>", methods=["GET"])
@login_required
def get_student_analytics(student_id: int):
    """
    Get student analytics including subject marks, trends, comparison, and attendance.
    Enforces IDOR check: Students can only view their own data.
    """
    check_student_scope(student_id)
    analytics = AnalyticsService.get_student_analytics(student_id)
    return api_response(data=analytics, message="Student analytics generated successfully.")


@analytics_bp.route("/student/me", methods=["GET"])
@login_required
def get_own_student_analytics():
    """Convenience endpoint for logged-in students to fetch their own analytics."""
    user = get_current_user()
    if user["role"] != "Student" or not user.get("student_id"):
        raise ForbiddenError("This endpoint is intended for student user accounts.")

    analytics = AnalyticsService.get_student_analytics(user["student_id"])
    return api_response(data=analytics, message="Personal student analytics generated successfully.")


@analytics_bp.route("/faculty", methods=["GET"])
@roles_required("Faculty", "Admin")
def get_faculty_analytics():
    """Get aggregated analytics strictly within the faculty member's assigned courses."""
    user = get_current_user()
    if user["role"] == "Faculty":
        faculty_id = user.get("faculty_id")
        if not faculty_id:
            raise ForbiddenError("Faculty profile not associated with this user account.")
    else:
        # Admin can inspect any faculty member by ?faculty_id=...
        f_id = request.args.get("faculty_id")
        if not f_id or not f_id.isdigit():
            raise ValidationError("Query parameter 'faculty_id' is required for administrators.")
        faculty_id = int(f_id)

    analytics = AnalyticsService.get_faculty_analytics(faculty_id)
    return api_response(data=analytics, message="Faculty course analytics generated successfully.")


@analytics_bp.route("/overview", methods=["GET"])
@roles_required("Admin")
def get_admin_overview_analytics():
    """Get institution-wide KPIs, grade distributions, and department metrics (Admin only)."""
    analytics = AnalyticsService.get_admin_analytics()
    return api_response(data=analytics, message="Administrative overview analytics generated successfully.")
