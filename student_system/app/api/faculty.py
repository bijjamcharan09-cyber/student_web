"""
Faculty API Blueprint for academic instructor management and course assignments with organisation scoping.
"""

from flask import Blueprint, request
from app.repositories.faculty_repo import FacultyRepository
from app.repositories.subject_repo import SubjectRepository
from app.repositories.semester_repo import SemesterRepository
from app.utils.auth import (
    check_organisation_scope,
    get_current_user,
    get_effective_organisation_id,
    login_required,
    roles_required,
)
from app.utils.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.utils.responses import api_response

faculty_bp = Blueprint("faculty", __name__, url_prefix="/api/v1/faculty")


@faculty_bp.route("", methods=["GET"])
@roles_required("Admin", "Super Admin", "Organisation")
def list_faculty():
    """List faculty members with filtering, sorting, and organisation scoping."""
    org_id = get_effective_organisation_id()
    dept = request.args.get("department", "").strip() or None
    sort_by = request.args.get("sort_by", "").strip().lower() or None
    order = request.args.get("order", "").strip().lower() or None
    items = FacultyRepository.list_faculty(
        department=dept,
        organisation_id=org_id,
        sort_by=sort_by,
        order=order,
    )
    return api_response(data=items, message="Faculty members retrieved successfully.")


@faculty_bp.route("", methods=["POST"])
@roles_required("Admin", "Super Admin", "Organisation")
def create_faculty():
    """Create a new faculty profile within user's organisation."""
    payload = request.get_json(silent=True) or {}
    org_id = get_effective_organisation_id()
    if org_id is not None:
        payload["organisation_id"] = org_id

    code = payload.get("faculty_code", "").strip()
    first_name = payload.get("first_name", "").strip()
    last_name = payload.get("last_name", "").strip()
    email = payload.get("email", "").strip().lower()
    department = payload.get("department", "").strip()

    if not code or not first_name or not last_name or not email or not department:
        raise ValidationError("faculty_code, first_name, last_name, email, and department are required.")

    if FacultyRepository.get_by_code(code, organisation_id=payload.get("organisation_id")):
        from app.utils.exceptions import ConflictError
        raise ConflictError(f"Faculty code '{code}' is already assigned in this organisation.")

    fac_id = FacultyRepository.create(payload)
    created = FacultyRepository.get_by_id(fac_id)
    return api_response(data=created, message="Faculty profile created successfully.", status_code=201)


@faculty_bp.route("/<int:faculty_id>", methods=["GET"])
@login_required
def get_faculty(faculty_id: int):
    """Retrieve faculty details with organisation and role checks."""
    user = get_current_user()
    role = str(user.get("role") or "").strip().title()

    faculty = FacultyRepository.get_by_id(faculty_id)
    if not faculty:
        raise NotFoundError(f"Faculty with ID {faculty_id} not found.")

    check_organisation_scope(faculty.get("organisation_id"))

    if role == "Faculty" and user.get("faculty_id") != faculty_id:
        raise ForbiddenError("Access denied: You cannot view another faculty member's profile.")
    elif role == "Student":
        raise ForbiddenError("Students cannot access faculty profiles directly.")

    return api_response(data=faculty, message="Faculty profile retrieved successfully.")


@faculty_bp.route("/<int:faculty_id>/assign", methods=["POST"])
@roles_required("Admin", "Super Admin", "Organisation")
def assign_subject(faculty_id: int):
    """Assign a subject course to a faculty member with cross-organisation check."""
    payload = request.get_json(silent=True) or {}
    subject_id = payload.get("subject_id")
    semester_id = payload.get("semester_id")

    if not subject_id or not semester_id:
        raise ValidationError("Both 'subject_id' and 'semester_id' are required.")

    faculty = FacultyRepository.get_by_id(faculty_id)
    if not faculty:
        raise NotFoundError(f"Faculty with ID {faculty_id} not found.")

    subject = SubjectRepository.get_by_id(subject_id)
    if not subject:
        raise NotFoundError(f"Subject with ID {subject_id} not found.")

    semester = SemesterRepository.get_by_id(semester_id)
    if not semester:
        raise NotFoundError(f"Semester with ID {semester_id} not found.")

    check_organisation_scope(faculty.get("organisation_id"))
    if (
        int(faculty["organisation_id"]) != int(subject["organisation_id"])
        or int(faculty["organisation_id"]) != int(semester["organisation_id"])
    ):
        raise ValidationError("Cross-organisation assignment prohibited: Faculty, Subject, and Semester must belong to the same organisation.")

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
    faculty = FacultyRepository.get_by_id(faculty_id)
    if not faculty:
        raise NotFoundError(f"Faculty with ID {faculty_id} not found.")

    check_organisation_scope(faculty.get("organisation_id"))
    user = get_current_user()
    role = str(user.get("role") or "").strip().title()

    if role == "Faculty" and user.get("faculty_id") != faculty_id:
        raise ForbiddenError("You can only view your own assigned subjects.")
    elif role == "Student":
        raise ForbiddenError("Access forbidden.")

    sem_id = request.args.get("semester_id")
    semester_id = int(sem_id) if sem_id and sem_id.isdigit() else None

    subjects = FacultyRepository.get_assigned_subjects(faculty_id, semester_id=semester_id)
    return api_response(data=subjects, message="Assigned subjects retrieved successfully.")


@faculty_bp.route("/<int:faculty_id>", methods=["PUT", "PATCH"])
@roles_required("Admin", "Super Admin", "Organisation")
def update_faculty(faculty_id: int):
    """Update faculty profile."""
    existing = FacultyRepository.get_by_id(faculty_id)
    if not existing:
        raise NotFoundError(f"Faculty with ID {faculty_id} not found.")

    check_organisation_scope(existing.get("organisation_id"))
    payload = request.get_json(silent=True) or {}
    from app.utils.exceptions import ConflictError

    org_id = int(existing["organisation_id"])

    # Unique code check
    if "faculty_code" in payload and payload["faculty_code"]:
        new_code = str(payload["faculty_code"]).strip().upper()
        if new_code != existing["faculty_code"]:
            other = FacultyRepository.get_by_code(new_code, organisation_id=org_id)
            if other and other["id"] != faculty_id:
                raise ConflictError(f"Faculty code '{new_code}' is already assigned to another instructor.")
            payload["faculty_code"] = new_code

    # Unique email check
    if "email" in payload and payload["email"]:
        new_email = str(payload["email"]).strip().lower()
        if new_email != existing["email"]:
            other = FacultyRepository.get_by_email(new_email, organisation_id=org_id)
            if other and other["id"] != faculty_id:
                raise ConflictError(f"Email '{new_email}' is already assigned to another instructor.")
            payload["email"] = new_email

    from app import db
    fields = []
    params = {}
    allowed = ["faculty_code", "first_name", "last_name", "email", "phone", "department", "designation"]
    for k, v in payload.items():
        if k in allowed:
            fields.append(f"`{k}` = %({k})s")
            params[k] = v

    if fields:
        params["id"] = faculty_id
        db.execute_update(f"UPDATE faculty SET {', '.join(fields)} WHERE id = %(id)s", params)

    updated = FacultyRepository.get_by_id(faculty_id)
    return api_response(data=updated, message="Faculty profile updated successfully.")


@faculty_bp.route("/<int:faculty_id>", methods=["DELETE"])
@roles_required("Admin", "Super Admin", "Organisation")
def delete_faculty(faculty_id: int):
    """Delete faculty profile."""
    existing = FacultyRepository.get_by_id(faculty_id)
    if not existing:
        raise NotFoundError(f"Faculty with ID {faculty_id} not found.")

    check_organisation_scope(existing.get("organisation_id"))

    from app import db
    row = db.query_one("SELECT COUNT(*) as c FROM faculty_subjects WHERE faculty_id = %s", (faculty_id,))
    assigned_count = row["c"] if row else 0
    if assigned_count > 0:
        from app.utils.exceptions import ConflictError
        raise ConflictError(
            f"Cannot delete faculty member: Instructor is actively assigned to {assigned_count} course(s). "
            f"Please unassign course teaching duties first."
        )

    # Unlink any user accounts linked to this faculty
    db.execute_update("UPDATE users SET faculty_id = NULL WHERE faculty_id = %s", (faculty_id,))

    db.execute_update("DELETE FROM faculty WHERE id = %s", (faculty_id,))
    return api_response(data={"deleted_id": faculty_id}, message="Faculty profile deleted successfully.")
