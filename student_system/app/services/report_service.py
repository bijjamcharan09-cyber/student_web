"""
Report service for generating student transcripts, semester summaries, and academic alerts.
"""

from typing import Any, Dict, List, Optional
from collections import defaultdict
from app.repositories.student_repo import StudentRepository
from app.repositories.semester_repo import SemesterRepository
from app.repositories.mark_repo import MarkRepository
from app.repositories.attendance_repo import AttendanceRepository
from app.services.mark_service import enrich_mark
from app.services.attendance_service import AttendanceService
from app.utils.exceptions import NotFoundError


class ReportService:
    """Service generating academic transcripts, analytics, and reports."""

    @staticmethod
    def get_student_transcript(student_id: int) -> Dict[str, Any]:
        """
        Generate full academic transcript with CGPA and semester GPA.
        Calculates credit-weighted GPA: sum(credits * grade_point) / sum(credits)
        """
        student = StudentRepository.get_by_id(student_id)
        if not student:
            raise NotFoundError(f"Student with ID {student_id} not found.")

        # Get all marks for student
        raw_marks = MarkRepository.list_marks(student_id=student_id, limit=500)
        enriched_marks = [enrich_mark(m) for m in raw_marks]

        # Group marks by semester and subject
        semesters_dict = defaultdict(lambda: {
            "semester_id": None,
            "semester_name": "",
            "subjects": defaultdict(lambda: {
                "subject_id": None,
                "subject_code": "",
                "subject_name": "",
                "credits": 0.0,
                "assessments": [],
                "total_obtained": 0.0,
                "total_max": 0.0,
            }),
            "total_credits": 0.0,
            "earned_points": 0.0,
        })

        for m in enriched_marks:
            sem_id = m["semester_id"]
            sem_name = m.get("semester_name", f"Semester {sem_id}")
            sub_id = m["subject_id"]

            sem_entry = semesters_dict[sem_id]
            sem_entry["semester_id"] = sem_id
            sem_entry["semester_name"] = sem_name

            sub_entry = sem_entry["subjects"][sub_id]
            sub_entry["subject_id"] = sub_id
            sub_entry["subject_code"] = m.get("subject_code", "")
            sub_entry["subject_name"] = m.get("subject_name", "")
            sub_entry["credits"] = float(m.get("credits", 3.0))

            sub_entry["assessments"].append({
                "exam_type": m["exam_type"],
                "marks_obtained": float(m["marks_obtained"]),
                "max_marks": float(m["max_marks"]),
                "percentage": m["percentage"],
                "grade": m["grade"],
                "grade_point": m["grade_point"],
            })
            sub_entry["total_obtained"] += float(m["marks_obtained"])
            sub_entry["total_max"] += float(m["max_marks"])

        cumulative_credits = 0.0
        cumulative_points = 0.0
        semester_reports = []

        for sem_id, sem_data in sorted(semesters_dict.items()):
            sem_credits = 0.0
            sem_points = 0.0
            subjects_list = []

            for sub_id, sub_data in sem_data["subjects"].items():
                credits = sub_data["credits"]
                total_obt = sub_data["total_obtained"]
                total_mx = sub_data["total_max"]
                final_pct = round((total_obt / total_mx) * 100, 2) if total_mx > 0 else 0.0

                from app.services.mark_service import compute_grade_and_points
                sub_grade, sub_pts = compute_grade_and_points(total_obt, total_mx)

                sub_data["overall_percentage"] = final_pct
                sub_data["overall_grade"] = sub_grade
                sub_data["grade_point"] = sub_pts

                sem_credits += credits
                sem_points += (credits * sub_pts)
                subjects_list.append(sub_data)

            sem_gpa = round(sem_points / sem_credits, 2) if sem_credits > 0 else 0.0
            cumulative_credits += sem_credits
            cumulative_points += sem_points

            semester_reports.append({
                "semester_id": sem_id,
                "semester_name": sem_data["semester_name"],
                "total_credits": sem_credits,
                "semester_gpa": sem_gpa,
                "subjects": subjects_list,
            })

        cgpa = round(cumulative_points / cumulative_credits, 2) if cumulative_credits > 0 else 0.0

        # Get attendance summary
        attendance_info = AttendanceService.get_student_summary(student_id)

        return {
            "student": {
                "id": student["id"],
                "roll_number": student["roll_number"],
                "name": f"{student['first_name']} {student['last_name']}",
                "email": student["email"],
                "status": student["status"],
                "current_semester": student.get("current_semester_name"),
            },
            "academic_summary": {
                "total_semesters_completed": len(semester_reports),
                "total_credits_earned": cumulative_credits,
                "cumulative_gpa": cgpa,
            },
            "semesters": semester_reports,
            "attendance": attendance_info["overall_summary"],
        }

    @staticmethod
    def get_low_attendance_report(threshold: float = 75.0) -> List[Dict[str, Any]]:
        """Identify students whose overall attendance falls below threshold."""
        students = StudentRepository.list_students(limit=1000)
        at_risk = []

        for st in students:
            summary = AttendanceService.get_student_summary(st["id"])
            overall = summary["overall_summary"]
            if overall["total_sessions"] > 0 and overall["attendance_percentage"] < threshold:
                at_risk.append({
                    "student_id": st["id"],
                    "roll_number": st["roll_number"],
                    "student_name": f"{st['first_name']} {st['last_name']}",
                    "email": st["email"],
                    "status": st["status"],
                    "total_sessions": overall["total_sessions"],
                    "attended_sessions": overall["present"] + overall["excused"],
                    "attendance_percentage": overall["attendance_percentage"],
                    "threshold": threshold,
                })

        return at_risk
