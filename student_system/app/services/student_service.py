"""
Student service handling business logic for student profiles and organisation scoping.
"""

from typing import Any, Dict, List, Optional
import math
from app.repositories.organisation_repo import OrganisationRepository
from app.repositories.student_repo import StudentRepository
from app.repositories.semester_repo import SemesterRepository
from app.repositories.subject_repo import SubjectRepository
from app.utils.validators import validate_student_payload
from app.utils.exceptions import NotFoundError, ConflictError, ForbiddenError, ValidationError
from app.utils.auth import can_select_organisation


class StudentService:
    """Service encapsulating business operations on students."""

    @staticmethod
    def create_student(data: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = validate_student_payload(data, is_update=False)
        org_id = int(data.get("organisation_id") or cleaned.get("organisation_id") or 1)

        # Verify organisation exists and is active
        org = OrganisationRepository.get_by_id(org_id)
        if not org:
            raise NotFoundError(f"Organisation with ID {org_id} does not exist.")
        if org.get("status") == "Inactive":
            raise ValidationError(f"Cannot assign student to inactive organisation '{org['name']}'.")

        cleaned["organisation_id"] = org_id

        # Check duplicate roll number within the organisation
        if StudentRepository.get_by_roll_number(cleaned["roll_number"], organisation_id=org_id):
            raise ConflictError(f"A student with roll number '{cleaned['roll_number']}' already exists in this organisation.")

        # Check duplicate email within the organisation
        if StudentRepository.get_by_email(cleaned["email"], organisation_id=org_id):
            raise ConflictError(f"A student with email '{cleaned['email']}' already exists in this organisation.")

        # Check semester validity if provided
        if cleaned.get("current_semester_id"):
            semester = SemesterRepository.get_by_id(cleaned["current_semester_id"])
            if not semester:
                raise NotFoundError(f"Semester with ID {cleaned['current_semester_id']} does not exist.")
            if int(semester["organisation_id"]) != org_id:
                raise ValidationError("Cannot assign semester belonging to another organisation.")

        student_id = StudentRepository.create(cleaned)
        student = StudentRepository.get_by_id(student_id)
        return student

    @staticmethod
    def get_student(student_id: int, include_enrollments: bool = True) -> Dict[str, Any]:
        student = StudentRepository.get_by_id(student_id)
        if not student:
            raise NotFoundError(f"Student with ID {student_id} not found.")

        if include_enrollments:
            student["enrolled_subjects"] = StudentRepository.get_enrolled_subjects(student_id)

        return student

    @staticmethod
    def update_student(student_id: int, data: Dict[str, Any], current_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        existing = StudentRepository.get_by_id(student_id)
        if not existing:
            raise NotFoundError(f"Student with ID {student_id} not found.")

        cleaned = validate_student_payload(data, is_update=True)
        old_org_id = int(existing["organisation_id"])
        target_org_id = old_org_id

        # Handle organisation reassignment
        if "organisation_id" in data and data["organisation_id"] is not None:
            try:
                requested_org_id = int(data["organisation_id"])
            except (ValueError, TypeError):
                raise ValidationError("Invalid organisation_id.")

            if requested_org_id != old_org_id:
                # Reassignment attempted: Verify current_user has Admin / Super Admin permission
                if not current_user or not can_select_organisation(current_user):
                    raise ForbiddenError("Only Administrators can reassign a student to another organisation.")

                target_org = OrganisationRepository.get_by_id(requested_org_id)
                if not target_org:
                    raise NotFoundError(f"Target organisation with ID {requested_org_id} does not exist.")
                if target_org.get("status") == "Inactive":
                    raise ValidationError(f"Cannot reassign student to inactive organisation '{target_org['name']}'.")

                target_org_id = requested_org_id
                cleaned["organisation_id"] = target_org_id

        if not cleaned and target_org_id == old_org_id:
            return existing

        effective_org_id = target_org_id

        # Check roll number uniqueness if changed or org reassigned
        check_roll = cleaned.get("roll_number", existing["roll_number"])
        if check_roll != existing["roll_number"] or target_org_id != old_org_id:
            other = StudentRepository.get_by_roll_number(check_roll, organisation_id=effective_org_id)
            if other and other["id"] != student_id:
                raise ConflictError(f"Roll number '{check_roll}' is already assigned to another student in the target organisation.")

        # Check email uniqueness if changed or org reassigned
        check_email = cleaned.get("email", existing["email"])
        if check_email != existing["email"] or target_org_id != old_org_id:
            other = StudentRepository.get_by_email(check_email, organisation_id=effective_org_id)
            if other and other["id"] != student_id:
                raise ConflictError(f"Email '{check_email}' is already assigned to another student in the target organisation.")

        # Semester validity check
        if cleaned.get("current_semester_id"):
            semester = SemesterRepository.get_by_id(cleaned["current_semester_id"])
            if not semester:
                raise NotFoundError(f"Semester with ID {cleaned['current_semester_id']} does not exist.")
            if int(semester["organisation_id"]) != effective_org_id:
                raise ValidationError("Cannot assign semester belonging to another organisation.")
        elif target_org_id != old_org_id and existing.get("current_semester_id"):
            # If organisation changed and semester was not explicitly changed, check if old semester matches target org
            semester = SemesterRepository.get_by_id(existing["current_semester_id"])
            if semester and int(semester["organisation_id"]) != effective_org_id:
                cleaned["current_semester_id"] = None

        if cleaned:
            StudentRepository.update(student_id, cleaned)

        # If student's organisation changed, sync linked user accounts
        if target_org_id != old_org_id:
            from app import db
            db.execute_update(
                "UPDATE users SET organisation_id = %s WHERE student_id = %s",
                (target_org_id, student_id)
            )

        return StudentRepository.get_by_id(student_id)

    @staticmethod
    def delete_student(student_id: int) -> bool:
        existing = StudentRepository.get_by_id(student_id)
        if not existing:
            raise NotFoundError(f"Student with ID {student_id} not found.")

        from app import db
        # Check if student has marks or attendance records
        m_count = db.query_one("SELECT COUNT(*) as c FROM marks WHERE student_id = %s", (student_id,))
        marks_count = m_count["c"] if m_count else 0

        a_count = db.query_one("SELECT COUNT(*) as c FROM attendance WHERE student_id = %s", (student_id,))
        att_count = a_count["c"] if a_count else 0

        if marks_count > 0 or att_count > 0:
            reasons = []
            if marks_count:
                reasons.append(f"{marks_count} academic mark(s)")
            if att_count:
                reasons.append(f"{att_count} attendance record(s)")
            raise ConflictError(
                f"Cannot delete student: Student has existing academic records ({', '.join(reasons)}). "
                f"Please archive or resolve academic evaluations before deleting."
            )

        # Unlink any user accounts linked to this student
        db.execute_update("UPDATE users SET student_id = NULL WHERE student_id = %s", (student_id,))

        StudentRepository.delete(student_id)
        return True

    @staticmethod
    def list_students(
        search: Optional[str] = None,
        status: Optional[str] = None,
        semester_id: Optional[int] = None,
        organisation_id: Optional[int] = None,
        sort_by: Optional[str] = None,
        order: Optional[str] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> Dict[str, Any]:
        offset = (page - 1) * per_page
        items = StudentRepository.list_students(
            search=search,
            status=status,
            semester_id=semester_id,
            organisation_id=organisation_id,
            sort_by=sort_by,
            order=order,
            limit=per_page,
            offset=offset,
        )
        total = StudentRepository.count_students(
            search=search,
            status=status,
            semester_id=semester_id,
            organisation_id=organisation_id,
        )
        total_pages = math.ceil(total / per_page) if total > 0 else 1

        return {
            "items": items,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            }
        }

    @staticmethod
    def enroll_subject(student_id: int, subject_id: int, semester_id: int) -> Dict[str, Any]:
        student = StudentRepository.get_by_id(student_id)
        if not student:
            raise NotFoundError(f"Student with ID {student_id} not found.")

        subject = SubjectRepository.get_by_id(subject_id)
        if not subject:
            raise NotFoundError(f"Subject with ID {subject_id} not found.")

        semester = SemesterRepository.get_by_id(semester_id)
        if not semester:
            raise NotFoundError(f"Semester with ID {semester_id} not found.")

        # Prevent cross-organisation enrollments
        if (
            int(student["organisation_id"]) != int(subject["organisation_id"])
            or int(student["organisation_id"]) != int(semester["organisation_id"])
        ):
            raise ValidationError(
                "Cross-organisation enrollment prohibited: Student, Subject, and Semester must belong to the same organisation."
            )

        StudentRepository.enroll_subject(student_id, subject_id, semester_id)
        return {
            "student_id": student_id,
            "subject_id": subject_id,
            "semester_id": semester_id,
            "enrolled": True,
        }

    @staticmethod
    def unenroll_subject(student_id: int, subject_id: int, semester_id: int) -> bool:
        affected = StudentRepository.unenroll_subject(student_id, subject_id, semester_id)
        if affected == 0:
            raise NotFoundError("Enrollment record not found.")
        return True
