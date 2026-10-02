"""
Analytics service for generating role-appropriate analytics and metrics from MySQL.
"""

from typing import Any, Dict, List, Optional
from collections import defaultdict
from app import db
from app.repositories.student_repo import StudentRepository
from app.repositories.mark_repo import MarkRepository
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.faculty_repo import FacultyRepository
from app.services.mark_service import enrich_mark, compute_grade_and_points
from app.services.attendance_service import AttendanceService
from app.services.report_service import ReportService
from app.utils.auth import check_student_scope, get_current_user
from app.utils.exceptions import NotFoundError, ForbiddenError


class AnalyticsService:
    """Service providing calculated analytical indicators for Student, Faculty, and Admin dashboards."""

    @staticmethod
    def get_student_analytics(student_id: int) -> Dict[str, Any]:
        """
        Generate detailed student analytics strictly from actual database records.
        Protects against IDOR via check_student_scope.
        """
        check_student_scope(student_id)

        student = StudentRepository.get_by_id(student_id)
        if not student:
            raise NotFoundError(f"Student with ID {student_id} not found.")

        # 1. Fetch marks
        raw_marks = MarkRepository.list_marks(student_id=student_id, limit=500)
        enriched_marks = [enrich_mark(m) for m in raw_marks]

        # Group by subject
        subjects_data = defaultdict(lambda: {
            "subject_id": None,
            "subject_code": "",
            "subject_name": "",
            "credits": 0.0,
            "assessments": [],
            "total_obtained": 0.0,
            "total_max": 0.0,
        })

        for m in enriched_marks:
            sub_id = m["subject_id"]
            entry = subjects_data[sub_id]
            entry["subject_id"] = sub_id
            entry["subject_code"] = m.get("subject_code", "")
            entry["subject_name"] = m.get("subject_name", "")
            entry["credits"] = float(m.get("credits", 3.0))
            entry["assessments"].append({
                "exam_type": m["exam_type"],
                "marks_obtained": float(m["marks_obtained"]),
                "max_marks": float(m["max_marks"]),
                "percentage": m["percentage"],
                "grade": m["grade"],
            })
            entry["total_obtained"] += float(m["marks_obtained"])
            entry["total_max"] += float(m["max_marks"])

        subject_wise_marks = []
        overall_total_obtained = 0.0
        overall_total_max = 0.0

        for sub_id, item in subjects_data.items():
            tot_obt = item["total_obtained"]
            tot_max = item["total_max"]
            sub_pct = round((tot_obt / tot_max) * 100, 2) if tot_max > 0 else 0.0
            grade, _ = compute_grade_and_points(tot_obt, tot_max)
            item["percentage"] = sub_pct
            item["overall_grade"] = grade
            subject_wise_marks.append(item)
            overall_total_obtained += tot_obt
            overall_total_max += tot_max

        overall_average = (
            round((overall_total_obtained / overall_total_max) * 100, 2)
            if overall_total_max > 0
            else 0.0
        )

        # 2. Fetch transcript for semester performance & CGPA
        transcript = ReportService.get_student_transcript(student_id)
        semester_performance = []
        for sem in transcript.get("semesters", []):
            semester_performance.append({
                "semester_id": sem["semester_id"],
                "semester_name": sem["semester_name"],
                "semester_gpa": sem["semester_gpa"],
                "total_credits": sem["total_credits"],
                "subject_count": len(sem["subjects"]),
            })

        # 3. Subject comparison (highest vs lowest)
        sorted_subjects = sorted(subject_wise_marks, key=lambda x: x["percentage"], reverse=True)
        best_subject = sorted_subjects[0] if sorted_subjects else None
        worst_subject = sorted_subjects[-1] if sorted_subjects else None

        # 4. Performance trends over assessments
        performance_trends = []
        for idx, m in enumerate(enriched_marks):
            performance_trends.append({
                "index": idx + 1,
                "label": f"{m.get('subject_code')} - {m.get('exam_type')}",
                "percentage": m.get("percentage", 0.0),
                "grade": m.get("grade", "F"),
            })

        # 5. Attendance analytics
        att_summary = AttendanceService.get_student_summary(student_id)
        overall_att = att_summary["overall_summary"]

        return {
            "student": {
                "id": student["id"],
                "roll_number": student["roll_number"],
                "name": f"{student['first_name']} {student['last_name']}",
                "email": student["email"],
                "status": student["status"],
            },
            "metrics": {
                "overall_average_percentage": overall_average,
                "cumulative_gpa": transcript.get("academic_summary", {}).get("cumulative_gpa", 0.0),
                "total_assessments_taken": len(enriched_marks),
                "attendance_percentage": overall_att["attendance_percentage"],
                "total_sessions": overall_att["total_sessions"],
                "attended_sessions": overall_att["present"] + overall_att["excused"],
                "is_low_attendance": overall_att["is_low_attendance"],
            },
            "subject_wise_marks": subject_wise_marks,
            "subject_comparison": {
                "highest": {
                    "subject": best_subject["subject_code"] if best_subject else None,
                    "percentage": best_subject["percentage"] if best_subject else 0.0,
                },
                "lowest": {
                    "subject": worst_subject["subject_code"] if worst_subject else None,
                    "percentage": worst_subject["percentage"] if worst_subject else 0.0,
                },
                "ranking": [
                    {"code": s["subject_code"], "name": s["subject_name"], "percentage": s["percentage"]}
                    for s in sorted_subjects
                ],
            },
            "semester_performance": semester_performance,
            "performance_trends": performance_trends,
            "attendance_breakdown": att_summary["by_subject"],
        }

    @staticmethod
    def get_faculty_analytics(faculty_id: int) -> Dict[str, Any]:
        """
        Generate faculty-level aggregated performance analytics.
        Strictly scoped to courses assigned to this faculty member.
        """
        faculty = FacultyRepository.get_by_id(faculty_id)
        if not faculty:
            raise NotFoundError(f"Faculty with ID {faculty_id} not found.")

        assigned_subjects = FacultyRepository.get_assigned_subjects(faculty_id)
        subject_analytics = []

        total_students_taught = set()
        overall_scores = []

        for sub in assigned_subjects:
            sub_id = sub["id"]
            sem_id = sub["semester_id"]

            # Query enrolled students for this course
            enrolled_sql = """
                SELECT student_id FROM student_subjects 
                WHERE subject_id = %s AND semester_id = %s
            """
            enrolled_rows = db.query_all(enrolled_sql, (sub_id, sem_id))
            enrolled_count = len(enrolled_rows)
            for r in enrolled_rows:
                total_students_taught.add(r["student_id"])

            # Query marks statistics for this subject
            marks_sql = """
                SELECT 
                    COUNT(*) as total_entries,
                    AVG(marks_obtained / max_marks * 100) as avg_percentage,
                    MAX(marks_obtained / max_marks * 100) as max_percentage,
                    MIN(marks_obtained / max_marks * 100) as min_percentage,
                    SUM(CASE WHEN (marks_obtained / max_marks * 100) >= 50 THEN 1 ELSE 0 END) as pass_count
                FROM marks
                WHERE subject_id = %s AND semester_id = %s
            """
            stats = db.query_one(marks_sql, (sub_id, sem_id))

            # Query attendance statistics for this subject
            att_sql = """
                SELECT 
                    COUNT(*) as total_records,
                    SUM(CASE WHEN status IN ('Present', 'Excused') THEN 1 WHEN status = 'Late' THEN 0.5 ELSE 0 END) as attended
                FROM attendance
                WHERE subject_id = %s
            """
            att_stats = db.query_one(att_sql, (sub_id,))
            att_pct = 0.0
            if att_stats and att_stats["total_records"] and int(att_stats["total_records"]) > 0:
                att_pct = round((float(att_stats["attended"]) / float(att_stats["total_records"])) * 100, 2)

            avg_p = round(float(stats["avg_percentage"]), 2) if stats and stats["avg_percentage"] is not None else 0.0
            if avg_p > 0:
                overall_scores.append(avg_p)

            tot_m = int(stats["total_entries"]) if stats and stats["total_entries"] else 0
            pass_c = int(stats["pass_count"]) if stats and stats["pass_count"] else 0
            pass_rate = round((pass_c / tot_m) * 100, 2) if tot_m > 0 else 0.0

            subject_analytics.append({
                "subject_id": sub_id,
                "subject_code": sub["subject_code"],
                "subject_name": sub["name"],
                "semester_name": sub["semester_name"],
                "enrolled_students": enrolled_count,
                "total_assessments_logged": tot_m,
                "class_average_percentage": avg_p,
                "highest_percentage": round(float(stats["max_percentage"]), 2) if stats and stats["max_percentage"] is not None else 0.0,
                "lowest_percentage": round(float(stats["min_percentage"]), 2) if stats and stats["min_percentage"] is not None else 0.0,
                "pass_rate_percentage": pass_rate,
                "attendance_rate_percentage": att_pct,
            })

        faculty_avg = round(sum(overall_scores) / len(overall_scores), 2) if overall_scores else 0.0

        return {
            "faculty": {
                "id": faculty["id"],
                "faculty_code": faculty["faculty_code"],
                "name": f"{faculty['first_name']} {faculty['last_name']}",
                "department": faculty["department"],
                "designation": faculty["designation"],
            },
            "summary": {
                "total_assigned_courses": len(assigned_subjects),
                "total_unique_students_taught": len(total_students_taught),
                "overall_teaching_average": faculty_avg,
            },
            "courses": subject_analytics,
        }

    @staticmethod
    def get_admin_analytics() -> Dict[str, Any]:
        """
        Generate institution-wide aggregated analytics and KPI overviews.
        Admin-only scope.
        """
        # 1. Total counts
        total_students = StudentRepository.count_students()
        total_subjects = db.query_one("SELECT COUNT(*) as c FROM subjects")["c"]
        total_semesters = db.query_one("SELECT COUNT(*) as c FROM semesters")["c"]
        total_faculty = db.query_one("SELECT COUNT(*) as c FROM faculty")["c"]

        # Active semester
        active_sem = db.query_one("SELECT name, academic_year FROM semesters WHERE is_active = TRUE LIMIT 1")

        # 2. Institution-wide Grade Distribution
        grade_dist_sql = """
            SELECT 
                SUM(CASE WHEN (marks_obtained / max_marks * 100) >= 90 THEN 1 ELSE 0 END) as grade_a_plus,
                SUM(CASE WHEN (marks_obtained / max_marks * 100) >= 80 AND (marks_obtained / max_marks * 100) < 90 THEN 1 ELSE 0 END) as grade_a,
                SUM(CASE WHEN (marks_obtained / max_marks * 100) >= 70 AND (marks_obtained / max_marks * 100) < 80 THEN 1 ELSE 0 END) as grade_b,
                SUM(CASE WHEN (marks_obtained / max_marks * 100) >= 60 AND (marks_obtained / max_marks * 100) < 70 THEN 1 ELSE 0 END) as grade_c,
                SUM(CASE WHEN (marks_obtained / max_marks * 100) >= 50 AND (marks_obtained / max_marks * 100) < 60 THEN 1 ELSE 0 END) as grade_d,
                SUM(CASE WHEN (marks_obtained / max_marks * 100) < 50 THEN 1 ELSE 0 END) as grade_f,
                COUNT(*) as total_marks
            FROM marks
        """
        g_row = db.query_one(grade_dist_sql)
        grade_distribution = {
            "A+": int(g_row["grade_a_plus"] or 0),
            "A": int(g_row["grade_a"] or 0),
            "B": int(g_row["grade_b"] or 0),
            "C": int(g_row["grade_c"] or 0),
            "D": int(g_row["grade_d"] or 0),
            "F": int(g_row["grade_f"] or 0),
            "total": int(g_row["total_marks"] or 0),
        }

        # 3. Departmental averages
        dept_sql = """
            SELECT 
                sub.department,
                COUNT(DISTINCT sub.id) as course_count,
                COUNT(m.id) as assessments_count,
                AVG(m.marks_obtained / m.max_marks * 100) as avg_score
            FROM subjects sub
            LEFT JOIN marks m ON sub.id = m.subject_id
            GROUP BY sub.department
            ORDER BY sub.department ASC
        """
        dept_rows = db.query_all(dept_sql)
        department_metrics = [
            {
                "department": r["department"],
                "course_count": int(r["course_count"]),
                "assessments_count": int(r["assessments_count"] or 0),
                "average_percentage": round(float(r["avg_score"]), 2) if r["avg_score"] is not None else 0.0,
            }
            for r in dept_rows
        ]

        # 4. Overall Attendance KPI
        att_kpi = db.query_one("""
            SELECT 
                COUNT(*) as total_sessions,
                SUM(CASE WHEN status IN ('Present', 'Excused') THEN 1 WHEN status = 'Late' THEN 0.5 ELSE 0 END) as attended
            FROM attendance
        """)
        overall_att_rate = 0.0
        if att_kpi and att_kpi["total_sessions"] and int(att_kpi["total_sessions"]) > 0:
            overall_att_rate = round((float(att_kpi["attended"]) / float(att_kpi["total_sessions"])) * 100, 2)

        # 5. At-risk students
        low_att_list = ReportService.get_low_attendance_report(threshold=75.0)

        return {
            "kpis": {
                "total_students": total_students,
                "total_faculty": total_faculty,
                "total_subjects": total_subjects,
                "total_semesters": total_semesters,
                "active_semester": f"{active_sem['name']} ({active_sem['academic_year']})" if active_sem else "None",
                "overall_attendance_percentage": overall_att_rate,
                "students_with_low_attendance": len(low_att_list),
            },
            "grade_distribution": grade_distribution,
            "department_metrics": department_metrics,
            "at_risk_students": low_att_list,
        }
