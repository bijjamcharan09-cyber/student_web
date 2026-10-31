"""
Faculty repository for managing academic staff and course assignments with organisation scoping.
"""

from typing import Any, Dict, List, Optional
from app import db


class FacultyRepository:
    """Repository handling SQL operations for faculty and course assignments."""

    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        payload = {
            "organisation_id": int(data.get("organisation_id") or 1),
            "faculty_code": data.get("faculty_code"),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "department": data.get("department"),
            "designation": data.get("designation", "Lecturer"),
        }
        sql = """
            INSERT INTO faculty (organisation_id, faculty_code, first_name, last_name, email, phone, department, designation)
            VALUES (%(organisation_id)s, %(faculty_code)s, %(first_name)s, %(last_name)s, %(email)s, %(phone)s, %(department)s, %(designation)s)
        """
        return db.execute_insert(sql, payload)

    @staticmethod
    def get_by_id(faculty_id: int) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT f.*, org.name AS organisation_name, org.code AS organisation_code
            FROM faculty f
            LEFT JOIN organisations org ON f.organisation_id = org.id
            WHERE f.id = %s
        """
        return db.query_one(sql, (faculty_id,))

    @staticmethod
    def get_by_code(code: str, organisation_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        if organisation_id is not None:
            sql = "SELECT * FROM faculty WHERE faculty_code = %s AND organisation_id = %s"
            return db.query_one(sql, (code, organisation_id))
        sql = "SELECT * FROM faculty WHERE faculty_code = %s"
        return db.query_one(sql, (code,))

    @staticmethod
    def get_by_email(email: str, organisation_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        if organisation_id is not None:
            sql = "SELECT * FROM faculty WHERE email = %s AND organisation_id = %s"
            return db.query_one(sql, (email, organisation_id))
        sql = "SELECT * FROM faculty WHERE email = %s"
        return db.query_one(sql, (email,))

    @staticmethod
    def list_faculty(
        department: Optional[str] = None,
        organisation_id: Optional[int] = None,
        sort_by: Optional[str] = None,
        order: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params = []
        where_clauses = []
        if organisation_id is not None:
            where_clauses.append("organisation_id = %s")
            params.append(organisation_id)
        if department:
            where_clauses.append("department = %s")
            params.append(department)

        where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        sort_map = {
            "faculty_code": "faculty_code",
            "name": "first_name",
            "first_name": "first_name",
            "last_name": "last_name",
            "department": "department",
            "designation": "designation",
            "email": "email",
            "id": "id",
        }
        direction = "DESC" if str(order).upper() == "DESC" else "ASC"
        if not sort_by or sort_by not in sort_map:
            order_clause = "ORDER BY last_name ASC, first_name ASC"
        elif sort_by in ("name", "first_name"):
            order_clause = f"ORDER BY first_name {direction}, last_name {direction}"
        else:
            order_clause = f"ORDER BY {sort_map[sort_by]} {direction}"

        sql = f"SELECT * FROM faculty {where} {order_clause}"
        return db.query_all(sql, tuple(params) if params else None)

    @staticmethod
    def assign_subject(faculty_id: int, subject_id: int, semester_id: int) -> int:
        sql = """
            INSERT INTO faculty_subjects (faculty_id, subject_id, semester_id)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE assigned_at = CURRENT_TIMESTAMP
        """
        return db.execute_insert(sql, (faculty_id, subject_id, semester_id))

    @staticmethod
    def get_assigned_subjects(faculty_id: int, semester_id: Optional[int] = None) -> List[Dict[str, Any]]:
        params = [faculty_id]
        where_sem = ""
        if semester_id:
            where_sem = "AND fs.semester_id = %s"
            params.append(semester_id)

        sql = f"""
            SELECT sub.*, sem.name AS semester_name, sem.academic_year, fs.assigned_at
            FROM faculty_subjects fs
            JOIN subjects sub ON fs.subject_id = sub.id
            JOIN semesters sem ON fs.semester_id = sem.id
            WHERE fs.faculty_id = %s {where_sem}
            ORDER BY sub.subject_code ASC
        """
        return db.query_all(sql, tuple(params))

    @staticmethod
    def is_faculty_assigned_to_subject(faculty_id: int, subject_id: int, semester_id: Optional[int] = None) -> bool:
        params = [faculty_id, subject_id]
        where_sem = ""
        if semester_id:
            where_sem = "AND semester_id = %s"
            params.append(semester_id)

        sql = f"SELECT 1 FROM faculty_subjects WHERE faculty_id = %s AND subject_id = %s {where_sem} LIMIT 1"
        row = db.query_one(sql, tuple(params))
        return row is not None

    @staticmethod
    def is_student_taught_by_faculty(faculty_id: int, student_id: int) -> bool:
        sql = """
            SELECT 1
            FROM faculty_subjects fs
            JOIN student_subjects ss ON fs.subject_id = ss.subject_id AND fs.semester_id = ss.semester_id
            WHERE fs.faculty_id = %s AND ss.student_id = %s
            LIMIT 1
        """
        row = db.query_one(sql, (faculty_id, student_id))
        return row is not None
