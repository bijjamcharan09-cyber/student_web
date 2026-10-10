"""
Semesters API blueprint using standard Flask routes.
"""

from flask import Blueprint, request
from app.services.semester_service import SemesterService
from app.utils.auth import roles_required
from app.utils.responses import api_response

semesters_bp = Blueprint("semesters", __name__, url_prefix="/api/v1/semesters")


@semesters_bp.route("", methods=["GET"])
def list_semesters():
    """List all semesters, optionally filtered by academic year, active status, and sorting."""
    academic_year = request.args.get("academic_year", "").strip() or None
    is_active_raw = request.args.get("is_active")
    is_active = (
        True if is_active_raw in ("true", "True", "1")
        else False if is_active_raw in ("false", "False", "0")
        else None
    )
    sort_by = request.args.get("sort_by", "").strip().lower() or None
    order = request.args.get("order", "").strip().lower() or None

    items = SemesterService.list_semesters(
        academic_year=academic_year,
        is_active=is_active,
        sort_by=sort_by,
        order=order,
    )
    return api_response(data=items, message="Semesters retrieved successfully")


@semesters_bp.route("", methods=["POST"])
def create_semester():
    """Create a new semester."""
    payload = request.get_json(silent=True) or {}
    semester = SemesterService.create_semester(payload)
    return api_response(data=semester, message="Semester created successfully", status_code=201)


@semesters_bp.route("/<int:semester_id>", methods=["GET"])
def get_semester(semester_id: int):
    """Get semester details by ID."""
    semester = SemesterService.get_semester(semester_id)
    return api_response(data=semester, message="Semester retrieved successfully")


@semesters_bp.route("/<int:semester_id>", methods=["PUT", "PATCH"])
@roles_required("Admin")
def update_semester(semester_id: int):
    """Update semester details (Admin only)."""
    payload = request.get_json(silent=True) or {}
    updated = SemesterService.update_semester(semester_id, payload)
    return api_response(data=updated, message="Semester updated successfully")


@semesters_bp.route("/<int:semester_id>/activate", methods=["POST"])
def activate_semester(semester_id: int):
    """Set a semester as currently active."""
    updated = SemesterService.set_active(semester_id)
    return api_response(data=updated, message="Semester activated successfully")


@semesters_bp.route("/<int:semester_id>", methods=["DELETE"])
@roles_required("Admin")
def delete_semester(semester_id: int):
    """Delete a semester (Admin only)."""
    SemesterService.delete_semester(semester_id)
    return api_response(data={"deleted_id": semester_id}, message="Semester deleted successfully")
