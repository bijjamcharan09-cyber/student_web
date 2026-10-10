"""
Attendance service handling attendance logging, batch operations, and statistics.
"""

from typing import Any, Dict, List, Optional
import math
from app import db
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.student_repo import StudentRepository
from app.repositories.subject_repo import SubjectRepository
from app.utils.validators import validate_attendance_payload
from app.utils.exceptions import NotFoundError, ConflictError, ValidationError


class AttendanceService:
    """Service encapsulating business operations on student attendance."""

    @staticmethod
    def record_attendance(data: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = validate_attendance_payload(data, is_update=False)

        # Verify existence
        if not StudentRepository.get_by_id(cleaned["student_id"]):
            raise NotFoundError(f"Student with ID {cleaned['student_id']} does not exist.")
        if not SubjectRepository.get_by_id(cleaned["subject_id"]):
            raise NotFoundError(f"Subject with ID {cleaned['subject_id']} does not exist.")

        # Check unique constraint
        existing = AttendanceRepository.get_by_student_subject_date(
            student_id=cleaned["student_id"],
            subject_id=cleaned["subject_id"],
            date_val=cleaned["date"],
        )
        if existing:
            raise ConflictError(
                f"Attendance for student {cleaned['student_id']}, subject {cleaned['subject_id']} "
                f"on {cleaned['date']} has already been recorded."
            )

        att_id = AttendanceRepository.create(cleaned)
        return AttendanceRepository.get_by_id(att_id)

    @staticmethod
    def batch_record_attendance(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Record attendance in batch within an ACID transaction.
        Rolls back completely if any single record is invalid or duplicate.
        """
        if not isinstance(records, list) or len(records) == 0:
            raise ValidationError("Batch attendance payload must be a non-empty list of attendance items.")

        validated_records = []
        for i, item in enumerate(records):
            try:
                cleaned = validate_attendance_payload(item, is_update=False)
                validated_records.append(cleaned)
            except ValidationError as e:
                raise ValidationError(f"Batch item at index {i} invalid: {e.message}", details=e.details)

        inserted_ids = []
        with db.transaction() as cursor:
            for item in validated_records:
                cursor.execute(
                    "SELECT id FROM attendance WHERE student_id = %s AND subject_id = %s AND date = %s",
                    (item["student_id"], item["subject_id"], item["date"]),
                )
                if cursor.fetchone():
                    raise ConflictError(
                        f"Attendance already recorded for student {item['student_id']}, "
                        f"subject {item['subject_id']} on {item['date']}."
                    )

                cursor.execute(
                    """
                    INSERT INTO attendance (student_id, subject_id, date, status, remarks)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (item["student_id"], item["subject_id"], item["date"], item["status"], item["remarks"]),
                )
                inserted_ids.append(cursor.lastrowid)

        results = []
        for aid in inserted_ids:
            rec = AttendanceRepository.get_by_id(aid)
            if rec:
                results.append(rec)
        return results

    @staticmethod
    def get_attendance(attendance_id: int) -> Dict[str, Any]:
        rec = AttendanceRepository.get_by_id(attendance_id)
        if not rec:
            raise NotFoundError(f"Attendance record with ID {attendance_id} not found.")
        return rec

    @staticmethod
    def update_attendance(attendance_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = AttendanceRepository.get_by_id(attendance_id)
        if not existing:
            raise NotFoundError(f"Attendance record with ID {attendance_id} not found.")

        cleaned = validate_attendance_payload(data, is_update=True)
        if not cleaned:
            return existing

        AttendanceRepository.update(attendance_id, cleaned)
        return AttendanceRepository.get_by_id(attendance_id)

    @staticmethod
    def delete_attendance(attendance_id: int) -> bool:
        existing = AttendanceRepository.get_by_id(attendance_id)
        if not existing:
            raise NotFoundError(f"Attendance record with ID {attendance_id} not found.")

        AttendanceRepository.delete(attendance_id)
        return True

    @staticmethod
    def list_attendance(
        student_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
        sort_by: Optional[str] = None,
        order: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> Dict[str, Any]:
        offset = (page - 1) * per_page
        items = AttendanceRepository.list_attendance(
            student_id=student_id,
            subject_id=subject_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
            sort_by=sort_by,
            order=order,
            limit=per_page,
            offset=offset,
        )
        total = AttendanceRepository.count_attendance(
            student_id=student_id,
            subject_id=subject_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
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

    @staticmethod
    def get_student_summary(student_id: int, subject_id: Optional[int] = None) -> Dict[str, Any]:
        student = StudentRepository.get_by_id(student_id)
        if not student:
            raise NotFoundError(f"Student with ID {student_id} not found.")

        stats = AttendanceRepository.get_student_subject_stats(student_id, subject_id)

        total_sessions = 0
        total_present = 0
        total_absent = 0
        total_late = 0
        total_excused = 0

        subject_summaries = []
        for row in stats:
            sessions = int(row["total_sessions"])
            present = int(row["present_count"])
            absent = int(row["absent_count"])
            late = int(row["late_count"])
            excused = int(row["excused_count"])

            total_sessions += sessions
            total_present += present
            total_absent += absent
            total_late += late
            total_excused += excused

            # Present + Excused counts as attended; late counts as 0.5
            effective_attended = present + excused + (0.5 * late)
            pct = round((effective_attended / sessions) * 100, 2) if sessions > 0 else 0.0

            subject_summaries.append({
                "subject_id": row["subject_id"],
                "subject_code": row["subject_code"],
                "subject_name": row["subject_name"],
                "total_sessions": sessions,
                "present": present,
                "absent": absent,
                "late": late,
                "excused": excused,
                "attendance_percentage": pct,
                "is_low_attendance": pct < 75.0,
            })

        overall_effective = total_present + total_excused + (0.5 * total_late)
        overall_pct = (
            round((overall_effective / total_sessions) * 100, 2)
            if total_sessions > 0
            else 0.0
        )

        return {
            "student_id": student["id"],
            "roll_number": student["roll_number"],
            "student_name": f"{student['first_name']} {student['last_name']}",
            "overall_summary": {
                "total_sessions": total_sessions,
                "present": total_present,
                "absent": total_absent,
                "late": total_late,
                "excused": total_excused,
                "attendance_percentage": overall_pct,
                "is_low_attendance": overall_pct < 75.0 and total_sessions > 0,
            },
            "by_subject": subject_summaries,
        }
