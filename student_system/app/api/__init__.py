"""
API Blueprints package initialization.
"""

from app.api.students import students_bp
from app.api.subjects import subjects_bp
from app.api.semesters import semesters_bp
from app.api.marks import marks_bp
from app.api.attendance import attendance_bp
from app.api.reports import reports_bp

__all__ = [
    "students_bp",
    "subjects_bp",
    "semesters_bp",
    "marks_bp",
    "attendance_bp",
    "reports_bp",
]
