"""
Campus Settings and Attendance Session repositories.
"""

from typing import Any, Dict, List, Optional
from app import db


# ─────────────────────────────────────────────────────────────────────────────
# Campus Settings Repository
# ─────────────────────────────────────────────────────────────────────────────

class CampusSettingsRepository:
    """Repository for reading and writing campus_settings rows."""

    @staticmethod
    def get_all() -> List[Dict[str, Any]]:
        return db.query_all("SELECT * FROM campus_settings ORDER BY setting_key ASC", None)

    @staticmethod
    def get(key: str) -> Optional[str]:
        row = db.query_one(
            "SELECT setting_value FROM campus_settings WHERE setting_key = %s",
            (key,)
        )
        return row["setting_value"] if row else None

    @staticmethod
    def get_float(key: str, default: float = 0.0) -> float:
        v = CampusSettingsRepository.get(key)
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def set(key: str, value: str, updated_by: Optional[int] = None) -> None:
        existing = db.query_one(
            "SELECT id FROM campus_settings WHERE setting_key = %s", (key,)
        )
        if existing:
            db.execute_update(
                """UPDATE campus_settings
                   SET setting_value = %s, updated_by = %s
                   WHERE setting_key = %s""",
                (value, updated_by, key),
            )
        else:
            db.execute_insert(
                """INSERT INTO campus_settings (setting_key, setting_value, updated_by)
                   VALUES (%s, %s, %s)""",
                (key, value, updated_by),
            )

    @staticmethod
    def get_campus_config() -> Dict[str, Any]:
        """Return a complete campus configuration dict with typed values."""
        rows = CampusSettingsRepository.get_all()
        cfg: Dict[str, str] = {r["setting_key"]: r["setting_value"] for r in rows}
        return {
            "campus_name":        cfg.get("campus_name", "Vijay Rural Engineering College"),
            "campus_location":    cfg.get("campus_location", "Nizamabad, Telangana, India"),
            "campus_latitude":    float(cfg.get("campus_latitude", "18.9972")),
            "campus_longitude":   float(cfg.get("campus_longitude", "78.2497")),
            "geofence_radius_m":  float(cfg.get("geofence_radius_m", "150")),
            "max_gps_accuracy_m": float(cfg.get("max_gps_accuracy_m", "50")),
            "attendance_enabled": cfg.get("attendance_enabled", "true").lower() == "true",
            # Surface all raw rows for admin display
            "all_settings": rows,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Attendance Session Repository
# ─────────────────────────────────────────────────────────────────────────────

class AttendanceSessionRepository:
    """Repository for CRUD on attendance_sessions."""

    _SESSION_SELECT = """
        SELECT
            s.id, s.subject_id, s.faculty_id, s.semester_id,
            s.session_date, s.start_time, s.end_time, s.is_active,
            s.created_by, s.faculty_lat, s.faculty_lng, s.faculty_accuracy,
            s.notes, s.created_at, s.updated_at,
            sub.name AS subject_name, sub.subject_code, sub.department,
            f.first_name AS faculty_first_name, f.last_name AS faculty_last_name,
            f.faculty_code,
            sem.name AS semester_name, sem.semester_number
        FROM attendance_sessions s
        JOIN subjects  sub ON s.subject_id  = sub.id
        JOIN faculty   f   ON s.faculty_id  = f.id
        JOIN semesters sem ON s.semester_id = sem.id
    """

    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        sql = """
            INSERT INTO attendance_sessions
                (subject_id, faculty_id, semester_id, session_date,
                 start_time, end_time, is_active, created_by,
                 faculty_lat, faculty_lng, faculty_accuracy, notes)
            VALUES
                (%(subject_id)s, %(faculty_id)s, %(semester_id)s, %(session_date)s,
                 %(start_time)s, %(end_time)s, %(is_active)s, %(created_by)s,
                 %(faculty_lat)s, %(faculty_lng)s, %(faculty_accuracy)s, %(notes)s)
        """
        return db.execute_insert(sql, data)

    @staticmethod
    def get_by_id(session_id: int) -> Optional[Dict[str, Any]]:
        sql = AttendanceSessionRepository._SESSION_SELECT + " WHERE s.id = %s"
        return db.query_one(sql, (session_id,))

    @staticmethod
    def list_sessions(
        faculty_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        semester_id: Optional[int] = None,
        session_date: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conditions: List[str] = []
        params: List[Any] = []

        if faculty_id is not None:
            conditions.append("s.faculty_id = %s")
            params.append(faculty_id)
        if subject_id is not None:
            conditions.append("s.subject_id = %s")
            params.append(subject_id)
        if semester_id is not None:
            conditions.append("s.semester_id = %s")
            params.append(semester_id)
        if session_date is not None:
            conditions.append("s.session_date = %s")
            params.append(session_date)
        if is_active is not None:
            conditions.append("s.is_active = %s")
            params.append(1 if is_active else 0)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = (
            AttendanceSessionRepository._SESSION_SELECT
            + f" {where} ORDER BY s.session_date DESC, s.start_time DESC LIMIT %s OFFSET %s"
        )
        params.extend([limit, offset])
        return db.query_all(sql, tuple(params))

    @staticmethod
    def count_sessions(
        faculty_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        semester_id: Optional[int] = None,
    ) -> int:
        conditions: List[str] = []
        params: List[Any] = []
        if faculty_id is not None:
            conditions.append("faculty_id = %s")
            params.append(faculty_id)
        if subject_id is not None:
            conditions.append("subject_id = %s")
            params.append(subject_id)
        if semester_id is not None:
            conditions.append("semester_id = %s")
            params.append(semester_id)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"SELECT COUNT(*) AS total FROM attendance_sessions {where}"
        row = db.query_one(sql, tuple(params) if params else None)
        return row["total"] if row else 0

    @staticmethod
    def deactivate(session_id: int) -> int:
        return db.execute_update(
            "UPDATE attendance_sessions SET is_active = FALSE WHERE id = %s",
            (session_id,),
        )

    @staticmethod
    def get_active_sessions_for_subject(subject_id: int, now_dt: str) -> List[Dict[str, Any]]:
        """Return sessions for a subject that are currently open (start <= now <= end)."""
        sql = (
            AttendanceSessionRepository._SESSION_SELECT
            + """
            WHERE s.subject_id = %s
              AND s.is_active = TRUE
              AND s.start_time <= %s
              AND s.end_time   >= %s
            ORDER BY s.start_time ASC
            """
        )
        return db.query_all(sql, (subject_id, now_dt, now_dt))

    @staticmethod
    def get_session_attendance_count(session_id: int) -> int:
        """Count students who have already marked attendance for this session."""
        row = db.query_one(
            "SELECT COUNT(*) AS total FROM attendance WHERE session_id = %s",
            (session_id,)
        )
        return row["total"] if row else 0

    @staticmethod
    def student_already_marked(student_id: int, session_id: int) -> bool:
        """Return True if the student already has an attendance row for this session."""
        row = db.query_one(
            "SELECT id FROM attendance WHERE student_id = %s AND session_id = %s",
            (student_id, session_id)
        )
        return row is not None
