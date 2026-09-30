"""
Semester service handling business logic for academic semesters.
"""

from typing import Any, Dict, List, Optional
from app import db
from app.repositories.semester_repo import SemesterRepository
from app.utils.validators import validate_semester_payload
from app.utils.exceptions import NotFoundError, ConflictError


class SemesterService:
    """Service encapsulating business operations on semesters."""

    @staticmethod
    def create_semester(data: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = validate_semester_payload(data, is_update=False)

        # Check unique name
        if SemesterRepository.get_by_name(cleaned["name"]):
            raise ConflictError(f"Semester with name '{cleaned['name']}' already exists.")

        # If marking this semester as active, deactivate previous ones
        if cleaned.get("is_active"):
            SemesterRepository.deactivate_all()

        sem_id = SemesterRepository.create(cleaned)
        return SemesterRepository.get_by_id(sem_id)

    @staticmethod
    def get_semester(semester_id: int) -> Dict[str, Any]:
        semester = SemesterRepository.get_by_id(semester_id)
        if not semester:
            raise NotFoundError(f"Semester with ID {semester_id} not found.")
        return semester

    @staticmethod
    def update_semester(semester_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = SemesterRepository.get_by_id(semester_id)
        if not existing:
            raise NotFoundError(f"Semester with ID {semester_id} not found.")

        cleaned = validate_semester_payload(data, is_update=True)
        if not cleaned:
            return existing

        # Check unique name if changed
        if "name" in cleaned and cleaned["name"] != existing["name"]:
            other = SemesterRepository.get_by_name(cleaned["name"])
            if other and other["id"] != semester_id:
                raise ConflictError(f"Semester with name '{cleaned['name']}' already exists.")

        # If setting active to True, deactivate others first
        if cleaned.get("is_active") is True:
            SemesterRepository.deactivate_all()

        SemesterRepository.update(semester_id, cleaned)
        return SemesterRepository.get_by_id(semester_id)

    @staticmethod
    def set_active(semester_id: int) -> Dict[str, Any]:
        existing = SemesterRepository.get_by_id(semester_id)
        if not existing:
            raise NotFoundError(f"Semester with ID {semester_id} not found.")

        SemesterRepository.deactivate_all()
        SemesterRepository.update(semester_id, {"is_active": True})
        return SemesterRepository.get_by_id(semester_id)

    @staticmethod
    def delete_semester(semester_id: int) -> bool:
        existing = SemesterRepository.get_by_id(semester_id)
        if not existing:
            raise NotFoundError(f"Semester with ID {semester_id} not found.")

        SemesterRepository.delete(semester_id)
        return True

    @staticmethod
    def list_semesters(academic_year: Optional[str] = None, is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
        return SemesterRepository.list_semesters(academic_year=academic_year, is_active=is_active)
