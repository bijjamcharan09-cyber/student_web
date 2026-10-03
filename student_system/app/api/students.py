"""
Students API blueprint using standard Flask routes.
"""

from flask import Blueprint, request
from app.services.student_service import StudentService
from app.utils.auth import login_required, roles_required
from app.utils.responses import api_response
from app.utils.validators import parse_pagination

students_bp = Blueprint("students", __name__, url_prefix="/api/v1/students")


@students_bp.route("", methods=["GET"])
def list_students():
    """List students with search and filtering."""
    search = request.args.get("search", "").strip() or None
    status = request.args.get("status", "").strip() or None
    sem_id_raw = request.args.get("semester_id")
    semester_id = int(sem_id_raw) if sem_id_raw and sem_id_raw.isdigit() else None

    page, per_page = parse_pagination(request.args.get("page"), request.args.get("per_page"))

    result = StudentService.list_students(
        search=search,
        status=status,
        semester_id=semester_id,
        page=page,
        per_page=per_page,
    )
    return api_response(
        data=result["items"],
        message="Students retrieved successfully",
        meta=result["pagination"],
    )


@students_bp.route("", methods=["POST"])
def create_student():
    """Create a new student profile."""
    payload = request.get_json(silent=True) or {}
    student = StudentService.create_student(payload)
    return api_response(data=student, message="Student created successfully", status_code=201)


@students_bp.route("/<int:student_id>", methods=["GET"])
def get_student(student_id: int):
    """Retrieve student details by ID."""
    student = StudentService.get_student(student_id)
    return api_response(data=student, message="Student retrieved successfully")


@students_bp.route("/<int:student_id>", methods=["PUT", "PATCH"])
@roles_required("Admin")
def update_student(student_id: int):
    """Update student profile (Admin only)."""
    payload = request.get_json(silent=True) or {}
    updated = StudentService.update_student(student_id, payload)
    return api_response(data=updated, message="Student updated successfully")


@students_bp.route("/<int:student_id>", methods=["DELETE"])
@roles_required("Admin")
def delete_student(student_id: int):
    """Delete a student profile (Admin only)."""
    StudentService.delete_student(student_id)
    return api_response(data={"deleted_id": student_id}, message="Student deleted successfully")


@students_bp.route("/<int:student_id>/enroll", methods=["POST"])
def enroll_subject(student_id: int):
    """Enroll a student in a subject for a given semester."""
    payload = request.get_json(silent=True) or {}
    subject_id = payload.get("subject_id")
    semester_id = payload.get("semester_id")

    if not subject_id or not semester_id:
        from app.utils.exceptions import ValidationError
        raise ValidationError("Both 'subject_id' and 'semester_id' are required.")

    result = StudentService.enroll_subject(student_id, int(subject_id), int(semester_id))
    return api_response(data=result, message="Student enrolled in subject successfully", status_code=201)


@students_bp.route("/<int:student_id>/enroll/<int:subject_id>/<int:semester_id>", methods=["DELETE"])
def unenroll_subject(student_id: int, subject_id: int, semester_id: int):
    """Unenroll a student from a subject."""
    StudentService.unenroll_subject(student_id, subject_id, semester_id)
    return api_response(
        data={"student_id": student_id, "subject_id": subject_id, "semester_id": semester_id},
        message="Student unenrolled successfully",
    )
