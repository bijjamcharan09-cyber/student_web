"""
Faculty API Blueprint for academic instructor management and course assignments.
"""

from flask import Blueprint, request
from app.repositories.faculty_repo import FacultyRepository
from app.repositories.subject_repo import SubjectRepository
from app.repositories.semester_repo import SemesterRepository
from app.utils.auth import get_current_user, login_required, roles_required
from app.utils.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.utils.responses import api_response

faculty_bp = Blueprint("faculty", __name__, url_prefix="/api/v1/faculty")


@faculty_bp.route("", methods=["GET"])
@roles_required("Admin")
def list_faculty():
    """List all faculty members (Admin only)."""
    dept = request.args.get("department", "").strip() or None
    items = FacultyRepository.list_faculty(department=dept)
    return api_response(data=items, message="Faculty members retrieved successfully.")


@faculty_bp.route("", methods=["POST"])
@roles_required("Admin")
def create_faculty():
    """Create a new faculty profile (Admin only)."""
    payload = request.get_json(silent=True) or {}
    code = payload.get("faculty_code", "").strip()
    first_name = payload.get("first_name", "").strip()
    last_name = payload.get("last_name", "").strip()
    email = payload.get("email", "").strip().lower()
    department = payload.get("department", "").strip()

    if not code or not first_name or not last_name or not email or not department:
        raise ValidationError("faculty_code, first_name, last_name, email, and department are required.")

    if FacultyRepository.get_by_code(code):
        from app.utils.exceptions import ConflictError
        raise ConflictError(f"Faculty code '{code}' is already assigned.")

    fac_id = FacultyRepository.create(payload)
    created = FacultyRepository.get_by_id(fac_id)
    return api_response(data=created, message="Faculty profile created successfully.", status_code=201)


@faculty_bp.route("/<int:faculty_id>", methods=["GET"])
@login_required
def get_faculty(faculty_id: int):
    """Retrieve faculty details. Allowed for Admin or the faculty member themselves."""
    user = get_current_user()
    if user["role"] == "Faculty" and user.get("faculty_id") != faculty_id:
        raise ForbiddenError("Access denied: You cannot view another faculty member's profile.")
    elif user["role"] == "Student":
        raise ForbiddenError("Students cannot access faculty profiles directly.")

    faculty = FacultyRepository.get_by_id(faculty_id)
    if not faculty:
        raise NotFoundError(f"Faculty with ID {faculty_id} not found.")

    return api_response(data=faculty, message="Faculty profile retrieved successfully.")


@faculty_bp.route("/<int:faculty_id>/assign", methods=["POST"])
@roles_required("Admin")
def assign_subject(faculty_id: int):
    """Assign a subject course to a faculty member (Admin only)."""
    payload = request.get_json(silent=True) or {}
    subject_id = payload.get("subject_id")
    semester_id = payload.get("semester_id")

    if not subject_id or not semester_id:
        raise ValidationError("Both 'subject_id' and 'semester_id' are required.")

    if not FacultyRepository.get_by_id(faculty_id):
        raise NotFoundError(f"Faculty with ID {faculty_id} not found.")
    if not SubjectRepository.get_by_id(subject_id):
        raise NotFoundError(f"Subject with ID {subject_id} not found.")
    if not SemesterRepository.get_by_id(semester_id):
        raise NotFoundError(f"Semester with ID {semester_id} not found.")

    FacultyRepository.assign_subject(faculty_id, int(subject_id), int(semester_id))
    return api_response(
        data={"faculty_id": faculty_id, "subject_id": subject_id, "semester_id": semester_id},
        message="Subject assigned to faculty successfully.",
        status_code=201,
    )


@faculty_bp.route("/<int:faculty_id>/subjects", methods=["GET"])
@login_required
def get_assigned_subjects(faculty_id: int):
    """List subjects assigned to a faculty member."""
    user = get_current_user()
    if user["role"] == "Faculty" and user.get("faculty_id") != faculty_id:
        raise ForbiddenError("You can only view your own assigned subjects.")
    elif user["role"] == "Student":
        raise ForbiddenError("Access forbidden.")

    sem_id = request.args.get("semester_id")
    semester_id = int(sem_id) if sem_id and sem_id.isdigit() else None

    subjects = FacultyRepository.get_assigned_subjects(faculty_id, semester_id=semester_id)
    return api_response(data=subjects, message="Assigned subjects retrieved successfully.")
