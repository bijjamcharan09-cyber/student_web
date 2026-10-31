"""
Semester repository for data access operations with organisation scoping.
"""

from typing import Any, Dict, List, Optional
from app import db


class SemesterRepository:
    """Repository handling SQL operations for semesters."""

    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        payload = {
            "organisation_id": int(data.get("organisation_id") or 1),
            "name": data.get("name"),
            "semester_number": data.get("semester_number"),
            "academic_year": data.get("academic_year"),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "is_active": data.get("is_active", False),
        }
        sql = """
            INSERT INTO semesters (organisation_id, name, semester_number, academic_year, start_date, end_date, is_active)
            VALUES (%(organisation_id)s, %(name)s, %(semester_number)s, %(academic_year)s, %(start_date)s, %(end_date)s, %(is_active)s)
        """
        return db.execute_insert(sql, payload)

    @staticmethod
    def get_by_id(semester_id: int) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT sem.*, org.name AS organisation_name, org.code AS organisation_code
            FROM semesters sem
            LEFT JOIN organisations org ON sem.organisation_id = org.id
            WHERE sem.id = %s
        """
        return db.query_one(sql, (semester_id,))

    @staticmethod
    def get_by_name(name: str, organisation_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        if organisation_id is not None:
            sql = "SELECT * FROM semesters WHERE name = %s AND organisation_id = %s"
            return db.query_one(sql, (name, organisation_id))
        sql = "SELECT * FROM semesters WHERE name = %s"
        return db.query_one(sql, (name,))

    @staticmethod
    def get_active(organisation_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        if organisation_id is not None:
            sql = "SELECT * FROM semesters WHERE is_active = TRUE AND organisation_id = %s LIMIT 1"
            return db.query_one(sql, (organisation_id,))
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
    def deactivate_all(organisation_id: Optional[int] = None) -> int:
        if organisation_id is not None:
            sql = "UPDATE semesters SET is_active = FALSE WHERE organisation_id = %s"
            return db.execute_update(sql, (organisation_id,))
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
        organisation_id: Optional[int] = None,
        sort_by: Optional[str] = None,
        order: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        conditions = []
        params: List[Any] = []

        if organisation_id is not None:
            conditions.append("organisation_id = %s")
            params.append(organisation_id)

        if academic_year:
            conditions.append("academic_year = %s")
            params.append(academic_year)

        if is_active is not None:
            conditions.append("is_active = %s")
            params.append(is_active)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        sort_map = {
            "semester_number": "semester_number",
            "name": "name",
            "academic_year": "academic_year",
            "start_date": "start_date",
            "end_date": "end_date",
            "is_active": "is_active",
            "id": "id",
        }
        direction = "DESC" if str(order).upper() == "DESC" else "ASC"
        if not sort_by or sort_by not in sort_map:
            order_clause = "ORDER BY academic_year DESC, semester_number ASC"
        else:
            order_clause = f"ORDER BY {sort_map[sort_by]} {direction}"

        sql = f"""
            SELECT * FROM semesters
            {where_clause}
            {order_clause}
        """
        return db.query_all(sql, tuple(params) if params else None)
