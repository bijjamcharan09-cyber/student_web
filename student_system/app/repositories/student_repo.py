"""
Student repository for data access operations.
"""

from typing import Any, Dict, List, Optional
from app import db


class StudentRepository:
    """Repository handling SQL operations for students."""

    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        payload = {
            "roll_number": data.get("roll_number"),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "date_of_birth": data.get("date_of_birth"),
            "gender": data.get("gender"),
            "current_semester_id": data.get("current_semester_id"),
            "enrollment_date": data.get("enrollment_date"),
            "status": data.get("status", "Active"),
            "address": data.get("address"),
        }
        sql = """
            INSERT INTO students (
                roll_number, first_name, last_name, email, phone,
                date_of_birth, gender, current_semester_id, enrollment_date,
                status, address
            ) VALUES (
                %(roll_number)s, %(first_name)s, %(last_name)s, %(email)s, %(phone)s,
                %(date_of_birth)s, %(gender)s, %(current_semester_id)s, %(enrollment_date)s,
                %(status)s, %(address)s
            )
        """
        return db.execute_insert(sql, payload)

    @staticmethod
    def get_by_id(student_id: int) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT s.*, 
                   sem.name AS current_semester_name,
                   sem.semester_number AS current_semester_number
            FROM students s
            LEFT JOIN semesters sem ON s.current_semester_id = sem.id
            WHERE s.id = %s
        """
        return db.query_one(sql, (student_id,))

    @staticmethod
    def get_by_roll_number(roll_number: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM students WHERE roll_number = %s"
        return db.query_one(sql, (roll_number,))

    @staticmethod
    def get_by_email(email: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM students WHERE email = %s"
        return db.query_one(sql, (email,))

    @staticmethod
    def update(student_id: int, data: Dict[str, Any]) -> int:
        fields = []
        params = {}
        for key, value in data.items():
            fields.append(f"`{key}` = %({key})s")
            params[key] = value

        if not fields:
            return 0

        params["student_id"] = student_id
        sql = f"UPDATE students SET {', '.join(fields)} WHERE id = %(student_id)s"
        return db.execute_update(sql, params)

    @staticmethod
    def delete(student_id: int) -> int:
        sql = "DELETE FROM students WHERE id = %s"
        return db.execute_update(sql, (student_id,))

    @staticmethod
    def list_students(
        search: Optional[str] = None,
        status: Optional[str] = None,
        semester_id: Optional[int] = None,
        sort_by: Optional[str] = None,
        order: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conditions = []
        params: List[Any] = []

        if search:
            search_param = f"%{search}%"
            conditions.append(
                "(s.roll_number LIKE %s OR s.first_name LIKE %s OR s.last_name LIKE %s OR s.email LIKE %s)"
            )
            params.extend([search_param, search_param, search_param, search_param])

        if status:
            conditions.append("s.status = %s")
            params.append(status)

        if semester_id:
            conditions.append("s.current_semester_id = %s")
            params.append(semester_id)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Whitelist sorting fields
        sort_map = {
            "roll_number": "s.roll_number",
            "name": "s.first_name",
            "first_name": "s.first_name",
            "last_name": "s.last_name",
            "email": "s.email",
            "semester": "sem.semester_number",
            "status": "s.status",
            "id": "s.id",
        }
        direction = "DESC" if str(order).upper() == "DESC" else "ASC"
        if not sort_by or sort_by not in sort_map:
            order_clause = "ORDER BY s.id DESC"
        elif sort_by in ("name", "first_name"):
            order_clause = f"ORDER BY s.first_name {direction}, s.last_name {direction}"
        else:
            order_clause = f"ORDER BY {sort_map[sort_by]} {direction}"

        sql = f"""
            SELECT s.*, 
                   sem.name AS current_semester_name,
                   sem.semester_number AS current_semester_number
            FROM students s
            LEFT JOIN semesters sem ON s.current_semester_id = sem.id
            {where_clause}
            {order_clause}
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        return db.query_all(sql, tuple(params))

    @staticmethod
    def count_students(
        search: Optional[str] = None,
        status: Optional[str] = None,
        semester_id: Optional[int] = None,
    ) -> int:
        conditions = []
        params: List[Any] = []

        if search:
            search_param = f"%{search}%"
            conditions.append(
                "(s.roll_number LIKE %s OR s.first_name LIKE %s OR s.last_name LIKE %s OR s.email LIKE %s)"
            )
            params.extend([search_param, search_param, search_param, search_param])

        if status:
            conditions.append("s.status = %s")
            params.append(status)

        if semester_id:
            conditions.append("s.current_semester_id = %s")
            params.append(semester_id)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT COUNT(*) AS total FROM students s {where_clause}"
        result = db.query_one(sql, tuple(params) if params else None)
        return result["total"] if result else 0

    @staticmethod
    def enroll_subject(student_id: int, subject_id: int, semester_id: int) -> int:
        sql = """
            INSERT INTO student_subjects (student_id, subject_id, semester_id)
            VALUES (%s, %s, %s)
        """
        return db.execute_insert(sql, (student_id, subject_id, semester_id))

    @staticmethod
    def unenroll_subject(student_id: int, subject_id: int, semester_id: int) -> int:
        sql = """
            DELETE FROM student_subjects 
            WHERE student_id = %s AND subject_id = %s AND semester_id = %s
        """
        return db.execute_update(sql, (student_id, subject_id, semester_id))

    @staticmethod
    def get_enrolled_subjects(student_id: int, semester_id: Optional[int] = None) -> List[Dict[str, Any]]:
        conditions = ["ss.student_id = %s"]
        params = [student_id]
        if semester_id:
            conditions.append("ss.semester_id = %s")
            params.append(semester_id)

        sql = f"""
            SELECT sub.*, ss.semester_id, sem.name AS semester_name, ss.enrolled_at
            FROM student_subjects ss
            JOIN subjects sub ON ss.subject_id = sub.id
            JOIN semesters sem ON ss.semester_id = sem.id
            WHERE {' AND '.join(conditions)}
            ORDER BY sub.subject_code ASC
        """
        return db.query_all(sql, tuple(params))
