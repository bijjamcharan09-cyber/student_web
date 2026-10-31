"""
Subjects API blueprint with authentication, role checks, and organisation scoping.
"""

from flask import Blueprint, request
from app.services.subject_service import SubjectService
from app.utils.auth import (
    check_organisation_scope,
    get_current_user,
    get_effective_organisation_id,
    login_required,
    roles_required,
)
from app.utils.responses import api_response
from app.utils.validators import parse_pagination

subjects_bp = Blueprint("subjects", __name__, url_prefix="/api/v1/subjects")


@subjects_bp.route("", methods=["GET"])
def list_subjects():
    """List subjects with filters for department, semester, and sorting. Public for catalog browsing."""
    org_id = get_effective_organisation_id()
    department = request.args.get("department", "").strip() or None
    search = request.args.get("search", "").strip() or None
    sem_id_raw = request.args.get("semester_id")
    semester_id = int(sem_id_raw) if sem_id_raw and sem_id_raw.isdigit() else None
    sort_by = request.args.get("sort_by", "").strip().lower() or None
    order = request.args.get("order", "").strip().lower() or None

    page, per_page = parse_pagination(request.args.get("page"), request.args.get("per_page"))

    result = SubjectService.list_subjects(
        department=department,
        semester_id=semester_id,
        search=search,
        organisation_id=org_id,
        sort_by=sort_by,
        order=order,
        page=page,
        per_page=per_page,
    )
    return api_response(
        data=result["items"],
        message="Subjects retrieved successfully",
        meta=result["pagination"],
    )


@subjects_bp.route("", methods=["POST"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def create_subject():
    """Create a new subject within user's organisation."""
    payload = request.get_json(silent=True) or {}
    org_id = get_effective_organisation_id()
    if org_id is not None:
        payload["organisation_id"] = org_id

    subject = SubjectService.create_subject(payload)
    return api_response(data=subject, message="Subject created successfully", status_code=201)


@subjects_bp.route("/<int:subject_id>", methods=["GET"])
def get_subject(subject_id: int):
    """Get subject details by ID."""
    subject = SubjectService.get_subject(subject_id)
    return api_response(data=subject, message="Subject retrieved successfully")


@subjects_bp.route("/<int:subject_id>", methods=["PUT", "PATCH"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def update_subject(subject_id: int):
    """Update subject details (Admin and Organisation managers only)."""
    subject = SubjectService.get_subject(subject_id)
    check_organisation_scope(subject.get("organisation_id"))

    payload = request.get_json(silent=True) or {}
    updated = SubjectService.update_subject(subject_id, payload)
    return api_response(data=updated, message="Subject updated successfully")


@subjects_bp.route("/<int:subject_id>", methods=["DELETE"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def delete_subject(subject_id: int):
    """Delete a subject (Admin and Organisation managers only)."""
    subject = SubjectService.get_subject(subject_id)
    check_organisation_scope(subject.get("organisation_id"))

    SubjectService.delete_subject(subject_id)
    return api_response(data={"deleted_id": subject_id}, message="Subject deleted successfully")
