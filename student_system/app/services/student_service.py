"""
Student service handling business logic for student profiles.
"""

from typing import Any, Dict, List, Optional
import math
from app.repositories.student_repo import StudentRepository
from app.repositories.semester_repo import SemesterRepository
from app.repositories.subject_repo import SubjectRepository
from app.utils.validators import validate_student_payload
from app.utils.exceptions import NotFoundError, ConflictError, ValidationError


class StudentService:
    """Service encapsulating business operations on students."""

    @staticmethod
    def create_student(data: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = validate_student_payload(data, is_update=False)

        # Check duplicate roll number
        if StudentRepository.get_by_roll_number(cleaned["roll_number"]):
            raise ConflictError(f"A student with roll number '{cleaned['roll_number']}' already exists.")

        # Check duplicate email
        if StudentRepository.get_by_email(cleaned["email"]):
            raise ConflictError(f"A student with email '{cleaned['email']}' already exists.")

        # Check semester validity if provided
        if cleaned.get("current_semester_id"):
            semester = SemesterRepository.get_by_id(cleaned["current_semester_id"])
            if not semester:
                raise NotFoundError(f"Semester with ID {cleaned['current_semester_id']} does not exist.")

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
    def update_student(student_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = StudentRepository.get_by_id(student_id)
        if not existing:
            raise NotFoundError(f"Student with ID {student_id} not found.")

        cleaned = validate_student_payload(data, is_update=True)
        if not cleaned:
            return existing

        # Check roll number uniqueness if changed
        if "roll_number" in cleaned and cleaned["roll_number"] != existing["roll_number"]:
            other = StudentRepository.get_by_roll_number(cleaned["roll_number"])
            if other and other["id"] != student_id:
                raise ConflictError(f"Roll number '{cleaned['roll_number']}' is already assigned to another student.")

        # Check email uniqueness if changed
        if "email" in cleaned and cleaned["email"] != existing["email"]:
            other = StudentRepository.get_by_email(cleaned["email"])
            if other and other["id"] != student_id:
                raise ConflictError(f"Email '{cleaned['email']}' is already assigned to another student.")

        # Check semester validity if changed
        if cleaned.get("current_semester_id"):
            semester = SemesterRepository.get_by_id(cleaned["current_semester_id"])
            if not semester:
                raise NotFoundError(f"Semester with ID {cleaned['current_semester_id']} does not exist.")

        StudentRepository.update(student_id, cleaned)
        return StudentRepository.get_by_id(student_id)

    @staticmethod
    def delete_student(student_id: int) -> bool:
        existing = StudentRepository.get_by_id(student_id)
        if not existing:
            raise NotFoundError(f"Student with ID {student_id} not found.")

        StudentRepository.delete(student_id)
        return True

    @staticmethod
    def list_students(
        search: Optional[str] = None,
        status: Optional[str] = None,
        semester_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> Dict[str, Any]:
        offset = (page - 1) * per_page
        items = StudentRepository.list_students(
            search=search,
            status=status,
            semester_id=semester_id,
            limit=per_page,
            offset=offset,
        )
        total = StudentRepository.count_students(search=search, status=status, semester_id=semester_id)
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
