"""
Attendance repository for data access operations.
"""

from typing import Any, Dict, List, Optional
from app import db


class AttendanceRepository:
    """Repository handling SQL operations for student attendance."""

    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        sql = """
            INSERT INTO attendance (student_id, subject_id, date, status, remarks)
            VALUES (%(student_id)s, %(subject_id)s, %(date)s, %(status)s, %(remarks)s)
        """
        return db.execute_insert(sql, data)

    @staticmethod
    def get_by_id(attendance_id: int) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT a.*,
                   s.roll_number, s.first_name, s.last_name,
                   sub.subject_code, sub.name AS subject_name
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            JOIN subjects sub ON a.subject_id = sub.id
            WHERE a.id = %s
        """
        return db.query_one(sql, (attendance_id,))

    @staticmethod
    def get_by_student_subject_date(student_id: int, subject_id: int, date_val: str) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT * FROM attendance
            WHERE student_id = %s AND subject_id = %s AND date = %s
        """
        return db.query_one(sql, (student_id, subject_id, date_val))

    @staticmethod
    def update(attendance_id: int, data: Dict[str, Any]) -> int:
        fields = []
        params = {}
        for key, value in data.items():
            fields.append(f"`{key}` = %({key})s")
            params[key] = value

        if not fields:
            return 0

        params["attendance_id"] = attendance_id
        sql = f"UPDATE attendance SET {', '.join(fields)} WHERE id = %(attendance_id)s"
        return db.execute_update(sql, params)

    @staticmethod
    def delete(attendance_id: int) -> int:
        sql = "DELETE FROM attendance WHERE id = %s"
        return db.execute_update(sql, (attendance_id,))

    @staticmethod
    def list_attendance(
        student_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conditions = []
        params: List[Any] = []

        if student_id:
            conditions.append("a.student_id = %s")
            params.append(student_id)

        if subject_id:
            conditions.append("a.subject_id = %s")
            params.append(subject_id)

        if date_from:
            conditions.append("a.date >= %s")
            params.append(date_from)

        if date_to:
            conditions.append("a.date <= %s")
            params.append(date_to)

        if status:
            conditions.append("a.status = %s")
            params.append(status)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        sql = f"""
            SELECT a.*,
                   s.roll_number, s.first_name, s.last_name,
                   sub.subject_code, sub.name AS subject_name
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            JOIN subjects sub ON a.subject_id = sub.id
            {where_clause}
            ORDER BY a.date DESC, a.id DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        return db.query_all(sql, tuple(params))

    @staticmethod
    def count_attendance(
        student_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        conditions = []
        params: List[Any] = []

        if student_id:
            conditions.append("a.student_id = %s")
            params.append(student_id)

        if subject_id:
            conditions.append("a.subject_id = %s")
            params.append(subject_id)

        if date_from:
            conditions.append("a.date >= %s")
            params.append(date_from)

        if date_to:
            conditions.append("a.date <= %s")
            params.append(date_to)

        if status:
            conditions.append("a.status = %s")
            params.append(status)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT COUNT(*) AS total FROM attendance a {where_clause}"
        result = db.query_one(sql, tuple(params) if params else None)
        return result["total"] if result else 0

    @staticmethod
    def get_student_subject_stats(student_id: int, subject_id: Optional[int] = None) -> List[Dict[str, Any]]:
        conditions = ["a.student_id = %s"]
        params = [student_id]

        if subject_id:
            conditions.append("a.subject_id = %s")
            params.append(subject_id)

        sql = f"""
            SELECT 
                a.subject_id,
                sub.subject_code,
                sub.name AS subject_name,
                COUNT(*) AS total_sessions,
                SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count,
                SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
                SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) AS late_count,
                SUM(CASE WHEN a.status = 'Excused' THEN 1 ELSE 0 END) AS excused_count
            FROM attendance a
            JOIN subjects sub ON a.subject_id = sub.id
            WHERE {' AND '.join(conditions)}
            GROUP BY a.subject_id, sub.subject_code, sub.name
            ORDER BY sub.subject_code ASC
        """
        return db.query_all(sql, tuple(params))
