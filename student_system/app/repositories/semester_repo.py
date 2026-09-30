"""
Semester repository for data access operations.
"""

from typing import Any, Dict, List, Optional
from app import db


class SemesterRepository:
    """Repository handling SQL operations for semesters."""

    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        sql = """
            INSERT INTO semesters (name, semester_number, academic_year, start_date, end_date, is_active)
            VALUES (%(name)s, %(semester_number)s, %(academic_year)s, %(start_date)s, %(end_date)s, %(is_active)s)
        """
        return db.execute_insert(sql, data)

    @staticmethod
    def get_by_id(semester_id: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM semesters WHERE id = %s"
        return db.query_one(sql, (semester_id,))

    @staticmethod
    def get_by_name(name: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM semesters WHERE name = %s"
        return db.query_one(sql, (name,))

    @staticmethod
    def get_active() -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM semesters WHERE is_active = TRUE LIMIT 1"
        return db.query_one(sql)

    @staticmethod
    def update(semester_id: int, data: Dict[str, Any]) -> int:
        fields = []
        params = {}
        for key, value in data.items():
            fields.append(f"`{key}` = %({key})s")
            params[key] = value

        if not fields:
            return 0

        params["semester_id"] = semester_id
        sql = f"UPDATE semesters SET {', '.join(fields)} WHERE id = %(semester_id)s"
        return db.execute_update(sql, params)

    @staticmethod
    def deactivate_all() -> int:
        sql = "UPDATE semesters SET is_active = FALSE"
        return db.execute_update(sql)

    @staticmethod
    def delete(semester_id: int) -> int:
        sql = "DELETE FROM semesters WHERE id = %s"
        return db.execute_update(sql, (semester_id,))

    @staticmethod
    def list_semesters(
        academic_year: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        conditions = []
        params: List[Any] = []

        if academic_year:
            conditions.append("academic_year = %s")
            params.append(academic_year)

        if is_active is not None:
            conditions.append("is_active = %s")
            params.append(is_active)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
            SELECT * FROM semesters
            {where_clause}
            ORDER BY academic_year DESC, semester_number ASC
        """
        return db.query_all(sql, tuple(params) if params else None)
