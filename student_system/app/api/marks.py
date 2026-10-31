"""
Marks and grades API blueprint with strict authentication, RBAC, organisation scoping, and IDOR protection.
"""

from flask import Blueprint, request
from app.repositories.faculty_repo import FacultyRepository
from app.repositories.mark_repo import MarkRepository
from app.services.mark_service import MarkService
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

marks_bp = Blueprint("marks", __name__, url_prefix="/api/v1/marks")


@marks_bp.route("", methods=["GET"])
@login_required
def list_marks():
    """List marks filtered by student, subject, semester, or exam type with sorting and organisation scoping."""
    user = get_current_user()
    role = str(user.get("role") or "").strip().title()

    def parse_int_param(param_name):
        val = request.args.get(param_name)
        return int(val) if val and val.isdigit() else None

    student_id = parse_int_param("student_id")
    subject_id = parse_int_param("subject_id")
    semester_id = parse_int_param("semester_id")
    exam_type = request.args.get("exam_type", "").strip().capitalize() or None
    sort_by = request.args.get("sort_by", "").strip().lower() or None
    order = request.args.get("order", "").strip().lower() or None

    # Enforce IDOR protection: Students can ONLY query their own marks
    if role == "Student":
        student_id = user.get("student_id")

    org_id = get_effective_organisation_id()
    page, per_page = parse_pagination(request.args.get("page"), request.args.get("per_page"))

    result = MarkService.list_marks(
        student_id=student_id,
        subject_id=subject_id,
        semester_id=semester_id,
        exam_type=exam_type,
        organisation_id=org_id,
        sort_by=sort_by,
        order=order,
        page=page,
        per_page=per_page,
    )
    return api_response(
        data=result["items"],
        message="Marks retrieved successfully",
        meta=result["pagination"],
    )


@marks_bp.route("", methods=["POST"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation", "Faculty")
def record_mark():
    """Record an individual student mark (Admin, Organisation, or assigned Faculty only)."""
    user = get_current_user()
    role = str(user.get("role") or "").strip().title()
    payload = request.get_json(silent=True) or {}

    # Verify faculty assignment
    if role == "Faculty":
        check_subject_management_scope(payload.get("subject_id"), payload.get("semester_id"))
    elif role in ("Organisation", "Organization"):
        check_organisation_scope(user.get("organisation_id"))
        payload["organisation_id"] = user.get("organisation_id")

    record = MarkService.record_mark(payload)
    return api_response(data=record, message="Mark recorded successfully", status_code=201)


@marks_bp.route("/batch", methods=["POST"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation", "Faculty")
def batch_record_marks():
    """Record multiple marks in an atomic transaction."""
    user = get_current_user()
    role = str(user.get("role") or "").strip().title()
    payload = request.get_json(silent=True)
    if isinstance(payload, dict) and "records" in payload:
        records = payload["records"]
    elif isinstance(payload, list):
        records = payload
    else:
        from app.utils.exceptions import ValidationError
        raise ValidationError("Request body must be a list of marks or {'records': [...]}.")

    # For faculty, verify subject management scope for each record
    if role == "Faculty":
        for item in records:
            check_subject_management_scope(item.get("subject_id"), item.get("semester_id"))

    expected_org_id = None
    if role in ("Organisation", "Organization"):
        expected_org_id = user.get("organisation_id")

    inserted = MarkService.batch_record_marks(records, expected_org_id=expected_org_id)
    return api_response(
        data=inserted,
        message=f"Successfully recorded {len(inserted)} marks in transaction",
        status_code=201,
    )


@marks_bp.route("/<int:mark_id>", methods=["GET"])
@login_required
def get_mark(mark_id: int):
    """Get single mark record with grade calculations and organisation scoping."""
    existing = MarkRepository.get_by_id(mark_id)
    if not existing:
        raise NotFoundError(f"Mark entry with ID {mark_id} not found.")

    # Enforce organisation and student access controls
    check_organisation_scope(existing.get("organisation_id"))
    user = get_current_user()
    if user["role"] == "Student":
        check_student_scope(existing["student_id"])

    record = MarkService.get_mark(mark_id)
    return api_response(data=record, message="Mark retrieved successfully")


@marks_bp.route("/<int:mark_id>", methods=["PUT", "PATCH"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation", "Faculty")
def update_mark(mark_id: int):
    """Update mark entry (Admin, Organisation, or assigned Faculty only)."""
    user = get_current_user()
    role = str(user.get("role") or "").strip().title()

    existing = MarkRepository.get_by_id(mark_id)
    if not existing:
        raise NotFoundError(f"Mark entry with ID {mark_id} not found.")

    check_organisation_scope(existing.get("organisation_id"))

    if role == "Faculty":
        faculty_id = user.get("faculty_id")
        if not faculty_id or not FacultyRepository.is_faculty_assigned_to_subject(
            faculty_id, existing["subject_id"], existing["semester_id"]
        ):
            raise ForbiddenError("You are not authorized to modify marks for this course.")

    payload = request.get_json(silent=True) or {}
    updated = MarkService.update_mark(mark_id, payload)
    return api_response(data=updated, message="Mark updated successfully")


@marks_bp.route("/<int:mark_id>", methods=["DELETE"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def delete_mark(mark_id: int):
    """Delete mark entry (Admin and Organisation managers only)."""
    existing = MarkRepository.get_by_id(mark_id)
    if not existing:
        raise NotFoundError(f"Mark entry with ID {mark_id} not found.")

    check_organisation_scope(existing.get("organisation_id"))
    MarkService.delete_mark(mark_id)
    return api_response(data={"deleted_id": mark_id}, message="Mark deleted successfully")
