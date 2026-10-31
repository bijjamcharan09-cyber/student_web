"""
Semesters API blueprint with authentication, role checks, and organisation scoping.
"""

from flask import Blueprint, request
from app.services.semester_service import SemesterService
from app.utils.auth import (
    check_organisation_scope,
    get_effective_organisation_id,
    login_required,
    roles_required,
)
from app.utils.responses import api_response

semesters_bp = Blueprint("semesters", __name__, url_prefix="/api/v1/semesters")


@semesters_bp.route("", methods=["GET"])
def list_semesters():
    """List all semesters, optionally filtered by academic year, active status, and sorting. Public for catalog."""
    org_id = get_effective_organisation_id()
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
        organisation_id=org_id,
        sort_by=sort_by,
        order=order,
    )
    return api_response(data=items, message="Semesters retrieved successfully")


@semesters_bp.route("", methods=["POST"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def create_semester():
    """Create a new semester within the caller's organisation."""
    payload = request.get_json(silent=True) or {}
    org_id = get_effective_organisation_id()
    if org_id is not None:
        payload["organisation_id"] = org_id

    semester = SemesterService.create_semester(payload)
    return api_response(data=semester, message="Semester created successfully", status_code=201)


@semesters_bp.route("/<int:semester_id>", methods=["GET"])
def get_semester(semester_id: int):
    """Get semester details by ID."""
    semester = SemesterService.get_semester(semester_id)
    return api_response(data=semester, message="Semester retrieved successfully")


@semesters_bp.route("/<int:semester_id>", methods=["PUT", "PATCH"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def update_semester(semester_id: int):
    """Update semester details (Admin and Organisation managers only)."""
    semester = SemesterService.get_semester(semester_id)
    check_organisation_scope(semester.get("organisation_id"))

    payload = request.get_json(silent=True) or {}
    updated = SemesterService.update_semester(semester_id, payload)
    return api_response(data=updated, message="Semester updated successfully")


@semesters_bp.route("/<int:semester_id>/activate", methods=["POST"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def activate_semester(semester_id: int):
    """Set a semester as currently active within caller's organisation."""
    semester = SemesterService.get_semester(semester_id)
    check_organisation_scope(semester.get("organisation_id"))

    updated = SemesterService.set_active(semester_id)
    return api_response(data=updated, message="Semester activated successfully")


@semesters_bp.route("/<int:semester_id>", methods=["DELETE"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def delete_semester(semester_id: int):
    """Delete a semester (Admin and Organisation managers only)."""
    semester = SemesterService.get_semester(semester_id)
    check_organisation_scope(semester.get("organisation_id"))

    SemesterService.delete_semester(semester_id)
    return api_response(data={"deleted_id": semester_id}, message="Semester deleted successfully")
