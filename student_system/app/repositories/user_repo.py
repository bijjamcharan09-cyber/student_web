"""
User repository for RBAC authentication, credentials, and organisation scoping.
"""

from typing import Any, Dict, List, Optional
from app import db


class UserRepository:
    """Repository handling SQL operations for users."""

    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        payload = {
            "organisation_id": int(data.get("organisation_id") or 1),
            "username": data.get("username"),
            "email": data.get("email"),
            "password_hash": data.get("password_hash"),
            "role": data.get("role", "Student"),
            "student_id": data.get("student_id"),
            "faculty_id": data.get("faculty_id"),
            "is_active": data.get("is_active", True),
        }
        sql = """
            INSERT INTO users (organisation_id, username, email, password_hash, role, student_id, faculty_id, is_active)
            VALUES (%(organisation_id)s, %(username)s, %(email)s, %(password_hash)s, %(role)s, %(student_id)s, %(faculty_id)s, %(is_active)s)
        """
        return db.execute_insert(sql, payload)

    @staticmethod
    def get_by_id(user_id: int) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT u.*,
                   org.name AS organisation_name, org.code AS organisation_code,
                   s.roll_number, s.first_name AS student_first_name, s.last_name AS student_last_name,
                   f.faculty_code, f.first_name AS faculty_first_name, f.last_name AS faculty_last_name, f.department AS faculty_department
            FROM users u
            LEFT JOIN organisations org ON u.organisation_id = org.id
            LEFT JOIN students s ON u.student_id = s.id
            LEFT JOIN faculty f ON u.faculty_id = f.id
            WHERE u.id = %s
        """
        return db.query_one(sql, (user_id,))

    @staticmethod
    def get_by_username(username: str) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT u.*,
                   org.name AS organisation_name, org.code AS organisation_code,
                   s.roll_number, s.first_name AS student_first_name, s.last_name AS student_last_name,
                   f.faculty_code, f.first_name AS faculty_first_name, f.last_name AS faculty_last_name, f.department AS faculty_department
            FROM users u
            LEFT JOIN organisations org ON u.organisation_id = org.id
            LEFT JOIN students s ON u.student_id = s.id
            LEFT JOIN faculty f ON u.faculty_id = f.id
            WHERE u.username = %s
        """
        return db.query_one(sql, (username,))

    @staticmethod
    def get_by_email(email: str) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT u.*, org.name AS organisation_name, org.code AS organisation_code
            FROM users u
            LEFT JOIN organisations org ON u.organisation_id = org.id
            WHERE u.email = %s
        """
        return db.query_one(sql, (email,))

    @staticmethod
    def get_by_student_id(student_id: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM users WHERE student_id = %s"
        return db.query_one(sql, (student_id,))

    @staticmethod
    def get_by_faculty_id(faculty_id: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM users WHERE faculty_id = %s"
        return db.query_one(sql, (faculty_id,))

    @staticmethod
    def update_password(user_id: int, password_hash: str) -> int:
        sql = "UPDATE users SET password_hash = %s WHERE id = %s"
        return db.execute_update(sql, (password_hash, user_id))

    @staticmethod
    def list_users(
        role: Optional[str] = None,
        organisation_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        params: List[Any] = []
        where_clauses: List[str] = []

        if organisation_id is not None:
            where_clauses.append("u.organisation_id = %s")
            params.append(organisation_id)

        if role:
            where_clauses.append("u.role = %s")
            params.append(role)

        where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        sql = f"""
            SELECT u.id, u.organisation_id, u.username, u.email, u.role, u.student_id, u.faculty_id, u.is_active, u.created_at,
                   org.name AS organisation_name, org.code AS organisation_code,
                   s.roll_number, f.faculty_code
            FROM users u
            LEFT JOIN organisations org ON u.organisation_id = org.id
            LEFT JOIN students s ON u.student_id = s.id
            LEFT JOIN faculty f ON u.faculty_id = f.id
            {where}
            ORDER BY u.id DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        return db.query_all(sql, tuple(params))

    @staticmethod
    def update_user(user_id: int, data: Dict[str, Any]) -> int:
        allowed_fields = [
            "username",
            "email",
            "role",
            "is_active",
            "password_hash",
            "student_id",
            "faculty_id",
            "organisation_id",
        ]
        fields = []
        params = {}
        for key, value in data.items():
            if key in allowed_fields:
                fields.append(f"`{key}` = %({key})s")
                params[key] = value

        if not fields:
            return 0

        params["user_id"] = user_id
        sql = f"UPDATE users SET {', '.join(fields)} WHERE id = %(user_id)s"
        return db.execute_update(sql, params)

    @staticmethod
    def delete_user(user_id: int) -> int:
        sql = "DELETE FROM users WHERE id = %s"
        return db.execute_update(sql, (user_id,))

    @staticmethod
    def count_active_admins() -> int:
        sql = "SELECT COUNT(*) as c FROM users WHERE role IN ('Admin', 'Super Admin') AND is_active = 1"
        row = db.query_one(sql)
        return row["c"] if row else 0
