"""
Students API blueprint with strict authentication, RBAC, IDOR protection, and organisation scoping.
"""

from flask import Blueprint, request
from app.services.student_service import StudentService
from app.utils.auth import (
    check_student_scope,
    get_current_user,
    get_effective_organisation_id,
    login_required,
    roles_required,
)
from app.utils.responses import api_response
from app.utils.validators import parse_pagination

students_bp = Blueprint("students", __name__, url_prefix="/api/v1/students")


@students_bp.route("", methods=["GET"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation", "Faculty")
def list_students():
    """List students with search, filtering, sorting, and organisation scoping."""
    org_id = get_effective_organisation_id()
    search = request.args.get("search", "").strip() or None
    status = request.args.get("status", "").strip() or None
    sem_id_raw = request.args.get("semester_id")
    semester_id = int(sem_id_raw) if sem_id_raw and sem_id_raw.isdigit() else None
    sort_by = request.args.get("sort_by", "").strip().lower() or None
    order = request.args.get("order", "").strip().lower() or None

    page, per_page = parse_pagination(request.args.get("page"), request.args.get("per_page"))

    result = StudentService.list_students(
        search=search,
        status=status,
        semester_id=semester_id,
        organisation_id=org_id,
        sort_by=sort_by,
        order=order,
        page=page,
        per_page=per_page,
    )
    return api_response(
        data=result["items"],
        message="Students retrieved successfully",
        meta=result["pagination"],
    )


@students_bp.route("", methods=["POST"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def create_student():
    """Create a new student profile within the authenticated user's organisation."""
    from app.utils.auth import can_select_organisation
    from app.utils.exceptions import ForbiddenError

    user = get_current_user()
    payload = request.get_json(silent=True) or {}
    
    if can_select_organisation(user):
        # Admin can explicitly assign to any organisation via payload, active selection, or default
        requested_org = payload.get("organisation_id")
        if requested_org is not None and str(requested_org).strip() != "":
            payload["organisation_id"] = int(requested_org)
        else:
            eff_org = get_effective_organisation_id()
            payload["organisation_id"] = eff_org if eff_org is not None else 1
    else:
        # Organisation user: strictly enforce their own organisation_id
        user_org_id = int(user.get("organisation_id") or 1)
        if "organisation_id" in payload and payload["organisation_id"] is not None:
            if int(payload["organisation_id"]) != user_org_id:
                raise ForbiddenError("Access denied: Organisation users cannot assign students to another organisation.")
        payload["organisation_id"] = user_org_id

    student = StudentService.create_student(payload)
    return api_response(data=student, message="Student created successfully", status_code=201)


@students_bp.route("/<int:student_id>", methods=["GET"])
@login_required
def get_student(student_id: int):
    """Retrieve student details by ID with IDOR and organisation boundary verification."""
    check_student_scope(student_id)
    student = StudentService.get_student(student_id)
    return api_response(data=student, message="Student retrieved successfully")


@students_bp.route("/<int:student_id>", methods=["PUT", "PATCH"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def update_student(student_id: int):
    """Update student profile (Admin and Organisation managers only)."""
    check_student_scope(student_id)
    user = get_current_user()
    payload = request.get_json(silent=True) or {}
    updated = StudentService.update_student(student_id, payload, current_user=user)
    return api_response(data=updated, message="Student updated successfully")


@students_bp.route("/<int:student_id>", methods=["DELETE"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def delete_student(student_id: int):
    """Delete a student profile (Admin and Organisation managers only)."""
    check_student_scope(student_id)
    StudentService.delete_student(student_id)
    return api_response(data={"deleted_id": student_id}, message="Student deleted successfully")


@students_bp.route("/<int:student_id>/enroll", methods=["POST"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def enroll_subject(student_id: int):
    """Enroll a student in a subject for a given semester with cross-organisation check."""
    check_student_scope(student_id)
    payload = request.get_json(silent=True) or {}
    subject_id = payload.get("subject_id")
    semester_id = payload.get("semester_id")

    if not subject_id or not semester_id:
        from app.utils.exceptions import ValidationError
        raise ValidationError("Both 'subject_id' and 'semester_id' are required.")

    result = StudentService.enroll_subject(student_id, int(subject_id), int(semester_id))
    return api_response(data=result, message="Student enrolled in subject successfully", status_code=201)


@students_bp.route("/<int:student_id>/enroll/<int:subject_id>/<int:semester_id>", methods=["DELETE"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def unenroll_subject(student_id: int, subject_id: int, semester_id: int):
    """Unenroll a student from a subject."""
    check_student_scope(student_id)
    StudentService.unenroll_subject(student_id, subject_id, semester_id)
    return api_response(
        data={"student_id": student_id, "subject_id": subject_id, "semester_id": semester_id},
        message="Student unenrolled successfully",
    )
