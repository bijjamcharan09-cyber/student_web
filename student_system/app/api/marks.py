"""
Marks and grades API blueprint using standard Flask routes.
"""

from flask import Blueprint, request
from app.repositories.faculty_repo import FacultyRepository
from app.repositories.mark_repo import MarkRepository
from app.services.mark_service import MarkService
from app.utils.auth import get_current_user, login_required, roles_required
from app.utils.exceptions import ForbiddenError, NotFoundError
from app.utils.responses import api_response
from app.utils.validators import parse_pagination

marks_bp = Blueprint("marks", __name__, url_prefix="/api/v1/marks")


@marks_bp.route("", methods=["GET"])
def list_marks():
    """List marks filtered by student, subject, semester, or exam type."""
    def parse_int_param(param_name):
        val = request.args.get(param_name)
        return int(val) if val and val.isdigit() else None

    student_id = parse_int_param("student_id")
    subject_id = parse_int_param("subject_id")
    semester_id = parse_int_param("semester_id")
    exam_type = request.args.get("exam_type", "").strip().capitalize() or None

    page, per_page = parse_pagination(request.args.get("page"), request.args.get("per_page"))

    result = MarkService.list_marks(
        student_id=student_id,
        subject_id=subject_id,
        semester_id=semester_id,
        exam_type=exam_type,
        page=page,
        per_page=per_page,
    )
    return api_response(
        data=result["items"],
        message="Marks retrieved successfully",
        meta=result["pagination"],
    )


@marks_bp.route("", methods=["POST"])
def record_mark():
    """Record an individual student mark."""
    payload = request.get_json(silent=True) or {}
    record = MarkService.record_mark(payload)
    return api_response(data=record, message="Mark recorded successfully", status_code=201)


@marks_bp.route("/batch", methods=["POST"])
def batch_record_marks():
    """Record multiple marks in an atomic transaction."""
    payload = request.get_json(silent=True)
    if isinstance(payload, dict) and "records" in payload:
        records = payload["records"]
    elif isinstance(payload, list):
        records = payload
    else:
        from app.utils.exceptions import ValidationError
        raise ValidationError("Request body must be a list of marks or {'records': [...]}.")

    inserted = MarkService.batch_record_marks(records)
    return api_response(
        data=inserted,
        message=f"Successfully recorded {len(inserted)} marks in transaction",
        status_code=201,
    )


@marks_bp.route("/<int:mark_id>", methods=["GET"])
def get_mark(mark_id: int):
    """Get single mark record with grade calculations."""
    record = MarkService.get_mark(mark_id)
    return api_response(data=record, message="Mark retrieved successfully")


@marks_bp.route("/<int:mark_id>", methods=["PUT", "PATCH"])
@login_required
def update_mark(mark_id: int):
    """Update mark entry (Admin or assigned Faculty only)."""
    user = get_current_user()
    role = user["role"]
    if role == "Student":
        raise ForbiddenError("Students cannot modify marks.")

    existing = MarkRepository.get_by_id(mark_id)
    if not existing:
        raise NotFoundError(f"Mark entry with ID {mark_id} not found.")

    if role == "Faculty":
        faculty_id = user.get("faculty_id")
        if not faculty_id or not FacultyRepository.is_faculty_assigned_to_subject(faculty_id, existing["subject_id"], existing["semester_id"]):
            raise ForbiddenError("You are not authorized to modify marks for this course.")

    payload = request.get_json(silent=True) or {}
    updated = MarkService.update_mark(mark_id, payload)
    return api_response(data=updated, message="Mark updated successfully")


@marks_bp.route("/<int:mark_id>", methods=["DELETE"])
@roles_required("Admin")
def delete_mark(mark_id: int):
    """Delete mark entry (Admin only)."""
    existing = MarkRepository.get_by_id(mark_id)
    if not existing:
        raise NotFoundError(f"Mark entry with ID {mark_id} not found.")

    MarkService.delete_mark(mark_id)
    return api_response(data={"deleted_id": mark_id}, message="Mark deleted successfully")
