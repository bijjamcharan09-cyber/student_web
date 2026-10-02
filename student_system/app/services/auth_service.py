"""
Authentication service handling user verification, password hashing, and user creation.
"""

from typing import Any, Dict, Optional
from werkzeug.security import check_password_hash, generate_password_hash

from app.repositories.user_repo import UserRepository
from app.repositories.student_repo import StudentRepository
from app.repositories.faculty_repo import FacultyRepository
from app.utils.auth import generate_auth_token
from app.utils.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError


class AuthService:
    """Service handling credential verification and registration."""

    @staticmethod
    def authenticate(username_or_email: str, password: str) -> Dict[str, Any]:
        """Authenticate user by username or email and verify password hash."""
        if not username_or_email or not password:
            raise ValidationError("Both username/email and password are required.")

        user = UserRepository.get_by_username(username_or_email)
        if not user:
            user = UserRepository.get_by_email(username_or_email)

        if not user:
            raise UnauthorizedError("Invalid username or password.")

        if not user.get("is_active"):
            raise UnauthorizedError("This account has been deactivated.")

        if not check_password_hash(user["password_hash"], password):
            raise UnauthorizedError("Invalid username or password.")

        # Generate bearer token
        token = generate_auth_token(user["id"])

        user_clean = {k: v for k, v in user.items() if k != "password_hash"}
        return {
            "user": user_clean,
            "token": token,
        }

    @staticmethod
    def register_user(data: Dict[str, Any], requested_by_role: str = "Admin") -> Dict[str, Any]:
        """Register a new user account with role enforcement."""
        if requested_by_role != "Admin":
            raise UnauthorizedError("Only administrators can register new user accounts.")

        username = str(data.get("username", "")).strip().lower()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", "")).strip()
        role = str(data.get("role", "Student")).strip().capitalize()
        student_id = data.get("student_id")
        faculty_id = data.get("faculty_id")

        if not username or len(username) < 3:
            raise ValidationError("Username must be at least 3 characters.")
        if not email or "@" not in email:
            raise ValidationError("Valid email address is required.")
        if not password or len(password) < 6:
            raise ValidationError("Password must be at least 6 characters.")
        if role not in ("Admin", "Faculty", "Student"):
            raise ValidationError("Role must be Admin, Faculty, or Student.")

        if UserRepository.get_by_username(username):
            raise ConflictError(f"Username '{username}' is already in use.")
        if UserRepository.get_by_email(email):
            raise ConflictError(f"Email '{email}' is already registered.")

        if role == "Student" and student_id:
            if not StudentRepository.get_by_id(student_id):
                raise NotFoundError(f"Student with ID {student_id} does not exist.")
            if UserRepository.get_by_student_id(student_id):
                raise ConflictError("A user account already exists for this student.")

        if role == "Faculty" and faculty_id:
            if not FacultyRepository.get_by_id(faculty_id):
                raise NotFoundError(f"Faculty with ID {faculty_id} does not exist.")
            if UserRepository.get_by_faculty_id(faculty_id):
                raise ConflictError("A user account already exists for this faculty member.")

        password_hash = generate_password_hash(password)
        user_id = UserRepository.create({
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "role": role,
            "student_id": student_id,
            "faculty_id": faculty_id,
            "is_active": True,
        })

        created = UserRepository.get_by_id(user_id)
        return {k: v for k, v in created.items() if k != "password_hash"}

    @staticmethod
    def public_register(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Public self-registration accessible to everyone.
        Creates or links Student/Faculty records, creates the User credentials,
        and returns authenticated session credentials.
        """
        import random
        from datetime import datetime

        username = str(data.get("username", "")).strip().lower()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", "")).strip()
        role = str(data.get("role", "Student")).strip().capitalize()
        first_name = str(data.get("first_name", "")).strip() or username.capitalize()
        last_name = str(data.get("last_name", "")).strip() or "User"

        if not username or len(username) < 3:
            raise ValidationError("Username must be at least 3 characters long.")
        if not email or "@" not in email:
            raise ValidationError("A valid email address is required.")
        if not password or len(password) < 6:
            raise ValidationError("Password must be at least 6 characters long.")
        if role not in ("Admin", "Faculty", "Student"):
            role = "Student"

        if UserRepository.get_by_username(username):
            raise ConflictError(f"Username '{username}' is already in use. Please choose another.")
        if UserRepository.get_by_email(email):
            raise ConflictError(f"Email '{email}' is already registered. Please log in.")

        student_id = data.get("student_id")
        faculty_id = data.get("faculty_id")

        if role == "Student":
            roll_number = str(data.get("roll_number", "")).strip().upper()
            if not roll_number:
                roll_number = f"STU-{random.randint(10000, 99999)}"

            # Link existing student or provision new profile
            existing_student = StudentRepository.get_by_roll_number(roll_number)
            if not existing_student:
                existing_student = StudentRepository.get_by_email(email)

            if existing_student:
                student_id = existing_student["id"]
            else:
                student_id = StudentRepository.create({
                    "roll_number": roll_number,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "date_of_birth": data.get("date_of_birth") or "2000-01-01",
                    "gender": data.get("gender") or "Other",
                    "enrollment_date": datetime.now().strftime("%Y-%m-%d"),
                    "status": "Active",
                })

        elif role == "Faculty":
            faculty_code = str(data.get("faculty_code", "")).strip().upper()
            if not faculty_code:
                faculty_code = f"FAC-{random.randint(1000, 9999)}"

            existing_faculty = FacultyRepository.get_by_code(faculty_code)
            if not existing_faculty:
                existing_faculty = FacultyRepository.get_by_email(email)

            if existing_faculty:
                faculty_id = existing_faculty["id"]
            else:
                faculty_id = FacultyRepository.create({
                    "faculty_code": faculty_code,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "department": data.get("department") or "Computer Science",
                    "designation": data.get("designation") or "Lecturer",
                })

        # Create user account
        password_hash = generate_password_hash(password)
        UserRepository.create({
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "role": role,
            "student_id": student_id,
            "faculty_id": faculty_id,
            "is_active": True,
        })

        # Immediately authenticate so the new user can log in seamlessly
        return AuthService.authenticate(username, password)

