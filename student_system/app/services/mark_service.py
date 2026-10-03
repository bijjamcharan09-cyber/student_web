"""
Marks service handling grading, marks recording, transactions, and GPA calculation.
"""

from typing import Any, Dict, List, Optional
import math
from app import db
from app.repositories.mark_repo import MarkRepository
from app.repositories.student_repo import StudentRepository
from app.repositories.subject_repo import SubjectRepository
from app.repositories.semester_repo import SemesterRepository
from app.utils.validators import validate_mark_payload
from app.utils.exceptions import NotFoundError, ConflictError, ValidationError


def compute_grade_and_points(marks_obtained: float, max_marks: float) -> tuple[str, float]:
    """
    Compute percentage, letter grade, and grade points based on JNTUH (10-point scale) insights:
    >= 90%        : O  (Outstanding)   -> 10.0 grade points
    80% to 89.99% : A+ (Excellent)     -> 9.0 grade points
    70% to 79.99% : A  (Very Good)     -> 8.0 grade points
    60% to 69.99% : B+ (Good)          -> 7.0 grade points
    50% to 59.99% : B  (Above Average) -> 6.0 grade points
    40% to 49.99% : C  (Pass)          -> 5.0 grade points
    < 40%         : F  (Fail)          -> 0.0 grade points
    """
    if max_marks <= 0:
        return "F", 0.0

    percentage = round((marks_obtained / max_marks) * 100.0, 2)
    if percentage >= 90:
        return "O", 10.0
    elif percentage >= 80:
        return "A+", 9.0
    elif percentage >= 70:
        return "A", 8.0
    elif percentage >= 60:
        return "B+", 7.0
    elif percentage >= 50:
        return "B", 6.0
    elif percentage >= 40:
        return "C", 5.0
    else:
        return "F", 0.0


def enrich_mark(mark: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich mark record with percentage and calculated grade."""
    if not mark:
        return mark

    obtained = float(mark.get("marks_obtained", 0))
    max_m = float(mark.get("max_marks", 100))
    pct = round((obtained / max_m) * 100, 2) if max_m > 0 else 0.0
    grade, gpa_point = compute_grade_and_points(obtained, max_m)

    enriched = dict(mark)
    enriched["percentage"] = pct
    enriched["grade"] = grade
    enriched["grade_point"] = gpa_point
    return enriched


class MarkService:
    """Service encapsulating business operations on marks and grades."""

    @staticmethod
    def record_mark(data: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = validate_mark_payload(data, is_update=False)

        # Verify existence
        if not StudentRepository.get_by_id(cleaned["student_id"]):
            raise NotFoundError(f"Student with ID {cleaned['student_id']} does not exist.")
        if not SubjectRepository.get_by_id(cleaned["subject_id"]):
            raise NotFoundError(f"Subject with ID {cleaned['subject_id']} does not exist.")
        if not SemesterRepository.get_by_id(cleaned["semester_id"]):
            raise NotFoundError(f"Semester with ID {cleaned['semester_id']} does not exist.")

        # Check unique constraint
        existing = MarkRepository.get_existing(
            student_id=cleaned["student_id"],
            subject_id=cleaned["subject_id"],
            semester_id=cleaned["semester_id"],
            exam_type=cleaned["exam_type"],
        )
        if existing:
            raise ConflictError(
                f"Mark for student {cleaned['student_id']}, subject {cleaned['subject_id']}, "
                f"semester {cleaned['semester_id']}, exam '{cleaned['exam_type']}' already exists."
            )

        mark_id = MarkRepository.create(cleaned)
        return enrich_mark(MarkRepository.get_by_id(mark_id))

    @staticmethod
    def batch_record_marks(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Record multiple marks in an atomic transaction.
        If any single record fails validation or insertion, all are rolled back.
        """
        if not isinstance(records, list) or len(records) == 0:
            raise ValidationError("Batch marks payload must be a non-empty array of mark objects.")

        validated_records = []
        for i, item in enumerate(records):
            try:
                cleaned = validate_mark_payload(item, is_update=False)
                validated_records.append(cleaned)
            except ValidationError as e:
                raise ValidationError(f"Batch item at index {i} invalid: {e.message}", details=e.details)

        inserted_ids = []
        with db.transaction() as cursor:
            for item in validated_records:
                # Check duplicates in DB
                cursor.execute(
                    """
                    SELECT id FROM marks 
                    WHERE student_id = %s AND subject_id = %s AND semester_id = %s AND exam_type = %s
                    """,
                    (item["student_id"], item["subject_id"], item["semester_id"], item["exam_type"]),
                )
                if cursor.fetchone():
                    raise ConflictError(
                        f"Duplicate mark entry found for student {item['student_id']}, "
                        f"subject {item['subject_id']}, exam '{item['exam_type']}'."
                    )

                cursor.execute(
                    """
                    INSERT INTO marks (
                        student_id, subject_id, semester_id, exam_type,
                        marks_obtained, max_marks, remarks
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        item["student_id"],
                        item["subject_id"],
                        item["semester_id"],
                        item["exam_type"],
                        item["marks_obtained"],
                        item["max_marks"],
                        item["remarks"],
                    ),
                )
                inserted_ids.append(cursor.lastrowid)

        # Retrieve and enrich inserted marks
        results = []
        for mid in inserted_ids:
            m = MarkRepository.get_by_id(mid)
            if m:
                results.append(enrich_mark(m))
        return results

    @staticmethod
    def get_mark(mark_id: int) -> Dict[str, Any]:
        mark = MarkRepository.get_by_id(mark_id)
        if not mark:
            raise NotFoundError(f"Mark entry with ID {mark_id} not found.")
        return enrich_mark(mark)

    @staticmethod
    def update_mark(mark_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = MarkRepository.get_by_id(mark_id)
        if not existing:
            raise NotFoundError(f"Mark entry with ID {mark_id} not found.")

        cleaned = validate_mark_payload(data, is_update=True)
        if not cleaned:
            return enrich_mark(existing)

        # Cross validate marks_obtained vs max_marks
        new_max = cleaned.get("max_marks", existing["max_marks"])
        new_obt = cleaned.get("marks_obtained", existing["marks_obtained"])
        if float(new_obt) > float(new_max):
            raise ValidationError(f"Marks obtained ({new_obt}) cannot exceed maximum marks ({new_max}).")

        MarkRepository.update(mark_id, cleaned)
        return enrich_mark(MarkRepository.get_by_id(mark_id))

    @staticmethod
    def delete_mark(mark_id: int) -> bool:
        existing = MarkRepository.get_by_id(mark_id)
        if not existing:
            raise NotFoundError(f"Mark entry with ID {mark_id} not found.")

        MarkRepository.delete(mark_id)
        return True

    @staticmethod
    def list_marks(
        student_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        semester_id: Optional[int] = None,
        exam_type: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> Dict[str, Any]:
        offset = (page - 1) * per_page
        raw_items = MarkRepository.list_marks(
            student_id=student_id,
            subject_id=subject_id,
            semester_id=semester_id,
            exam_type=exam_type,
            limit=per_page,
            offset=offset,
        )
        items = [enrich_mark(m) for m in raw_items]
        total = MarkRepository.count_marks(
            student_id=student_id,
            subject_id=subject_id,
            semester_id=semester_id,
            exam_type=exam_type,
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
