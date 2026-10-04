"""
Authentication service handling user verification, password hashing, and user creation.
"""

from datetime import datetime
import random
import re
from typing import Any, Dict, List, Optional
from werkzeug.security import check_password_hash, generate_password_hash

from app.repositories.user_repo import UserRepository
from app.repositories.student_repo import StudentRepository
from app.repositories.faculty_repo import FacultyRepository
from app.utils.auth import generate_auth_token
from app.utils.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError, ValidationError


class AuthService:
    """Service handling credential verification and admin-only registration."""

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
        """
        Register a new user account with strict Admin-only authorization.
        Can create Student, Faculty, or Admin accounts.
        """
        if requested_by_role != "Admin":
            raise ForbiddenError("Access denied: Only administrators can register new user accounts.")

        # Parse name fields
        raw_name = str(data.get("name", "")).strip()
        first_name = str(data.get("first_name", "")).strip()
        last_name = str(data.get("last_name", "")).strip()

        if raw_name and not (first_name or last_name):
            parts = raw_name.split(None, 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", "")).strip()
        role = str(data.get("role", "Student")).strip().capitalize()

        # Generate username if not provided
        raw_username = str(data.get("username", "")).strip().lower()
        if not raw_username:
            if email and "@" in email:
                base_username = re.sub(r'[^a-z0-9_]', '', email.split("@")[0].lower())
            elif first_name:
                base_username = re.sub(r'[^a-z0-9_]', '', f"{first_name}_{last_name}".strip("_").lower())
            else:
                base_username = "user"
            
            # Check availability and deduplicate
            candidate = base_username
            idx = 1
            while UserRepository.get_by_username(candidate):
                candidate = f"{base_username}_{idx}"
                idx += 1
            username = candidate
        else:
            username = raw_username

        if not username or len(username) < 3:
            raise ValidationError("Username must be at least 3 characters.")
        if not email or "@" not in email:
            raise ValidationError("A valid email address is required.")
        if not password or len(password) < 6:
            raise ValidationError("Password must be at least 6 characters.")
        if role not in ("Admin", "Faculty", "Student"):
            raise ValidationError("Role must be Admin, Faculty, or Student.")

        if UserRepository.get_by_username(username):
            raise ConflictError(f"Username '{username}' is already in use.")
        if UserRepository.get_by_email(email):
            raise ConflictError(f"Email '{email}' is already registered.")

        student_id = data.get("student_id")
        faculty_id = data.get("faculty_id")

        if role == "Student":
            if student_id:
                if not StudentRepository.get_by_id(student_id):
                    raise NotFoundError(f"Student with ID {student_id} does not exist.")
                if UserRepository.get_by_student_id(student_id):
                    raise ConflictError("A user account already exists for this student.")
            else:
                # Check if student exists by email or roll_number
                roll_number = str(data.get("roll_number", "")).strip().upper()
                existing_student = None
                if roll_number:
                    existing_student = StudentRepository.get_by_roll_number(roll_number)
                if not existing_student:
                    existing_student = StudentRepository.get_by_email(email)

                if existing_student:
                    student_id = existing_student["id"]
                    if UserRepository.get_by_student_id(student_id):
                        raise ConflictError("A user account already exists for this student.")
                else:
                    if not roll_number:
                        roll_number = f"STU-{random.randint(10000, 99999)}"
                    student_id = StudentRepository.create({
                        "roll_number": roll_number,
                        "first_name": first_name or username.capitalize(),
                        "last_name": last_name or "",
                        "email": email,
                        "date_of_birth": data.get("date_of_birth") or "2002-01-01",
                        "gender": data.get("gender") or "Other",
                        "enrollment_date": datetime.now().strftime("%Y-%m-%d"),
                        "status": "Active",
                    })

        elif role == "Faculty":
            if faculty_id:
                if not FacultyRepository.get_by_id(faculty_id):
                    raise NotFoundError(f"Faculty with ID {faculty_id} does not exist.")
                if UserRepository.get_by_faculty_id(faculty_id):
                    raise ConflictError("A user account already exists for this faculty member.")
            else:
                faculty_code = str(data.get("faculty_code", "")).strip().upper()
                existing_faculty = None
                if faculty_code:
                    existing_faculty = FacultyRepository.get_by_code(faculty_code)
                if not existing_faculty:
                    existing_faculty = FacultyRepository.get_by_email(email)

                if existing_faculty:
                    faculty_id = existing_faculty["id"]
                    if UserRepository.get_by_faculty_id(faculty_id):
                        raise ConflictError("A user account already exists for this faculty member.")
                else:
                    if not faculty_code:
                        faculty_code = f"FAC-{random.randint(1000, 9999)}"
                    faculty_id = FacultyRepository.create({
                        "faculty_code": faculty_code,
                        "first_name": first_name or username.capitalize(),
                        "last_name": last_name or "",
                        "email": email,
                        "department": data.get("department") or "Computer Science",
                        "designation": data.get("designation") or "Lecturer",
                    })

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
    def register_student_public(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Public self-service student registration.
        Strictly forces role to 'Student' and strips any attempts to gain Admin/Faculty privileges.
        Creates or links an associated student profile record.
        """
        # 1. Strip/ignore any client-provided role or faculty assignments
        # role is unconditionally forced to 'Student'
        forced_role = "Student"

        # 2. Parse name fields
        raw_name = str(data.get("name", "") or data.get("full_name", "")).strip()
        first_name = str(data.get("first_name", "")).strip()
        last_name = str(data.get("last_name", "")).strip()

        if raw_name and not (first_name or last_name):
            parts = raw_name.split(None, 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", "")).strip()
        confirm_password = str(data.get("confirm_password", "")).strip() if "confirm_password" in data else None
        roll_number = str(data.get("roll_number", "")).strip().upper()

        # 3. Input validations
        if not email or "@" not in email:
            raise ValidationError("A valid email address is required.")

        if confirm_password is not None and password != confirm_password:
            raise ValidationError("Passwords do not match.")

        if not password or len(password) < 6:
            raise ValidationError("Password must be at least 6 characters long.")

        # 4. Generate or validate username
        raw_username = str(data.get("username", "")).strip().lower()
        if not raw_username:
            if email and "@" in email:
                base_username = re.sub(r'[^a-z0-9_]', '', email.split("@")[0].lower())
            elif first_name:
                base_username = re.sub(r'[^a-z0-9_]', '', f"{first_name}_{last_name}".strip("_").lower())
            else:
                base_username = "student"

            candidate = base_username
            idx = 1
            while UserRepository.get_by_username(candidate):
                candidate = f"{base_username}_{idx}"
                idx += 1
            username = candidate
        else:
            username = raw_username

        if not username or len(username) < 3:
            raise ValidationError("Username must be at least 3 characters.")

        # 5. Check uniqueness in users table
        if UserRepository.get_by_username(username):
            raise ConflictError(f"Username '{username}' is already in use.")
        if UserRepository.get_by_email(email):
            raise ConflictError(f"Email '{email}' is already registered.")

        # 6. Student record linking / creation
        existing_student = None
        if roll_number:
            existing_student = StudentRepository.get_by_roll_number(roll_number)
            if existing_student:
                # Security check: if student already has a user account
                if UserRepository.get_by_student_id(existing_student["id"]):
                    raise ConflictError("A user account already exists for this student roll number.")
                # Security check: if student record has an email that differs from registration email
                if existing_student.get("email") and existing_student["email"].lower() != email:
                    raise ConflictError("The provided roll number is registered to a different email address.")

        if not existing_student:
            student_by_email = StudentRepository.get_by_email(email)
            if student_by_email:
                if UserRepository.get_by_student_id(student_by_email["id"]):
                    raise ConflictError("A user account already exists for this student email.")
                existing_student = student_by_email

        if existing_student:
            student_id = existing_student["id"]
        else:
            if not roll_number:
                for _ in range(10):
                    candidate_roll = f"STU-{random.randint(10000, 99999)}"
                    if not StudentRepository.get_by_roll_number(candidate_roll):
                        roll_number = candidate_roll
                        break
                if not roll_number:
                    roll_number = f"STU-{int(datetime.now().timestamp())}"

            student_id = StudentRepository.create({
                "roll_number": roll_number,
                "first_name": first_name or username.capitalize(),
                "last_name": last_name or "",
                "email": email,
                "date_of_birth": data.get("date_of_birth") or "2002-01-01",
                "gender": data.get("gender") or "Other",
                "enrollment_date": datetime.now().strftime("%Y-%m-%d"),
                "status": "Active",
                "address": data.get("address") or "",
            })

        # 7. Create user record with forced Student role and no faculty_id
        password_hash = generate_password_hash(password)
        user_id = UserRepository.create({
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "role": forced_role,
            "student_id": student_id,
            "faculty_id": None,
            "is_active": True,
        })

        created = UserRepository.get_by_id(user_id)
        return {k: v for k, v in created.items() if k != "password_hash"}

    @staticmethod
    def list_users(role: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List user accounts (Admin only)."""
        return UserRepository.list_users(role=role, limit=limit, offset=offset)

    @staticmethod
    def update_user_account(user_id: int, data: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing user account with protection against self-lockout and admin loss."""
        if current_user.get("role") != "Admin":
            raise ForbiddenError("Only Administrators can update user accounts.")

        target_user = UserRepository.get_by_id(user_id)
        if not target_user:
            raise NotFoundError(f"User with ID {user_id} not found.")

        update_payload: Dict[str, Any] = {}

        # Email
        if "email" in data and data["email"]:
            new_email = str(data["email"]).strip().lower()
            if new_email != target_user["email"]:
                existing_email = UserRepository.get_by_email(new_email)
                if existing_email and existing_email["id"] != user_id:
                    raise ConflictError(f"Email '{new_email}' is already in use by another account.")
                update_payload["email"] = new_email

        # Username
        if "username" in data and data["username"]:
            new_username = str(data["username"]).strip()
            if new_username != target_user["username"]:
                existing_user = UserRepository.get_by_username(new_username)
                if existing_user and existing_user["id"] != user_id:
                    raise ConflictError(f"Username '{new_username}' is already taken.")
                update_payload["username"] = new_username

        # Password
        if "password" in data and data["password"]:
            pwd = str(data["password"]).strip()
            if len(pwd) < 6:
                raise ValidationError("Password must be at least 6 characters long.")
            update_payload["password_hash"] = generate_password_hash(pwd)

        # Role change
        if "role" in data and data["role"]:
            new_role = str(data["role"]).strip().capitalize()
            if new_role not in ("Admin", "Faculty", "Student"):
                raise ValidationError(f"Invalid role '{new_role}'. Must be Admin, Faculty, or Student.")

            # Prevent Admin from demoting their own account
            if target_user["id"] == current_user["id"] and new_role != "Admin":
                raise ForbiddenError("You cannot revoke your own Administrator privileges.")

            # Prevent demoting the only active Admin
            if target_user["role"] == "Admin" and new_role != "Admin":
                if UserRepository.count_active_admins() <= 1:
                    raise ForbiddenError("Cannot demote the only remaining active Administrator.")

            update_payload["role"] = new_role

        # Active status
        if "is_active" in data:
            is_active = bool(data["is_active"])
            # Prevent deactivating own account
            if target_user["id"] == current_user["id"] and not is_active:
                raise ForbiddenError("You cannot deactivate your own active Administrator account.")
            # Prevent deactivating the only active Admin
            if target_user["role"] == "Admin" and not is_active:
                if UserRepository.count_active_admins() <= 1:
                    raise ForbiddenError("Cannot deactivate the only remaining active Administrator.")
            update_payload["is_active"] = is_active

        if update_payload:
            UserRepository.update_user(user_id, update_payload)

        updated = UserRepository.get_by_id(user_id)
        return {k: v for k, v in updated.items() if k != "password_hash"}

    @staticmethod
    def delete_user_account(user_id: int, current_user: Dict[str, Any]) -> bool:
        """Delete an existing user account with protection against self-deletion and admin loss."""
        if current_user.get("role") != "Admin":
            raise ForbiddenError("Only Administrators can delete user accounts.")

        target_user = UserRepository.get_by_id(user_id)
        if not target_user:
            raise NotFoundError(f"User with ID {user_id} not found.")

        # Prevent deleting own account
        if target_user["id"] == current_user["id"]:
            raise ForbiddenError("You cannot delete your own active Administrator account.")

        # Prevent deleting the only active Admin
        if target_user["role"] == "Admin":
            if UserRepository.count_active_admins() <= 1:
                raise ForbiddenError("Cannot delete the only remaining active Administrator.")

        UserRepository.delete_user(user_id)
        return True
