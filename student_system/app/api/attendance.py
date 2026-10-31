"""
Attendance API blueprint with strict authentication, RBAC, organisation scoping, and IDOR protection.
"""

from flask import Blueprint, request
from app.repositories.faculty_repo import FacultyRepository
from app.services.attendance_service import AttendanceService
from app.utils.auth import (
    check_organisation_scope,
    check_student_scope,
    check_subject_management_scope,
    get_current_user,
    get_effective_organisation_id,
    login_required,
    roles_required,
)
from app.utils.exceptions import ForbiddenError, NotFoundError
from app.utils.responses import api_response
from app.utils.validators import parse_pagination

attendance_bp = Blueprint("attendance", __name__, url_prefix="/api/v1/attendance")


@attendance_bp.route("", methods=["GET"])
@login_required
def list_attendance():
    """List attendance records with filters, sorting, and multi-organisation scoping."""
    user = get_current_user()
    role = str(user.get("role") or "").strip().title()

    def parse_int_param(param_name):
        val = request.args.get(param_name)
        return int(val) if val and val.isdigit() else None

    student_id = parse_int_param("student_id")
    # Enforce IDOR protection: Students can only view their own attendance
    if role == "Student":
        student_id = user.get("student_id")

    subject_id = parse_int_param("subject_id")
    date_from = request.args.get("date_from", "").strip() or None
    date_to = request.args.get("date_to", "").strip() or None
    status = request.args.get("status", "").strip().capitalize() or None
    sort_by = request.args.get("sort_by", "").strip().lower() or None
    order = request.args.get("order", "").strip().lower() or None

    org_id = get_effective_organisation_id()
    page, per_page = parse_pagination(request.args.get("page"), request.args.get("per_page"))

    result = AttendanceService.list_attendance(
        student_id=student_id,
        subject_id=subject_id,
        date_from=date_from,
        date_to=date_to,
        status=status,
        organisation_id=org_id,
        sort_by=sort_by,
        order=order,
        page=page,
        per_page=per_page,
    )
    return api_response(
        data=result["items"],
        message="Attendance records retrieved successfully",
        meta=result["pagination"],
    )


@attendance_bp.route("", methods=["POST"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation", "Faculty")
def record_attendance():
    """Record an individual attendance entry (Admin, Organisation, or assigned Faculty only)."""
    user = get_current_user()
    role = str(user.get("role") or "").strip().title()
    payload = request.get_json(silent=True) or {}

    if role == "Faculty":
        check_subject_management_scope(payload.get("subject_id"))
    elif role in ("Organisation", "Organization"):
        check_organisation_scope(user.get("organisation_id"))
        payload["organisation_id"] = user.get("organisation_id")

    record = AttendanceService.record_attendance(payload)
    return api_response(data=record, message="Attendance recorded successfully", status_code=201)


@attendance_bp.route("/batch", methods=["POST"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation", "Faculty")
def batch_record_attendance():
    """Record multiple attendance entries in an atomic transaction."""
    user = get_current_user()
    role = str(user.get("role") or "").strip().title()
    payload = request.get_json(silent=True)
    if isinstance(payload, dict) and "records" in payload:
        records = payload["records"]
    elif isinstance(payload, list):
        records = payload
    else:
        from app.utils.exceptions import ValidationError
        raise ValidationError("Request body must be a list of attendance items or {'records': [...]}.")

    if role == "Faculty":
        for item in records:
            check_subject_management_scope(item.get("subject_id"))

    expected_org_id = None
    if role in ("Organisation", "Organization"):
        expected_org_id = user.get("organisation_id")

    inserted = AttendanceService.batch_record_attendance(records, expected_org_id=expected_org_id)
    return api_response(
        data=inserted,
        message=f"Successfully recorded {len(inserted)} attendance items in transaction",
        status_code=201,
    )


@attendance_bp.route("/<int:attendance_id>", methods=["GET"])
@login_required
def get_attendance(attendance_id: int):
    """Get single attendance record with organisation and student scoping."""
    record = AttendanceService.get_attendance(attendance_id)
    check_organisation_scope(record.get("organisation_id"))

    user = get_current_user()
    if user["role"] == "Student":
        check_student_scope(record["student_id"])

    return api_response(data=record, message="Attendance record retrieved successfully")


@attendance_bp.route("/<int:attendance_id>", methods=["PUT", "PATCH"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation", "Faculty")
def update_attendance(attendance_id: int):
    """Update attendance record (Admin, Organisation, or assigned Faculty only)."""
    user = get_current_user()
    role = str(user.get("role") or "").strip().title()

    existing = AttendanceService.get_attendance(attendance_id)
    check_organisation_scope(existing.get("organisation_id"))

    if role == "Faculty":
        faculty_id = user.get("faculty_id")
        if not faculty_id or not FacultyRepository.is_faculty_assigned_to_subject(faculty_id, existing["subject_id"]):
            raise ForbiddenError("You are not authorized to modify attendance for this course.")

    payload = request.get_json(silent=True) or {}
    updated = AttendanceService.update_attendance(attendance_id, payload)
    return api_response(data=updated, message="Attendance record updated successfully")


@attendance_bp.route("/<int:attendance_id>", methods=["DELETE"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def delete_attendance(attendance_id: int):
    """Delete attendance record (Admin and Organisation managers only)."""
    existing = AttendanceService.get_attendance(attendance_id)
    check_organisation_scope(existing.get("organisation_id"))
    AttendanceService.delete_attendance(attendance_id)
    return api_response(data={"deleted_id": attendance_id}, message="Attendance record deleted successfully")


@attendance_bp.route("/student/<int:student_id>/summary", methods=["GET"])
@login_required
def get_student_attendance_summary(student_id: int):
    """Get attendance statistics and percentage for a student with IDOR and organisation verification."""
    check_student_scope(student_id)
    sub_id_raw = request.args.get("subject_id")
    subject_id = int(sub_id_raw) if sub_id_raw and sub_id_raw.isdigit() else None

    summary = AttendanceService.get_student_summary(student_id, subject_id=subject_id)
    return api_response(data=summary, message="Student attendance summary generated successfully")
