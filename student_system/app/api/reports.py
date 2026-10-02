"""
Reports API blueprint providing JSON viewing, CSV export, and PDF generation with strict RBAC.
"""

from datetime import datetime
from flask import Blueprint, request
from app import db
from app.repositories.faculty_repo import FacultyRepository
from app.repositories.mark_repo import MarkRepository
from app.repositories.semester_repo import SemesterRepository
from app.repositories.student_repo import StudentRepository
from app.repositories.subject_repo import SubjectRepository
from app.services.mark_service import enrich_mark
from app.services.report_generator import export_csv_response, export_pdf_response
from app.services.report_service import ReportService
from app.utils.auth import (
    check_student_scope,
    get_current_user,
    login_required,
    roles_required,
)
from app.utils.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.utils.responses import api_response

reports_bp = Blueprint("reports", __name__, url_prefix="/api/v1/reports")


@reports_bp.route("/academic", methods=["GET"])
@reports_bp.route("/student/<int:student_id>", methods=["GET"])
@reports_bp.route("/students/<int:student_id>/transcript", methods=["GET"])
@login_required
def get_student_academic_report(student_id: Optional[int] = None):
    """
    Generate student academic report / transcript.
    Supports ?format=json (default), ?format=csv, ?format=pdf.
    Enforces IDOR check: Students can only view their own transcript.
    """
    if student_id is None:
        raw_id = request.args.get("student_id")
        if raw_id and raw_id.isdigit():
            student_id = int(raw_id)
        else:
            user = get_current_user()
            if user.get("student_id"):
                student_id = user["student_id"]
            else:
                raise ValidationError("student_id parameter is required.")

    check_student_scope(student_id)
    transcript = ReportService.get_student_transcript(student_id)
    fmt = request.args.get("format", "json").lower().strip()

    student_meta = transcript["student"]
    summary_meta = transcript["academic_summary"]

    if fmt == "csv":
        headers = ["Semester", "Subject Code", "Subject Name", "Credits", "Assessment", "Score", "Max Marks", "Percentage", "Grade"]
        rows = []
        for sem in transcript.get("semesters", []):
            sem_name = sem["semester_name"]
            for sub in sem.get("subjects", []):
                sub_code = sub["subject_code"]
                sub_name = sub["subject_name"]
                credits = sub["credits"]
                for ass in sub.get("assessments", []):
                    rows.append([
                        sem_name,
                        sub_code,
                        sub_name,
                        credits,
                        ass["exam_type"],
                        ass["marks_obtained"],
                        ass["max_marks"],
                        f"{ass['percentage']}%",
                        ass["grade"],
                    ])
        filename = f"academic_report_{student_meta['roll_number']}_{datetime.now().strftime('%Y%m%d')}"
        return export_csv_response(filename, headers, rows)

    elif fmt == "pdf":
        headers = ["Semester", "Subject", "Credits", "Assessment", "Score", "Grade"]
        rows = []
        for sem in transcript.get("semesters", []):
            for sub in sem.get("subjects", []):
                for ass in sub.get("assessments", []):
                    rows.append([
                        sem["semester_name"],
                        f"{sub['subject_code']} - {sub['subject_name']}",
                        str(sub["credits"]),
                        ass["exam_type"],
                        f"{ass['marks_obtained']}/{ass['max_marks']} ({ass['percentage']}%)",
                        ass["grade"],
                    ])
        meta_pairs = [
            ("Student Name", student_meta["name"]),
            ("Roll Number", student_meta["roll_number"]),
            ("Email", student_meta["email"]),
            ("Status", student_meta["status"]),
            ("Cumulative GPA (CGPA)", str(summary_meta["cumulative_gpa"])),
            ("Total Credits Earned", str(summary_meta["total_credits_earned"])),
            ("Attendance Rate", f"{transcript['attendance']['attendance_percentage']}%"),
        ]
        filename = f"transcript_{student_meta['roll_number']}"
        return export_pdf_response(
            filename=filename,
            title="Official Student Academic Transcript",
            subtitle=f"Generated on {datetime.now().strftime('%B %d, %Y')}",
            headers=headers,
            rows=rows,
            meta_pairs=meta_pairs,
        )

    return api_response(data=transcript, message="Student academic transcript generated successfully.")


# ----------------------------------------------------------------------
# 2. Marks Report with JSON, CSV, and PDF export
# ----------------------------------------------------------------------
@reports_bp.route("/marks", methods=["GET"])
@login_required
def get_marks_report():
    """
    Generate marks report filtered by subject, semester, or student.
    Enforces RBAC: Faculty restricted to their assigned courses; Students to their own marks.
    """
    user = get_current_user()
    role = user["role"]

    sub_id_raw = request.args.get("subject_id")
    subject_id = int(sub_id_raw) if sub_id_raw and sub_id_raw.isdigit() else None

    sem_id_raw = request.args.get("semester_id")
    semester_id = int(sem_id_raw) if sem_id_raw and sem_id_raw.isdigit() else None

    target_stu_raw = request.args.get("student_id")
    target_student_id = int(target_stu_raw) if target_stu_raw and target_stu_raw.isdigit() else None

    # Enforce RBAC
    if role == "Student":
        target_student_id = user.get("student_id")
    elif role == "Faculty":
        faculty_id = user.get("faculty_id")
        if subject_id:
            if not FacultyRepository.is_faculty_assigned_to_subject(faculty_id, subject_id, semester_id):
                raise ForbiddenError("Access denied: You are not assigned to this subject.")
        else:
            # If no subject specified, scope to first assigned subject
            assigned = FacultyRepository.get_assigned_subjects(faculty_id)
            if not assigned:
                raise ForbiddenError("You have no assigned subjects to generate reports for.")
            subject_id = assigned[0]["id"]

    raw_marks = MarkRepository.list_marks(
        student_id=target_student_id,
        subject_id=subject_id,
        semester_id=semester_id,
        limit=1000,
    )
    enriched = [enrich_mark(m) for m in raw_marks]
    fmt = request.args.get("format", "json").lower().strip()

    if fmt == "csv":
        headers = ["Roll Number", "Student Name", "Subject Code", "Subject Name", "Semester", "Exam Type", "Marks Obtained", "Max Marks", "Percentage", "Grade"]
        rows = [
            [
                m["roll_number"],
                f"{m['first_name']} {m['last_name']}",
                m["subject_code"],
                m["subject_name"],
                m["semester_name"],
                m["exam_type"],
                m["marks_obtained"],
                m["max_marks"],
                f"{m['percentage']}%",
                m["grade"],
            ]
            for m in enriched
        ]
        return export_csv_response("marks_report", headers, rows)

    elif fmt == "pdf":
        headers = ["Roll No", "Student Name", "Subject", "Exam", "Marks", "Grade"]
        rows = [
            [
                m["roll_number"],
                f"{m['first_name']} {m['last_name']}",
                m["subject_code"],
                m["exam_type"],
                f"{m['marks_obtained']}/{m['max_marks']}",
                m["grade"],
            ]
            for m in enriched
        ]
        meta_pairs = [("Generated By", f"{user['username']} ({role})"), ("Total Entries", str(len(enriched)))]
        return export_pdf_response(
            filename="marks_report",
            title="Student Marks and Evaluation Report",
            subtitle=f"Generated on {datetime.now().strftime('%B %d, %Y')}",
            headers=headers,
            rows=rows,
            meta_pairs=meta_pairs,
        )

    return api_response(data=enriched, message="Marks report generated successfully.", meta={"count": len(enriched)})


# ----------------------------------------------------------------------
# 3. Attendance Report with JSON, CSV, and PDF export
# ----------------------------------------------------------------------
@reports_bp.route("/attendance", methods=["GET"])
@login_required
def get_attendance_report():
    """
    Generate attendance report filtered by subject, student, or date range.
    Enforces RBAC on faculty courses and student self-access.
    """
    user = get_current_user()
    role = user["role"]

    sub_id_raw = request.args.get("subject_id")
    subject_id = int(sub_id_raw) if sub_id_raw and sub_id_raw.isdigit() else None

    date_from = request.args.get("date_from", "").strip() or None
    date_to = request.args.get("date_to", "").strip() or None

    target_stu_raw = request.args.get("student_id")
    target_student_id = int(target_stu_raw) if target_stu_raw and target_stu_raw.isdigit() else None

    if role == "Student":
        target_student_id = user.get("student_id")
    elif role == "Faculty":
        faculty_id = user.get("faculty_id")
        if subject_id and not FacultyRepository.is_faculty_assigned_to_subject(faculty_id, subject_id):
            raise ForbiddenError("Access denied: You are not assigned to instruct this subject.")

    from app.repositories.attendance_repo import AttendanceRepository
    records = AttendanceRepository.list_attendance(
        student_id=target_student_id,
        subject_id=subject_id,
        date_from=date_from,
        date_to=date_to,
        limit=1000,
    )
    fmt = request.args.get("format", "json").lower().strip()

    if fmt == "csv":
        headers = ["Roll Number", "Student Name", "Subject Code", "Subject Name", "Date", "Status", "Remarks"]
        rows = [
            [
                r["roll_number"],
                f"{r['first_name']} {r['last_name']}",
                r["subject_code"],
                r["subject_name"],
                r["date"],
                r["status"],
                r["remarks"] or "",
            ]
            for r in records
        ]
        return export_csv_response("attendance_report", headers, rows)

    elif fmt == "pdf":
        headers = ["Roll No", "Student Name", "Subject", "Date", "Status", "Remarks"]
        rows = [
            [
                r["roll_number"],
                f"{r['first_name']} {r['last_name']}",
                r["subject_code"],
                str(r["date"]),
                r["status"],
                r["remarks"] or "-",
            ]
            for r in records
        ]
        meta_pairs = [("Generated By", f"{user['username']} ({role})"), ("Total Sessions", str(len(records)))]
        return export_pdf_response(
            filename="attendance_report",
            title="Student Attendance Report",
            subtitle=f"Generated on {datetime.now().strftime('%B %d, %Y')}",
            headers=headers,
            rows=rows,
            meta_pairs=meta_pairs,
        )

    return api_response(data=records, message="Attendance report generated successfully.", meta={"count": len(records)})


@reports_bp.route("/subject", methods=["GET"])
@reports_bp.route("/subject/<int:subject_id>", methods=["GET"])
@roles_required("Faculty", "Admin")
def get_subject_report(subject_id: Optional[int] = None):
    """Generate subject / class-level performance summary."""
    if subject_id is None:
        raw_id = request.args.get("subject_id")
        if raw_id and raw_id.isdigit():
            subject_id = int(raw_id)
        else:
            raise ValidationError("subject_id parameter is required.")

    user = get_current_user()
    if user["role"] == "Faculty":
        if not FacultyRepository.is_faculty_assigned_to_subject(user["faculty_id"], subject_id):
            raise ForbiddenError("Access denied: You are not assigned to instruct this course.")

    subject = SubjectRepository.get_by_id(subject_id)
    if not subject:
        raise NotFoundError(f"Subject with ID {subject_id} not found.")

    # Calculate class aggregates
    sql_marks = """
        SELECT 
            COUNT(*) as total_assessments,
            AVG(marks_obtained / max_marks * 100) as avg_score,
            MAX(marks_obtained / max_marks * 100) as max_score,
            MIN(marks_obtained / max_marks * 100) as min_score,
            SUM(CASE WHEN (marks_obtained / max_marks * 100) >= 50 THEN 1 ELSE 0 END) as passed_count
        FROM marks
        WHERE subject_id = %s
    """
    m_stats = db.query_one(sql_marks, (subject_id,))

    sql_enrolled = "SELECT COUNT(*) as c FROM student_subjects WHERE subject_id = %s"
    enrolled_c = db.query_one(sql_enrolled, (subject_id,))["c"]

    avg_score = round(float(m_stats["avg_score"]), 2) if m_stats and m_stats["avg_score"] is not None else 0.0
    tot_ass = int(m_stats["total_assessments"]) if m_stats and m_stats["total_assessments"] else 0
    passed = int(m_stats["passed_count"]) if m_stats and m_stats["passed_count"] else 0
    pass_rate = round((passed / tot_ass) * 100, 2) if tot_ass > 0 else 0.0

    report_data = {
        "subject": subject,
        "enrolled_students": enrolled_c,
        "total_assessments": tot_ass,
        "class_average_percentage": avg_score,
        "highest_score": round(float(m_stats["max_score"]), 2) if m_stats and m_stats["max_score"] is not None else 0.0,
        "lowest_score": round(float(m_stats["min_score"]), 2) if m_stats and m_stats["min_score"] is not None else 0.0,
        "pass_rate_percentage": pass_rate,
    }

    fmt = request.args.get("format", "json").lower().strip()
    if fmt == "csv":
        headers = ["Subject Code", "Subject Name", "Department", "Credits", "Enrolled Students", "Average %", "Pass Rate %"]
        rows = [[
            subject["subject_code"],
            subject["name"],
            subject["department"],
            subject["credits"],
            enrolled_c,
            f"{avg_score}%",
            f"{pass_rate}%",
        ]]
        return export_csv_response(f"subject_report_{subject['subject_code']}", headers, rows)

    elif fmt == "pdf":
        headers = ["Metric", "Value"]
        rows = [
            ["Subject Code", subject["subject_code"]],
            ["Course Name", subject["name"]],
            ["Department", subject["department"]],
            ["Credits", str(subject["credits"])],
            ["Enrolled Students", str(enrolled_c)],
            ["Class Average", f"{avg_score}%"],
            ["Pass Rate", f"{pass_rate}%"],
            ["Highest Score", f"{report_data['highest_score']}%"],
            ["Lowest Score", f"{report_data['lowest_score']}%"],
        ]
        return export_pdf_response(
            filename=f"subject_report_{subject['subject_code']}",
            title=f"Class Performance Report: {subject['subject_code']}",
            subtitle=f"{subject['name']} | Generated on {datetime.now().strftime('%B %d, %Y')}",
            headers=headers,
            rows=rows,
        )

    return api_response(data=report_data, message="Subject report generated successfully.")


@reports_bp.route("/semester", methods=["GET"])
@reports_bp.route("/semester/<int:semester_id>", methods=["GET"])
@roles_required("Faculty", "Admin")
def get_semester_report(semester_id: Optional[int] = None):
    """Generate semester term performance report."""
    if semester_id is None:
        raw_id = request.args.get("semester_id")
        if raw_id and raw_id.isdigit():
            semester_id = int(raw_id)
        else:
            raise ValidationError("semester_id parameter is required.")

    semester = SemesterRepository.get_by_id(semester_id)
    if not semester:
        raise NotFoundError(f"Semester with ID {semester_id} not found.")

    courses = SubjectRepository.list_subjects(semester_id=semester_id, limit=200)

    # Calculate overall grade counts in this semester
    sql_grades = """
        SELECT 
            COUNT(*) as total_grades,
            AVG(marks_obtained / max_marks * 100) as avg_pct
        FROM marks
        WHERE semester_id = %s
    """
    g_stat = db.query_one(sql_grades, (semester_id,))
    total_evals = int(g_stat["total_grades"]) if g_stat and g_stat["total_grades"] else 0
    term_avg = round(float(g_stat["avg_pct"]), 2) if g_stat and g_stat["avg_pct"] is not None else 0.0

    report_data = {
        "semester": semester,
        "total_courses": len(courses),
        "total_assessments": total_evals,
        "term_average_percentage": term_avg,
        "courses": courses,
    }

    fmt = request.args.get("format", "json").lower().strip()
    if fmt == "csv":
        headers = ["Semester", "Subject Code", "Subject Name", "Credits", "Department"]
        rows = [
            [semester["name"], c["subject_code"], c["name"], c["credits"], c["department"]]
            for c in courses
        ]
        return export_csv_response(f"semester_report_{semester['name'].replace(' ', '_')}", headers, rows)

    elif fmt == "pdf":
        headers = ["Course Code", "Course Title", "Credits", "Department"]
        rows = [[c["subject_code"], c["name"], str(c["credits"]), c["department"]] for c in courses]
        meta_pairs = [
            ("Semester", semester["name"]),
            ("Academic Year", semester["academic_year"]),
            ("Start Date", str(semester["start_date"])),
            ("End Date", str(semester["end_date"])),
            ("Term Average", f"{term_avg}%"),
        ]
        return export_pdf_response(
            filename=f"semester_report_{semester['name'].replace(' ', '_')}",
            title=f"Academic Semester Report: {semester['name']}",
            subtitle=f"Academic Year {semester['academic_year']}",
            headers=headers,
            rows=rows,
            meta_pairs=meta_pairs,
        )

    return api_response(data=report_data, message="Semester report generated successfully.")


# ----------------------------------------------------------------------
# 6. Low Attendance Alert (Kept for backwards compatibility)
# ----------------------------------------------------------------------
@reports_bp.route("/attendance/low", methods=["GET"])
@roles_required("Faculty", "Admin")
def get_low_attendance():
    """Identify students whose overall attendance is below threshold (default 75%)."""
    threshold_raw = request.args.get("threshold", 75.0)
    try:
        threshold = float(threshold_raw)
    except (ValueError, TypeError):
        threshold = 75.0

    at_risk = ReportService.get_low_attendance_report(threshold=threshold)
    return api_response(
        data=at_risk,
        message=f"Found {len(at_risk)} student(s) with attendance below {threshold}%",
        meta={"threshold": threshold, "count": len(at_risk)},
    )
