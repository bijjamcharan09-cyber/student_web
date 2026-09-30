"""
Repositories package initialization.
"""

from app.repositories.student_repo import StudentRepository
from app.repositories.subject_repo import SubjectRepository
from app.repositories.semester_repo import SemesterRepository
from app.repositories.mark_repo import MarkRepository
from app.repositories.attendance_repo import AttendanceRepository

__all__ = [
    "StudentRepository",
    "SubjectRepository",
    "SemesterRepository",
    "MarkRepository",
    "AttendanceRepository",
]
