"""
GPS Attendance API blueprint.

Provides:
  GET    /api/v1/gps-attendance/config              — Campus GPS config (all roles, public OK)
  PUT    /api/v1/gps-attendance/config              — Update campus settings (Admin only)
  POST   /api/v1/gps-attendance/validate-location   — Validate GPS coords (any authenticated user)

  GET    /api/v1/gps-attendance/sessions             — List sessions
  POST   /api/v1/gps-attendance/sessions             — Create session (Faculty)
  GET    /api/v1/gps-attendance/sessions/<id>        — Get session detail
  POST   /api/v1/gps-attendance/sessions/<id>/close — Close session early (Faculty/Admin)
  GET    /api/v1/gps-attendance/sessions/<id>/attendance — Session attendance list (Faculty/Admin)

  POST   /api/v1/gps-attendance/mark                — Student marks own attendance
  GET    /api/v1/gps-attendance/student/summary      — Student attendance summary (GPS records)
"""

from flask import Blueprint, request
from app.services.gps_attendance_service import GpsAttendanceService
from app.utils.auth import get_current_user, login_required, roles_required
from app.utils.exceptions import ForbiddenError, ValidationError
from app.utils.responses import api_response
from app.utils.validators import parse_pagination

gps_attendance_bp = Blueprint("gps_attendance", __name__, url_prefix="/api/v1/gps-attendance")


# ── Campus configuration ──────────────────────────────────────────────────────

@gps_attendance_bp.route("/config", methods=["GET"])
def get_campus_config():
    """Return campus GPS configuration (public: students and faculty need this to display UI)."""
    cfg = GpsAttendanceService.get_campus_config()
    # Strip raw settings list for non-admin callers — only surface the typed fields
    cfg.pop("all_settings", None)
    return api_response(data=cfg, message="Campus configuration retrieved successfully")


@gps_attendance_bp.route("/config", methods=["PUT", "PATCH"])
@roles_required("Admin")
def update_campus_config():
    """Update campus GPS settings (Admin only)."""
    user = get_current_user()
    payload = request.get_json(silent=True) or {}
    if not payload:
        raise ValidationError("Request body must be a JSON object of setting_key: value pairs.")
    result = GpsAttendanceService.update_campus_settings(payload, admin_user_id=user["id"])
    result.pop("all_settings", None)
    return api_response(data=result, message="Campus settings updated successfully")


@gps_attendance_bp.route("/config/all", methods=["GET"])
@roles_required("Admin")
def get_all_campus_config():
    """Return all raw campus_settings rows (Admin only)."""
    cfg = GpsAttendanceService.get_campus_config()
    return api_response(data=cfg, message="All campus settings retrieved successfully")


# ── Location validation ───────────────────────────────────────────────────────

@gps_attendance_bp.route("/validate-location", methods=["POST"])
@login_required
def validate_location():
    """
    Validate a GPS coordinate against the campus geofence.
    Accepts: { latitude, longitude, accuracy }
    Returns: { ok, distance_m, inside_fence, accuracy_ok, message, ... }
    """
    payload = request.get_json(silent=True) or {}
    result = GpsAttendanceService.check_location(
        lat=payload.get("latitude"),
        lng=payload.get("longitude"),
        accuracy=payload.get("accuracy", 9999),
    )
    return api_response(
        data=result,
        message="Location validated",
        status_code=200 if result["ok"] else 422,
    )


# ── Session management ────────────────────────────────────────────────────────

@gps_attendance_bp.route("/sessions", methods=["GET"])
@login_required
def list_sessions():
    """List attendance sessions. Faculty see only their own; Admin sees all."""
    user = get_current_user()

    def _int_param(name: str):
        v = request.args.get(name, "").strip()
        return int(v) if v.isdigit() else None

    subject_id  = _int_param("subject_id")
    semester_id = _int_param("semester_id")
    active_raw  = request.args.get("is_active", "").strip().lower()
    is_active   = True if active_raw == "true" else (False if active_raw == "false" else None)

    page, per_page = parse_pagination(request.args.get("page"), request.args.get("per_page"))

    faculty_user = user if user.get("role") == "Faculty" else None
    result = GpsAttendanceService.list_sessions(
        faculty_user=faculty_user,
        subject_id=subject_id,
        semester_id=semester_id,
        is_active=is_active,
        page=page,
        per_page=per_page,
    )
    return api_response(
        data=result["items"],
        message="Sessions retrieved successfully",
        meta=result["pagination"],
    )


@gps_attendance_bp.route("/sessions", methods=["POST"])
@roles_required("Faculty")
def create_session():
    """Faculty creates a new attendance session (must be within campus geofence)."""
    user = get_current_user()
    payload = request.get_json(silent=True) or {}
    session = GpsAttendanceService.create_session(payload, faculty_user=user)
    return api_response(data=session, message="Attendance session created successfully", status_code=201)


@gps_attendance_bp.route("/sessions/<int:session_id>", methods=["GET"])
@login_required
def get_session(session_id: int):
    """Get session detail. Faculty must own session; Admin unrestricted."""
    user = get_current_user()
    session = GpsAttendanceService.get_session(session_id)
    if user.get("role") == "Faculty" and session["faculty_id"] != user.get("faculty_id"):
        raise ForbiddenError("You can only view your own sessions.")
    return api_response(data=session, message="Session retrieved successfully")


@gps_attendance_bp.route("/sessions/<int:session_id>/close", methods=["POST"])
@login_required
def close_session(session_id: int):
    """Close a session early (Faculty who owns it, or Admin)."""
    user = get_current_user()
    if user.get("role") not in ("Faculty", "Admin"):
        raise ForbiddenError("Only Faculty or Admin can close sessions.")
    result = GpsAttendanceService.close_session(session_id, faculty_user=user)
    return api_response(data=result, message="Session closed successfully")


@gps_attendance_bp.route("/sessions/<int:session_id>/attendance", methods=["GET"])
@login_required
def session_attendance_list(session_id: int):
    """Get who has/hasn't marked attendance for a session (Faculty/Admin only)."""
    user = get_current_user()
    result = GpsAttendanceService.get_session_attendance(session_id, requesting_user=user)
    return api_response(data=result, message="Session attendance list retrieved")


# ── Student self-attendance ───────────────────────────────────────────────────

@gps_attendance_bp.route("/mark", methods=["POST"])
@roles_required("Student")
def mark_attendance():
    """
    Student marks their own attendance.
    Required payload: { session_id, latitude, longitude, accuracy }
    Student identity is derived exclusively from the server session cookie.
    """
    user = get_current_user()
    payload = request.get_json(silent=True) or {}
    result = GpsAttendanceService.student_mark_attendance(payload, student_user=user)
    return api_response(data=result, message="Attendance marked successfully", status_code=201)


@gps_attendance_bp.route("/student/sessions", methods=["GET"])
@roles_required("Student")
def student_active_sessions():
    """
    Return currently open attendance sessions for subjects the student is enrolled in.
    Student identity derived from server session.
    """
    user = get_current_user()
    from app.services.gps_attendance_service import _server_utc_now
    from app.repositories.gps_attendance_repo import AttendanceSessionRepository
    from app import db

    student_id = user.get("student_id")
    if not student_id:
        raise ForbiddenError("No student profile linked.")

    now = _server_utc_now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # Get subjects the student is enrolled in (directly or via current semester)
    student = db.query_one("SELECT current_semester_id FROM students WHERE id = %s", (student_id,))
    sem_id = student.get("current_semester_id") if student else None

    if sem_id:
        sub_rows = db.query_all(
            """
            SELECT subject_id FROM student_subjects WHERE student_id = %s
            UNION
            SELECT id AS subject_id FROM subjects WHERE semester_id = %s
            """,
            (student_id, sem_id)
        )
    else:
        sub_rows = db.query_all(
            "SELECT subject_id FROM student_subjects WHERE student_id = %s",
            (student_id,)
        )

    if not sub_rows:
        return api_response(data=[], message="No enrolled subjects found")

    subject_ids = [r["subject_id"] for r in sub_rows]
    placeholders = ",".join(["%s"] * len(subject_ids))
    open_sessions = db.query_all(
        f"""
        SELECT
            s.id, s.subject_id, s.faculty_id, s.semester_id,
            s.session_date, s.start_time, s.end_time, s.is_active,
            sub.name AS subject_name, sub.subject_code, sub.department,
            f.first_name AS faculty_first_name, f.last_name AS faculty_last_name,
            sem.name AS semester_name
        FROM attendance_sessions s
        JOIN subjects  sub ON s.subject_id  = sub.id
        JOIN faculty   f   ON s.faculty_id  = f.id
        JOIN semesters sem ON s.semester_id = sem.id
        WHERE s.subject_id IN ({placeholders})
          AND s.is_active = TRUE
          AND s.start_time <= %s
          AND s.end_time   >= %s
        ORDER BY s.start_time ASC
        """,
        (*subject_ids, now_str, now_str)
    )

    # For each open session, check if student already marked
    for sess in open_sessions:
        sess["already_marked"] = AttendanceSessionRepository.student_already_marked(
            student_id, sess["id"]
        )

    return api_response(
        data=open_sessions,
        message=f"Found {len(open_sessions)} active session(s)",
    )


@gps_attendance_bp.route("/student/summary", methods=["GET"])
@roles_required("Student")
def student_gps_summary():
    """GPS-verified attendance summary for the logged-in student."""
    from app.services.attendance_service import AttendanceService
    user = get_current_user()
    student_id = user.get("student_id")
    if not student_id:
        raise ForbiddenError("No student profile linked.")
    summary = AttendanceService.get_student_summary(student_id)
    return api_response(data=summary, message="Attendance summary retrieved")


@gps_attendance_bp.route("/faculty/subjects", methods=["GET"])
@roles_required("Faculty")
def faculty_assigned_subjects():
    """Return subjects assigned to the logged-in faculty member."""
    user = get_current_user()
    faculty_id = user.get("faculty_id")
    if not faculty_id:
        raise ForbiddenError("No faculty profile linked.")

    from app import db
    rows = db.query_all(
        """
        SELECT
            fs.subject_id, fs.semester_id,
            sub.name AS subject_name, sub.subject_code, sub.department, sub.credits,
            sem.name AS semester_name, sem.semester_number, sem.is_active AS semester_active
        FROM faculty_subjects fs
        JOIN subjects  sub ON fs.subject_id  = sub.id
        JOIN semesters sem ON fs.semester_id = sem.id
        WHERE fs.faculty_id = %s
        ORDER BY sem.semester_number DESC, sub.subject_code ASC
        """,
        (faculty_id,)
    )
    return api_response(data=rows, message="Assigned subjects retrieved")
