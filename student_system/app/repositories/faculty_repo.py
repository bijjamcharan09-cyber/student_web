"""
Faculty repository for managing academic staff and course assignments.
"""

from typing import Any, Dict, List, Optional
from app import db


class FacultyRepository:
    """Repository handling SQL operations for faculty and course assignments."""

    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        payload = {
            "faculty_code": data.get("faculty_code"),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "department": data.get("department"),
            "designation": data.get("designation", "Lecturer"),
        }
        sql = """
            INSERT INTO faculty (faculty_code, first_name, last_name, email, phone, department, designation)
            VALUES (%(faculty_code)s, %(first_name)s, %(last_name)s, %(email)s, %(phone)s, %(department)s, %(designation)s)
        """
        return db.execute_insert(sql, payload)

    @staticmethod
    def get_by_id(faculty_id: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM faculty WHERE id = %s"
        return db.query_one(sql, (faculty_id,))

    @staticmethod
    def get_by_code(code: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM faculty WHERE faculty_code = %s"
        return db.query_one(sql, (code,))

    @staticmethod
    def get_by_email(email: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM faculty WHERE email = %s"
        return db.query_one(sql, (email,))

    @staticmethod
    def list_faculty(department: Optional[str] = None) -> List[Dict[str, Any]]:
        params = []
        where = ""
        if department:
            where = "WHERE department = %s"
            params.append(department)
        sql = f"SELECT * FROM faculty {where} ORDER BY last_name ASC, first_name ASC"
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

        sql = f"""
            SELECT id FROM faculty_subjects
            WHERE faculty_id = %s AND subject_id = %s {where_sem}
            LIMIT 1
        """
        row = db.query_one(sql, tuple(params))
        return row is not None

    @staticmethod
    def is_student_taught_by_faculty(faculty_id: int, student_id: int) -> bool:
        """Check if a student is enrolled in ANY subject taught by the faculty member."""
        sql = """
            SELECT ss.id
            FROM student_subjects ss
            JOIN faculty_subjects fs 
              ON ss.subject_id = fs.subject_id AND ss.semester_id = fs.semester_id
            WHERE fs.faculty_id = %s AND ss.student_id = %s
            LIMIT 1
        """
        row = db.query_one(sql, (faculty_id, student_id))
        return row is not None

    @staticmethod
    def update(faculty_id: int, data: Dict[str, Any]) -> int:
        allowed = ["faculty_code", "first_name", "last_name", "email", "phone", "department", "designation"]
        fields = []
        params = {}
        for key, value in data.items():
            if key in allowed:
                fields.append(f"`{key}` = %({key})s")
                params[key] = value

        if not fields:
            return 0

        params["faculty_id"] = faculty_id
        sql = f"UPDATE faculty SET {', '.join(fields)} WHERE id = %(faculty_id)s"
        return db.execute_update(sql, params)

    @staticmethod
    def delete(faculty_id: int) -> int:
        sql = "DELETE FROM faculty WHERE id = %s"
        return db.execute_update(sql, (faculty_id,))

    @staticmethod
    def count_assigned_subjects(faculty_id: int) -> int:
        sql = "SELECT COUNT(*) as c FROM faculty_subjects WHERE faculty_id = %s"
        row = db.query_one(sql, (faculty_id,))
        return row["c"] if row else 0
