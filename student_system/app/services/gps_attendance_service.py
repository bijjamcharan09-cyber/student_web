"""
GPS Attendance Service — Session management, geofence validation, and
student self-attendance with server-side enforcement.

Key responsibilities:
  - Compute Haversine distance between two GPS points.
  - Validate student/faculty GPS coordinates against campus geofence.
  - Enforce session timing rules using server-authoritative UTC.
  - Create and close attendance sessions (faculty).
  - Mark student attendance with full audit trail.
  - NEVER trust client-provided role, identity, or timestamps.
"""

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app import db
from app.repositories.gps_attendance_repo import (
    AttendanceSessionRepository,
    CampusSettingsRepository,
)
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.student_repo import StudentRepository
from app.repositories.faculty_repo import FacultyRepository
from app.repositories.subject_repo import SubjectRepository
from app.utils.exceptions import (
    ValidationError,
    ForbiddenError,
    NotFoundError,
    ConflictError,
)


# ─────────────────────────────────────────────────────────────────────────────
# Haversine formula
# ─────────────────────────────────────────────────────────────────────────────

EARTH_RADIUS_M = 6_371_000  # metres


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Return the great-circle distance in metres between two GPS coordinates
    using the Haversine formula.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _parse_coords(lat: Any, lng: Any, label: str = "Coordinates") -> Tuple[float, float]:
    """Parse and range-check a lat/lng pair; raise ValidationError on failure."""
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        raise ValidationError(f"{label}: latitude and longitude must be numeric.")

    if not (-90 <= lat_f <= 90):
        raise ValidationError(f"{label}: latitude {lat_f} is out of range [-90, 90].")
    if not (-180 <= lng_f <= 180):
        raise ValidationError(f"{label}: longitude {lng_f} is out of range [-180, 180].")

    return lat_f, lng_f


def _server_utc_now() -> datetime:
    """Return the current server time in UTC. Client clock is never used."""
    return datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC for MySQL storage


# ─────────────────────────────────────────────────────────────────────────────
# Coordinate validation helper
# ─────────────────────────────────────────────────────────────────────────────

def validate_location(
    lat: Any,
    lng: Any,
    accuracy: Any,
    *,
    campus_lat: Optional[float] = None,
    campus_lng: Optional[float] = None,
    geofence_radius_m: Optional[float] = None,
    max_accuracy_m: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Validate a GPS coordinate against campus geofence rules.

    Returns a dict with:
      ok            bool   — True if all checks pass
      distance_m    float  — metres from campus centre
      inside_fence  bool
      accuracy_ok   bool
      message       str    — human-readable result
      lat / lng     float  — echoed back (server-validated)
    """
    # Load campus config if not supplied
    cfg = CampusSettingsRepository.get_campus_config()
    c_lat = campus_lat if campus_lat is not None else cfg["campus_latitude"]
    c_lng = campus_lng if campus_lng is not None else cfg["campus_longitude"]
    radius = geofence_radius_m if geofence_radius_m is not None else cfg["geofence_radius_m"]
    max_acc = max_accuracy_m if max_accuracy_m is not None else cfg["max_gps_accuracy_m"]

    # Parse and range-check coordinates
    user_lat, user_lng = _parse_coords(lat, lng, "User coordinates")

    # Validate accuracy
    try:
        acc_f = float(accuracy)
    except (TypeError, ValueError):
        raise ValidationError("GPS accuracy must be a numeric value in metres.")

    if acc_f < 0:
        raise ValidationError("GPS accuracy cannot be negative.")

    accuracy_ok = acc_f <= max_acc

    # Compute Haversine distance
    dist_m = haversine_distance(user_lat, user_lng, c_lat, c_lng)
    inside_fence = dist_m <= radius

    if not accuracy_ok:
        msg = (
            f"GPS accuracy ({acc_f:.1f} m) exceeds the allowed threshold ({max_acc:.0f} m). "
            "Please try again in an open area with better signal."
        )
    elif not inside_fence:
        msg = (
            f"You are approximately {dist_m:.0f} m from campus "
            f"({cfg['campus_name']}). You must be within {radius:.0f} m to mark attendance."
        )
    else:
        msg = f"Location verified. You are within campus ({dist_m:.0f} m from centre)."

    return {
        "ok": accuracy_ok and inside_fence,
        "lat": user_lat,
        "lng": user_lng,
        "accuracy_m": acc_f,
        "distance_m": round(dist_m, 2),
        "inside_fence": inside_fence,
        "accuracy_ok": accuracy_ok,
        "campus_lat": c_lat,
        "campus_lng": c_lng,
        "geofence_radius_m": radius,
        "max_accuracy_m": max_acc,
        "message": msg,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GPS Attendance Service
# ─────────────────────────────────────────────────────────────────────────────

class GpsAttendanceService:
    """Business logic for GPS-verified attendance sessions."""

    # ── Campus settings ───────────────────────────────────────────────────────

    @staticmethod
    def get_campus_config() -> Dict[str, Any]:
        return CampusSettingsRepository.get_campus_config()

    @staticmethod
    def update_campus_settings(payload: Dict[str, Any], admin_user_id: int) -> Dict[str, Any]:
        """
        Allow an Admin to update campus_settings.
        Only whitelisted keys are accepted.
        """
        ALLOWED_KEYS = {
            "campus_latitude", "campus_longitude",
            "geofence_radius_m", "max_gps_accuracy_m",
            "campus_name", "campus_location", "attendance_enabled",
        }
        updated = []
        for key, value in payload.items():
            if key not in ALLOWED_KEYS:
                raise ValidationError(f"Unknown setting key: '{key}'.")
            if key in ("campus_latitude",):
                v, _ = _parse_coords(value, 0.0, "Campus latitude")
                value = str(round(v, 7))
            elif key in ("campus_longitude",):
                _, v = _parse_coords(0.0, value, "Campus longitude")
                value = str(round(float(value), 7))
            elif key in ("geofence_radius_m", "max_gps_accuracy_m"):
                try:
                    fv = float(value)
                except (TypeError, ValueError):
                    raise ValidationError(f"'{key}' must be a positive number.")
                if fv <= 0:
                    raise ValidationError(f"'{key}' must be greater than zero.")
                value = str(round(fv, 2))
            elif key == "attendance_enabled":
                value = "true" if str(value).lower() in ("true", "1", "yes") else "false"

            CampusSettingsRepository.set(key, str(value), updated_by=admin_user_id)
            updated.append(key)

        return {"updated_keys": updated, **GpsAttendanceService.get_campus_config()}

    # ── Location validation (public helper) ───────────────────────────────────

    @staticmethod
    def check_location(lat: Any, lng: Any, accuracy: Any) -> Dict[str, Any]:
        """Validate coordinates against current campus config. No DB writes."""
        return validate_location(lat, lng, accuracy)

    # ── Session management (faculty) ──────────────────────────────────────────

    @staticmethod
    def create_session(payload: Dict[str, Any], faculty_user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Faculty creates an attendance session for their assigned subject.
        Faculty location is validated against campus geofence before creation.
        """
        faculty_id = faculty_user.get("faculty_id")
        if not faculty_id:
            raise ForbiddenError("Faculty profile not linked to this account.")

        # Required fields
        subject_id = payload.get("subject_id")
        semester_id = payload.get("semester_id")
        start_time_str = payload.get("start_time")  # ISO 8601 string
        end_time_str = payload.get("end_time")
        lat = payload.get("latitude")
        lng = payload.get("longitude")
        accuracy = payload.get("accuracy", 999)

        if not all([subject_id, semester_id, start_time_str, end_time_str]):
            raise ValidationError(
                "Required: subject_id, semester_id, start_time, end_time."
            )

        # Verify faculty is assigned to this subject
        if not FacultyRepository.is_faculty_assigned_to_subject(faculty_id, int(subject_id), int(semester_id)):
            raise ForbiddenError(
                "You are not assigned to teach this subject in the specified semester."
            )

        # Verify subject exists
        subject = SubjectRepository.get_by_id(int(subject_id))
        if not subject:
            raise NotFoundError(f"Subject {subject_id} not found.")

        # Validate faculty GPS location
        geo = validate_location(lat, lng, accuracy)
        if not geo["ok"]:
            raise ForbiddenError(
                f"Cannot create session: {geo['message']}"
            )

        # Parse times
        try:
            start_dt = datetime.fromisoformat(start_time_str.replace("Z", "+00:00")).replace(tzinfo=None)
            end_dt = datetime.fromisoformat(end_time_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            raise ValidationError("start_time and end_time must be valid ISO 8601 datetime strings.")

        now = _server_utc_now()
        if end_dt <= start_dt:
            raise ValidationError("end_time must be after start_time.")
        if end_dt <= now:
            raise ValidationError("Session end_time must be in the future.")

        session_date = start_dt.date().isoformat()

        session_id = AttendanceSessionRepository.create({
            "subject_id": int(subject_id),
            "faculty_id": faculty_id,
            "semester_id": int(semester_id),
            "session_date": session_date,
            "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "is_active": True,
            "created_by": faculty_user["id"],
            "faculty_lat": round(geo["lat"], 7),
            "faculty_lng": round(geo["lng"], 7),
            "faculty_accuracy": round(geo["accuracy_m"], 2),
            "notes": str(payload.get("notes", ""))[:255] or None,
        })

        return AttendanceSessionRepository.get_by_id(session_id)

    @staticmethod
    def close_session(session_id: int, faculty_user: Dict[str, Any]) -> Dict[str, Any]:
        """Faculty or Admin closes an attendance session early."""
        session = AttendanceSessionRepository.get_by_id(session_id)
        if not session:
            raise NotFoundError(f"Session {session_id} not found.")

        role = faculty_user.get("role", "")
        if role == "Faculty":
            if session["faculty_id"] != faculty_user.get("faculty_id"):
                raise ForbiddenError("You can only close your own sessions.")
        elif role != "Admin":
            raise ForbiddenError("Only Faculty or Admin can close sessions.")

        AttendanceSessionRepository.deactivate(session_id)
        return {**session, "is_active": False}

    @staticmethod
    def list_sessions(
        faculty_user: Optional[Dict[str, Any]] = None,
        subject_id: Optional[int] = None,
        semester_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        faculty_id = None
        if faculty_user and faculty_user.get("role") == "Faculty":
            faculty_id = faculty_user.get("faculty_id")

        offset = (page - 1) * per_page
        items = AttendanceSessionRepository.list_sessions(
            faculty_id=faculty_id,
            subject_id=subject_id,
            semester_id=semester_id,
            is_active=is_active,
            limit=per_page,
            offset=offset,
        )
        total = AttendanceSessionRepository.count_sessions(
            faculty_id=faculty_id,
            subject_id=subject_id,
            semester_id=semester_id,
        )
        total_pages = math.ceil(total / per_page) if total > 0 else 1

        # Attach attendance count to each session
        now = _server_utc_now()
        for s in items:
            s["attendance_count"] = AttendanceSessionRepository.get_session_attendance_count(s["id"])
            s["is_currently_open"] = (
                s["is_active"]
                and datetime.fromisoformat(str(s["start_time"])) <= now
                and datetime.fromisoformat(str(s["end_time"])) >= now
            )

        return {
            "items": items,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
            },
            "server_time": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    @staticmethod
    def get_session(session_id: int) -> Dict[str, Any]:
        s = AttendanceSessionRepository.get_by_id(session_id)
        if not s:
            raise NotFoundError(f"Attendance session {session_id} not found.")
        now = _server_utc_now()
        s["attendance_count"] = AttendanceSessionRepository.get_session_attendance_count(session_id)
        s["is_currently_open"] = (
            s["is_active"]
            and datetime.fromisoformat(str(s["start_time"])) <= now
            and datetime.fromisoformat(str(s["end_time"])) >= now
        )
        s["server_time"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        return s

    # ── Student self-attendance ────────────────────────────────────────────────

    @staticmethod
    def student_mark_attendance(
        payload: Dict[str, Any],
        student_user: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        A student marks their own attendance for an open session.

        Security enforced:
          - student_id derived from server session (never trusted from payload).
          - Validates GPS location against campus geofence.
          - Validates session is currently open (server clock).
          - Prevents duplicate submission.
          - Validates student enrollment in the session's subject.
        """
        # ── Identity: always from server session ──────────────────────────────
        student_id = student_user.get("student_id")
        if not student_id:
            raise ForbiddenError("No student profile linked to this account.")

        student = StudentRepository.get_by_id(student_id)
        if not student:
            raise NotFoundError("Student profile not found.")

        # ── Session validation ────────────────────────────────────────────────
        session_id = payload.get("session_id")
        if not session_id:
            raise ValidationError("session_id is required.")

        try:
            session_id = int(session_id)
        except (TypeError, ValueError):
            raise ValidationError("session_id must be an integer.")

        session = AttendanceSessionRepository.get_by_id(session_id)
        if not session:
            raise NotFoundError(f"Attendance session {session_id} not found.")

        if not session["is_active"]:
            raise ForbiddenError("This attendance session has been closed by the faculty.")

        # Server-authoritative timing check
        now = _server_utc_now()
        start_dt = datetime.fromisoformat(str(session["start_time"]))
        end_dt = datetime.fromisoformat(str(session["end_time"]))

        if now < start_dt:
            diff = int((start_dt - now).total_seconds() / 60)
            raise ForbiddenError(
                f"This session has not started yet. It opens in approximately {diff} minutes."
            )
        if now > end_dt:
            raise ForbiddenError(
                "This attendance session has already ended. Contact your faculty if you believe this is an error."
            )

        # ── Enrollment validation ─────────────────────────────────────────────
        enrolled_row = db.query_one(
            "SELECT id FROM student_subjects WHERE student_id = %s AND subject_id = %s",
            (student_id, session["subject_id"]),
        )
        if not enrolled_row:
            if student.get("current_semester_id") != session.get("semester_id"):
                raise ForbiddenError("You are not enrolled in this course or semester.")

        # ── GPS validation ────────────────────────────────────────────────────
        lat = payload.get("latitude")
        lng = payload.get("longitude")
        accuracy = payload.get("accuracy", 999)

        geo = validate_location(lat, lng, accuracy)
        if not geo["ok"]:
            raise ForbiddenError(
                f"Attendance rejected: {geo['message']}"
            )

        # ── Duplicate check ───────────────────────────────────────────────────
        if AttendanceSessionRepository.student_already_marked(student_id, session_id):
            raise ConflictError("You have already marked attendance for this session.")

        # ── Insert attendance record (transactional) ─────────────────────────
        subject_id = session["subject_id"]
        session_date = str(session["session_date"])

        with db.transaction() as cursor:
            # Re-check inside transaction to prevent race conditions
            cursor.execute(
                "SELECT id FROM attendance WHERE student_id = %s AND session_id = %s",
                (student_id, session_id)
            )
            if cursor.fetchone():
                raise ConflictError("Duplicate attendance submission detected.")

            # Also enforce the legacy unique constraint (student/subject/date)
            cursor.execute(
                "SELECT id FROM attendance WHERE student_id = %s AND subject_id = %s AND date = %s AND session_id = %s",
                (student_id, subject_id, session_date, session_id)
            )
            if cursor.fetchone():
                raise ConflictError("Attendance for this session already exists.")

            cursor.execute(
                """
                INSERT INTO attendance
                    (student_id, subject_id, date, status, remarks,
                     session_id, verified_lat, verified_lng,
                     verified_accuracy, distance_from_campus, verified_at)
                VALUES (%s, %s, %s, 'Present', %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    student_id,
                    subject_id,
                    session_date,
                    "GPS-verified attendance",
                    session_id,
                    round(geo["lat"], 7),
                    round(geo["lng"], 7),
                    round(geo["accuracy_m"], 2),
                    round(geo["distance_m"], 2),
                    now.strftime("%Y-%m-%d %H:%M:%S"),
                )
            )
            att_id = cursor.lastrowid

        record = AttendanceRepository.get_by_id(att_id)
        return {
            "attendance": record,
            "session": {
                "id": session["id"],
                "subject_name": session["subject_name"],
                "subject_code": session["subject_code"],
            },
            "geo": {
                "distance_m": geo["distance_m"],
                "inside_fence": geo["inside_fence"],
                "accuracy_m": geo["accuracy_m"],
                "message": geo["message"],
            },
        }

    # ── Session attendance list (faculty view) ────────────────────────────────

    @staticmethod
    def get_session_attendance(session_id: int, requesting_user: Dict[str, Any]) -> Dict[str, Any]:
        """Return all attendance records for a session with student details."""
        session = AttendanceSessionRepository.get_by_id(session_id)
        if not session:
            raise NotFoundError(f"Session {session_id} not found.")

        role = requesting_user.get("role", "")
        if role == "Faculty":
            faculty_id = requesting_user.get("faculty_id")
            if session["faculty_id"] != faculty_id:
                raise ForbiddenError("You can only view attendance for your own sessions.")
        elif role == "Student":
            raise ForbiddenError("Students cannot view session attendance lists.")
        # Admin: unrestricted

        rows = db.query_all(
            """
            SELECT
                a.id, a.student_id, a.status, a.verified_at,
                a.distance_from_campus, a.verified_accuracy,
                s.roll_number, s.first_name, s.last_name, s.email
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.session_id = %s
            ORDER BY s.roll_number ASC
            """,
            (session_id,)
        )

        # Enrolled students not yet marked
        enrolled_ids = set(r["student_id"] for r in rows)
        enrolled_all = db.query_all(
            """
            SELECT DISTINCT s.id, s.roll_number, s.first_name, s.last_name
            FROM students s
            LEFT JOIN student_subjects ss ON ss.student_id = s.id AND ss.subject_id = %s
            WHERE (ss.id IS NOT NULL OR s.current_semester_id = %s)
              AND s.status = 'Active'
            ORDER BY s.roll_number ASC
            """,
            (session["subject_id"], session["semester_id"])
        )
        absent = [e for e in enrolled_all if e["id"] not in enrolled_ids]

        now = _server_utc_now()
        return {
            "session": session,
            "server_time": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "present": rows,
            "absent_or_not_marked": absent,
            "total_enrolled": len(enrolled_all),
            "present_count": len(rows),
        }
