"""
Subject service handling business logic for academic subjects/courses.
"""

from typing import Any, Dict, List, Optional
import math
from app.repositories.subject_repo import SubjectRepository
from app.repositories.semester_repo import SemesterRepository
from app.utils.validators import validate_subject_payload
from app.utils.exceptions import NotFoundError, ConflictError


class SubjectService:
    """Service encapsulating business operations on subjects."""

    @staticmethod
    def create_subject(data: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = validate_subject_payload(data, is_update=False)

        # Check unique code
        if SubjectRepository.get_by_code(cleaned["subject_code"]):
            raise ConflictError(f"A subject with code '{cleaned['subject_code']}' already exists.")

        # Check semester if provided
        if cleaned.get("semester_id"):
            semester = SemesterRepository.get_by_id(cleaned["semester_id"])
            if not semester:
                raise NotFoundError(f"Semester with ID {cleaned['semester_id']} does not exist.")

        subject_id = SubjectRepository.create(cleaned)
        return SubjectRepository.get_by_id(subject_id)

    @staticmethod
    def get_subject(subject_id: int) -> Dict[str, Any]:
        subject = SubjectRepository.get_by_id(subject_id)
        if not subject:
            raise NotFoundError(f"Subject with ID {subject_id} not found.")
        return subject

    @staticmethod
    def update_subject(subject_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = SubjectRepository.get_by_id(subject_id)
        if not existing:
            raise NotFoundError(f"Subject with ID {subject_id} not found.")

        cleaned = validate_subject_payload(data, is_update=True)
        if not cleaned:
            return existing

        # Check unique code if changed
        if "subject_code" in cleaned and cleaned["subject_code"] != existing["subject_code"]:
            other = SubjectRepository.get_by_code(cleaned["subject_code"])
            if other and other["id"] != subject_id:
                raise ConflictError(f"Subject code '{cleaned['subject_code']}' is already assigned.")

        # Check semester if changed
        if cleaned.get("semester_id"):
            semester = SemesterRepository.get_by_id(cleaned["semester_id"])
            if not semester:
                raise NotFoundError(f"Semester with ID {cleaned['semester_id']} does not exist.")

        SubjectRepository.update(subject_id, cleaned)
        return SubjectRepository.get_by_id(subject_id)

    @staticmethod
    def delete_subject(subject_id: int) -> bool:
        existing = SubjectRepository.get_by_id(subject_id)
        if not existing:
            raise NotFoundError(f"Subject with ID {subject_id} not found.")

        from app import db
        # Check active dependencies
        m_count = db.query_one("SELECT COUNT(*) as c FROM marks WHERE subject_id = %s", (subject_id,))
        marks_count = m_count["c"] if m_count else 0

        a_count = db.query_one("SELECT COUNT(*) as c FROM attendance WHERE subject_id = %s", (subject_id,))
        att_count = a_count["c"] if a_count else 0

        e_count = db.query_one("SELECT COUNT(*) as c FROM student_subjects WHERE subject_id = %s", (subject_id,))
        enrolled_count = e_count["c"] if e_count else 0

        f_count = db.query_one("SELECT COUNT(*) as c FROM faculty_subjects WHERE subject_id = %s", (subject_id,))
        fac_count = f_count["c"] if f_count else 0

        if marks_count > 0 or att_count > 0 or enrolled_count > 0 or fac_count > 0:
            reasons = []
            if marks_count:
                reasons.append(f"{marks_count} academic mark(s)")
            if att_count:
                reasons.append(f"{att_count} attendance record(s)")
            if enrolled_count:
                reasons.append(f"{enrolled_count} enrolled student(s)")
            if fac_count:
                reasons.append(f"{fac_count} assigned instructor(s)")
            raise ConflictError(
                f"Cannot delete subject: Course has active academic dependencies ({', '.join(reasons)}). "
                f"Please resolve or archive related course records before deleting."
            )

        SubjectRepository.delete(subject_id)
        return True

    @staticmethod
    def list_subjects(
        department: Optional[str] = None,
        semester_id: Optional[int] = None,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        offset = (page - 1) * per_page
        items = SubjectRepository.list_subjects(
            department=department,
            semester_id=semester_id,
            search=search,
            limit=per_page,
            offset=offset,
        )
        total = SubjectRepository.count_subjects(
            department=department,
            semester_id=semester_id,
            search=search,
        )
        total_pages = math.ceil(total / per_page) if total > 0 else 1

        return {
            "items": items,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
            }
        }
