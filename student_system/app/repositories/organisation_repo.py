"""
Organisation repository for multi-tenancy and institution management.
"""

from typing import Any, Dict, List, Optional
from app import db


class OrganisationRepository:
    """Repository handling SQL operations for organisations."""

    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        payload = {
            "name": data.get("name"),
            "code": str(data.get("code", "")).strip().upper(),
            "status": data.get("status", "Active"),
        }
        sql = """
            INSERT INTO organisations (name, code, status)
            VALUES (%(name)s, %(code)s, %(status)s)
        """
        return db.execute_insert(sql, payload)

    @staticmethod
    def get_by_id(org_id: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM organisations WHERE id = %s"
        return db.query_one(sql, (org_id,))

    @staticmethod
    def get_by_code(code: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM organisations WHERE code = %s"
        return db.query_one(sql, (str(code).strip().upper(),))

    @staticmethod
    def list_all(status: Optional[str] = None) -> List[Dict[str, Any]]:
        params = []
        where = ""
        if status:
            where = "WHERE status = %s"
            params.append(status)
        sql = f"SELECT * FROM organisations {where} ORDER BY id ASC"
        return db.query_all(sql, tuple(params) if params else None)

    @staticmethod
    def update(org_id: int, data: Dict[str, Any]) -> int:
        allowed_fields = ["name", "code", "status"]
        fields = []
        params = {}
        for key, value in data.items():
            if key in allowed_fields:
                fields.append(f"`{key}` = %({key})s")
                params[key] = value.upper() if key == "code" else value

        if not fields:
            return 0

        params["org_id"] = org_id
        sql = f"UPDATE organisations SET {', '.join(fields)} WHERE id = %(org_id)s"
        return db.execute_update(sql, params)

    @staticmethod
    def delete(org_id: int) -> int:
        sql = "DELETE FROM organisations WHERE id = %s"
        return db.execute_update(sql, (org_id,))
