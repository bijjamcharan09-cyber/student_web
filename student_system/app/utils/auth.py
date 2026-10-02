"""
Authentication and Role-Based Access Control (RBAC) security module.
Enforces backend authorization, session/token verification, and IDOR prevention.
"""

from functools import wraps
from typing import Callable, List, Optional
from flask import current_app, g, request, session
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from app.repositories.faculty_repo import FacultyRepository
from app.repositories.user_repo import UserRepository
from app.utils.exceptions import ForbiddenError, UnauthorizedError
from app.utils.responses import error_response


def get_serializer() -> URLSafeTimedSerializer:
    """Return itsdangerous serializer configured with app secret key."""
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="sms-v2-auth-token")


def generate_auth_token(user_id: int) -> str:
    """Generate a signed, tamper-proof bearer token for API authorization."""
    s = get_serializer()
    return s.dumps({"user_id": user_id})


def verify_auth_token(token: str, max_age: int = 86400) -> Optional[int]:
    """Verify signed bearer token and extract user_id if valid and not expired."""
    s = get_serializer()
    try:
        data = s.loads(token, max_age=max_age)
        return data.get("user_id")
    except (BadSignature, SignatureExpired, Exception):
        return None


def get_current_user() -> Optional[dict]:
    """
    Resolve the currently authenticated user from session or Bearer token header.
    Caches result on flask.g for request duration.
    """
    if hasattr(g, "current_user") and g.current_user is not None:
        return g.current_user

    user_id = None

    # 1. Check Flask signed cookie session
    if "user_id" in session:
        user_id = session.get("user_id")

    # 2. Check Authorization Bearer header
    if not user_id:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            user_id = verify_auth_token(token)

    # 3. Check X-Auth-Token header
    if not user_id:
        x_token = request.headers.get("X-Auth-Token", "").strip()
        if x_token:
            user_id = verify_auth_token(x_token)

    if not user_id:
        g.current_user = None
        return None

    user = UserRepository.get_by_id(user_id)
    if user and user.get("is_active"):
        g.current_user = user
        return user

    g.current_user = None
    return None


def login_required(f: Callable) -> Callable:
    """Decorator ensuring that client is authenticated."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return error_response("Authentication required to access this resource.", "UNAUTHORIZED", 401)
        return f(*args, **kwargs)
    return decorated_function


def roles_required(*allowed_roles: str) -> Callable:
    """
    Decorator enforcing Role-Based Access Control (RBAC).
    Checks backend user role strictly on the Flask server.
    """
    allowed_set = {str(r).strip().title() for r in allowed_roles}

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return error_response("Authentication required.", "UNAUTHORIZED", 401)

            user_role = str(user.get("role") or "").strip().title()
            if user_role not in allowed_set:
                return error_response(
                    f"Access forbidden: Role '{user_role}' is not authorized for this action.",
                    "FORBIDDEN",
                    403,
                )
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def check_student_scope(target_student_id: int):
    """
    Enforces Object-Level Authorization / IDOR Protection.
    - Admin: Full access to all students.
    - Faculty: Access only to students enrolled in their assigned subjects.
    - Student: Access STRICTLY to their own student profile/data.
    """
    user = get_current_user()
    if not user:
        raise UnauthorizedError("Authentication required.")

    role = str(user.get("role") or "").strip().title()

    if role == "Admin":
        return True

    if role == "Student":
        own_id = user.get("student_id")
        if not own_id or int(own_id) != int(target_student_id):
            raise ForbiddenError("Access denied: You are only permitted to access your own student records.")
        return True

    if role == "Faculty":
        faculty_id = user.get("faculty_id")
        if not faculty_id:
            raise ForbiddenError("Faculty profile not associated with this account.")
        is_taught = FacultyRepository.is_student_taught_by_faculty(faculty_id, target_student_id)
        if not is_taught:
            raise ForbiddenError("Access denied: This student is not enrolled in any of your assigned subjects.")
        return True

    raise ForbiddenError("Access forbidden.")


def check_subject_management_scope(subject_id: int, semester_id: Optional[int] = None):
    """
    Enforces authorization on course marks/attendance management.
    - Admin: Full access.
    - Faculty: Only permitted if assigned to this subject.
    - Student: Prohibited from management operations.
    """
    user = get_current_user()
    if not user:
        raise UnauthorizedError("Authentication required.")

    role = str(user.get("role") or "").strip().title()

    if role == "Admin":
        return True

    if role == "Faculty":
        faculty_id = user.get("faculty_id")
        if not faculty_id:
            raise ForbiddenError("Faculty profile not linked.")
        if not FacultyRepository.is_faculty_assigned_to_subject(faculty_id, subject_id, semester_id):
            raise ForbiddenError("Access denied: You are not assigned to instruct or manage this subject.")
        return True

    raise ForbiddenError("Access denied: Students cannot manage course marks or attendance.")
