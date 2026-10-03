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

        from app import db
        sub_count = db.query_one("SELECT COUNT(*) as c FROM subjects WHERE semester_id = %s", (semester_id,))
        sc = sub_count["c"] if sub_count else 0

        stu_count = db.query_one("SELECT COUNT(*) as c FROM students WHERE current_semester_id = %s", (semester_id,))
        stuc = stu_count["c"] if stu_count else 0

        mark_count = db.query_one("SELECT COUNT(*) as c FROM marks WHERE semester_id = %s", (semester_id,))
        mc = mark_count["c"] if mark_count else 0

        ss_count = db.query_one("SELECT COUNT(*) as c FROM student_subjects WHERE semester_id = %s", (semester_id,))
        ssc = ss_count["c"] if ss_count else 0

        fs_count = db.query_one("SELECT COUNT(*) as c FROM faculty_subjects WHERE semester_id = %s", (semester_id,))
        fsc = fs_count["c"] if fs_count else 0

        if sc > 0 or stuc > 0 or mc > 0 or ssc > 0 or fsc > 0:
            reasons = []
            if sc:
                reasons.append(f"{sc} curriculum subject(s)")
            if stuc:
                reasons.append(f"{stuc} assigned student(s)")
            if mc:
                reasons.append(f"{mc} academic mark record(s)")
            if ssc:
                reasons.append(f"{ssc} student enrollment(s)")
            if fsc:
                reasons.append(f"{fsc} faculty course assignment(s)")
            raise ConflictError(
                f"Cannot delete semester: Semester contains linked records ({', '.join(reasons)}). "
                f"Please resolve or archive related records before deleting."
            )

        SemesterRepository.delete(semester_id)
        return True

    @staticmethod
    def list_semesters(academic_year: Optional[str] = None, is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
        return SemesterRepository.list_semesters(academic_year=academic_year, is_active=is_active)
