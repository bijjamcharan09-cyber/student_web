"""
Subject repository for data access operations.
"""

from typing import Any, Dict, List, Optional
from app import db


class SubjectRepository:
    """Repository handling SQL operations for subjects."""

    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        sql = """
            INSERT INTO subjects (subject_code, name, credits, department, semester_id)
            VALUES (%(subject_code)s, %(name)s, %(credits)s, %(department)s, %(semester_id)s)
        """
        return db.execute_insert(sql, data)

    @staticmethod
    def get_by_id(subject_id: int) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT sub.*, sem.name AS semester_name, sem.semester_number
            FROM subjects sub
            LEFT JOIN semesters sem ON sub.semester_id = sem.id
            WHERE sub.id = %s
        """
        return db.query_one(sql, (subject_id,))

    @staticmethod
    def get_by_code(code: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM subjects WHERE subject_code = %s"
        return db.query_one(sql, (code,))

    @staticmethod
    def update(subject_id: int, data: Dict[str, Any]) -> int:
        fields = []
        params = {}
        for key, value in data.items():
            fields.append(f"`{key}` = %({key})s")
            params[key] = value

        if not fields:
            return 0

        params["subject_id"] = subject_id
        sql = f"UPDATE subjects SET {', '.join(fields)} WHERE id = %(subject_id)s"
        return db.execute_update(sql, params)

    @staticmethod
    def delete(subject_id: int) -> int:
        sql = "DELETE FROM subjects WHERE id = %s"
        return db.execute_update(sql, (subject_id,))

    @staticmethod
    def list_subjects(
        department: Optional[str] = None,
        semester_id: Optional[int] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        order: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conditions = []
        params: List[Any] = []

        if department:
            conditions.append("sub.department = %s")
            params.append(department)

        if semester_id:
            conditions.append("sub.semester_id = %s")
            params.append(semester_id)

        if search:
            search_param = f"%{search}%"
            conditions.append("(sub.subject_code LIKE %s OR sub.name LIKE %s)")
            params.extend([search_param, search_param])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        sort_map = {
            "subject_code": "sub.subject_code",
            "name": "sub.name",
            "department": "sub.department",
            "credits": "sub.credits",
            "semester": "sem.semester_number",
            "id": "sub.id",
        }
        direction = "DESC" if str(order).upper() == "DESC" else "ASC"
        order_col = sort_map.get(sort_by, "sub.subject_code")
        order_clause = f"ORDER BY {order_col} {direction}"

        sql = f"""
            SELECT sub.*, sem.name AS semester_name, sem.semester_number
            FROM subjects sub
            LEFT JOIN semesters sem ON sub.semester_id = sem.id
            {where_clause}
            {order_clause}
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        return db.query_all(sql, tuple(params))

    @staticmethod
    def count_subjects(
        department: Optional[str] = None,
        semester_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> int:
        conditions = []
        params: List[Any] = []

        if department:
            conditions.append("sub.department = %s")
            params.append(department)

        if semester_id:
            conditions.append("sub.semester_id = %s")
            params.append(semester_id)

        if search:
            search_param = f"%{search}%"
            conditions.append("(sub.subject_code LIKE %s OR sub.name LIKE %s)")
            params.extend([search_param, search_param])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT COUNT(*) AS total FROM subjects sub {where_clause}"
        result = db.query_one(sql, tuple(params) if params else None)
        return result["total"] if result else 0
