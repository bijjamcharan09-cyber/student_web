"""
Repositories package initialization.
"""

from app.repositories.student_repo import StudentRepository
from app.repositories.subject_repo import SubjectRepository
from app.repositories.semester_repo import SemesterRepository
from app.repositories.mark_repo import MarkRepository
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.user_repo import UserRepository
from app.repositories.faculty_repo import FacultyRepository

__all__ = [
    "StudentRepository",
    "SubjectRepository",
    "SemesterRepository",
    "MarkRepository",
    "AttendanceRepository",
    "UserRepository",
    "FacultyRepository",
]

