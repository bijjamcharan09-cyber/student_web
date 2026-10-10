"""
Marks and grades repository for data access operations.
"""

from typing import Any, Dict, List, Optional
from app import db


class MarkRepository:
    """Repository handling SQL operations for marks and grades."""

    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        sql = """
            INSERT INTO marks (
                student_id, subject_id, semester_id, exam_type,
                marks_obtained, max_marks, remarks
            ) VALUES (
                %(student_id)s, %(subject_id)s, %(semester_id)s, %(exam_type)s,
                %(marks_obtained)s, %(max_marks)s, %(remarks)s
            )
        """
        return db.execute_insert(sql, data)

    @staticmethod
    def get_by_id(mark_id: int) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT m.*,
                   s.roll_number, s.first_name, s.last_name,
                   sub.subject_code, sub.name AS subject_name, sub.credits,
                   sem.name AS semester_name
            FROM marks m
            JOIN students s ON m.student_id = s.id
            JOIN subjects sub ON m.subject_id = sub.id
            JOIN semesters sem ON m.semester_id = sem.id
            WHERE m.id = %s
        """
        return db.query_one(sql, (mark_id,))

    @staticmethod
    def get_existing(student_id: int, subject_id: int, semester_id: int, exam_type: str) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT * FROM marks
            WHERE student_id = %s AND subject_id = %s AND semester_id = %s AND exam_type = %s
        """
        return db.query_one(sql, (student_id, subject_id, semester_id, exam_type))

    @staticmethod
    def update(mark_id: int, data: Dict[str, Any]) -> int:
        fields = []
        params = {}
        for key, value in data.items():
            fields.append(f"`{key}` = %({key})s")
            params[key] = value

        if not fields:
            return 0

        params["mark_id"] = mark_id
        sql = f"UPDATE marks SET {', '.join(fields)} WHERE id = %(mark_id)s"
        return db.execute_update(sql, params)

    @staticmethod
    def delete(mark_id: int) -> int:
        sql = "DELETE FROM marks WHERE id = %s"
        return db.execute_update(sql, (mark_id,))

    @staticmethod
    def list_marks(
        student_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        semester_id: Optional[int] = None,
        exam_type: Optional[str] = None,
        sort_by: Optional[str] = None,
        order: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conditions = []
        params: List[Any] = []

        if student_id:
            conditions.append("m.student_id = %s")
            params.append(student_id)

        if subject_id:
            conditions.append("m.subject_id = %s")
            params.append(subject_id)

        if semester_id:
            conditions.append("m.semester_id = %s")
            params.append(semester_id)

        if exam_type:
            conditions.append("m.exam_type = %s")
            params.append(exam_type)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        sort_map = {
            "roll_number": "s.roll_number",
            "student_name": "s.first_name",
            "student": "s.roll_number",
            "subject": "sub.name",
            "subject_code": "sub.subject_code",
            "marks_obtained": "m.marks_obtained",
            "marks": "m.marks_obtained",
            "percentage": "(m.marks_obtained / m.max_marks)",
            "exam_type": "m.exam_type",
            "semester": "m.semester_id",
            "id": "m.id",
        }
        direction = "DESC" if str(order).upper() == "DESC" else "ASC"
        if not sort_by or sort_by not in sort_map:
            order_clause = "ORDER BY m.semester_id DESC, sub.subject_code ASC, m.exam_type ASC"
        elif sort_by == "student_name":
            order_clause = f"ORDER BY s.first_name {direction}, s.last_name {direction}"
        else:
            order_clause = f"ORDER BY {sort_map[sort_by]} {direction}"

        sql = f"""
            SELECT m.*,
                   s.roll_number, s.first_name, s.last_name,
                   sub.subject_code, sub.name AS subject_name, sub.credits,
                   sem.name AS semester_name
            FROM marks m
            JOIN students s ON m.student_id = s.id
            JOIN subjects sub ON m.subject_id = sub.id
            JOIN semesters sem ON m.semester_id = sem.id
            {where_clause}
            {order_clause}
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        return db.query_all(sql, tuple(params))

    @staticmethod
    def count_marks(
        student_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        semester_id: Optional[int] = None,
        exam_type: Optional[str] = None,
    ) -> int:
        conditions = []
        params: List[Any] = []

        if student_id:
            conditions.append("m.student_id = %s")
            params.append(student_id)

        if subject_id:
            conditions.append("m.subject_id = %s")
            params.append(subject_id)

        if semester_id:
            conditions.append("m.semester_id = %s")
            params.append(semester_id)

        if exam_type:
            conditions.append("m.exam_type = %s")
            params.append(exam_type)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT COUNT(*) AS total FROM marks m {where_clause}"
        result = db.query_one(sql, tuple(params) if params else None)
        return result["total"] if result else 0
