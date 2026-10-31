"""
Authentication, Multi-Organisation Scoping, and Role-Based Access Control (RBAC) security module.
Enforces backend authorization, multi-tenant isolation, session/token verification, and IDOR prevention.
"""

from functools import wraps
from typing import Callable, List, Optional, Set
from flask import current_app, g, request, session
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from app.repositories.faculty_repo import FacultyRepository
from app.repositories.student_repo import StudentRepository
from app.repositories.subject_repo import SubjectRepository
from app.repositories.user_repo import UserRepository
from app.utils.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from app.utils.responses import error_response

# In-memory revocation set for revoked bearer tokens
_REVOKED_TOKENS: Set[str] = set()


def is_safe_url(target: Optional[str]) -> bool:
    """
    Validate that target URL is a safe internal relative path to prevent Open Redirect attacks.
    Must start with a single '/', cannot start with '//' or '/\\', cannot contain '\\' or scheme.
    """
    if not target or not isinstance(target, str):
        return False
    target = target.strip()
    if not target.startswith("/"):
        return False
    if target.startswith("//") or target.startswith("/\\"):
        return False
    path_part = target.split("?")[0].split("#")[0]
    if ":" in path_part or "\\" in target:
        return False
    return True


def get_serializer() -> URLSafeTimedSerializer:
    """Return itsdangerous serializer configured with app secret key."""
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="sms-v2-auth-token")


def generate_auth_token(user_id: int) -> str:
    """Generate a signed, tamper-proof bearer token for API authorization."""
    s = get_serializer()
    return s.dumps({"user_id": user_id})


def revoke_token(token: str) -> None:
    """Revoke a bearer token so it can no longer be used for authentication."""
    if token:
        _REVOKED_TOKENS.add(token.strip())


def verify_auth_token(token: str, max_age: int = 86400) -> Optional[int]:
    """Verify signed bearer token and extract user_id if valid, not expired, and not revoked."""
    if not token or token.strip() in _REVOKED_TOKENS:
        return None
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


# RBAC Permissions Mapping
RBAC_PERMISSIONS = {
    # 1. Global Administration (Super Admin / Admin only)
    "SELECT_ORGANISATION": {"Admin", "Super Admin"},
    "SWITCH_ORGANISATION": {"Admin", "Super Admin"},
    "MANAGE_ORGANISATIONS": {"Admin", "Super Admin"},
    "SUSPEND_ORGANISATIONS": {"Admin", "Super Admin"},
    "GLOBAL_USER_ACCESS": {"Admin", "Super Admin"},
    "ASSIGN_ORGANISATION_MEMBERSHIP": {"Admin", "Super Admin"},
    "REASSIGN_STUDENT_ORGANISATION": {"Admin", "Super Admin"},
    "MANAGE_GLOBAL_RBAC": {"Admin", "Super Admin"},
    "GLOBAL_VIEW": {"Admin", "Super Admin"},

    # 2. Organisation Operational Permissions (Scoped to Own Organisation)
    "ORG_VIEW_DASHBOARD": {"Admin", "Super Admin", "Organisation", "Organization"},
    "ORG_MANAGE_STUDENTS": {"Admin", "Super Admin", "Organisation", "Organization"},
    "ORG_MANAGE_FACULTY": {"Admin", "Super Admin", "Organisation", "Organization"},
    "ORG_MANAGE_SUBJECTS": {"Admin", "Super Admin", "Organisation", "Organization"},
    "ORG_MANAGE_SEMESTERS": {"Admin", "Super Admin", "Organisation", "Organization"},
    "ORG_MANAGE_MARKS": {"Admin", "Super Admin", "Organisation", "Organization"},
    "ORG_MANAGE_ATTENDANCE": {"Admin", "Super Admin", "Organisation", "Organization"},
    "ORG_VIEW_REPORTS": {"Admin", "Super Admin", "Organisation", "Organization"},
    "ORG_VIEW_ANALYTICS": {"Admin", "Super Admin", "Organisation", "Organization"},

    # 3. Organisation Scoped User Management
    "ORG_VIEW_USERS": {"Admin", "Super Admin", "Organisation", "Organization"},
    "ORG_EDIT_USERS": {"Admin", "Super Admin", "Organisation", "Organization"},
    "ORG_CREATE_USERS": {"Admin", "Super Admin", "Organisation", "Organization"},
    "ORG_DELETE_USERS": {"Admin", "Super Admin", "Organisation", "Organization"},
    "ORG_ASSIGN_ROLES": {"Admin", "Super Admin", "Organisation", "Organization"},

    # 4. Standard Operational Mappings (for existing decorators)
    "MANAGE_USERS": {"Admin", "Super Admin", "Organisation", "Organization"},
    "MANAGE_STUDENTS": {"Admin", "Super Admin", "Organisation", "Organization"},
    "MANAGE_SUBJECTS": {"Admin", "Super Admin", "Organisation", "Organization"},
    "MANAGE_SEMESTERS": {"Admin", "Super Admin", "Organisation", "Organization"},
    "RECORD_MARKS": {"Admin", "Super Admin", "Organisation", "Organization", "Faculty"},
    "RECORD_ATTENDANCE": {"Admin", "Super Admin", "Organisation", "Organization", "Faculty"},
    "VIEW_CLASS_ATTENDANCE": {"Admin", "Super Admin", "Organisation", "Organization", "Faculty"},
    "VIEW_ANALYTICS": {"Admin", "Super Admin", "Organisation", "Organization", "Faculty", "Student"},

    # 5. Student Scoped Permissions
    "VIEW_OWN_PROFILE": {"Admin", "Super Admin", "Organisation", "Organization", "Faculty", "Student"},
    "VIEW_OWN_MARKS": {"Admin", "Super Admin", "Organisation", "Organization", "Faculty", "Student"},
    "VIEW_OWN_ATTENDANCE": {"Admin", "Super Admin", "Organisation", "Organization", "Faculty", "Student"},
    "MARK_OWN_ATTENDANCE_GPS": {"Student"},
}


def has_permission(user_or_role, permission_name: str) -> bool:
    """
    Check if a user dict or role string possesses a given RBAC permission.
    """
    if isinstance(user_or_role, dict):
        role = str(user_or_role.get("role") or "").strip().title()
    else:
        role = str(user_or_role or "").strip().title()
    allowed = RBAC_PERMISSIONS.get(permission_name.upper())
    if not allowed:
        return False
    return role in allowed


def can_select_organisation(user: Optional[dict] = None) -> bool:
    """
    RBAC check: Only Super Administrator / Admin can select or switch organisations.
    """
    if user is None:
        user = get_current_user()
    if not user:
        return False
    return has_permission(user, "SELECT_ORGANISATION")


def permission_required(*permission_names: str) -> Callable:
    """
    Decorator enforcing granular RBAC permissions.
    Checks whether the authenticated user has at least one of the specified permissions.
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return error_response("Authentication required.", "UNAUTHORIZED", 401)

            has_any = any(has_permission(user, perm) for perm in permission_names)
            if not has_any:
                user_role = str(user.get("role") or "").strip().title()
                return error_response(
                    f"Access forbidden: Role '{user_role}' lacks permission for {', '.join(permission_names)}.",
                    "FORBIDDEN",
                    403,
                )
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def roles_required(*allowed_roles: str) -> Callable:
    """
    Decorator enforcing Role-Based Access Control (RBAC).
    Checks backend user role strictly on the Flask server.
    Supports Super Admin / Admin equivalence and Organisation / Organization equivalence.
    """
    allowed_set = set()
    for r in allowed_roles:
        normalized = str(r).strip().title()
        allowed_set.add(normalized)
        if normalized in ("Admin", "Super Admin"):
            allowed_set.add("Admin")
            allowed_set.add("Super Admin")
        if normalized in ("Organisation", "Organization"):
            allowed_set.add("Organisation")
            allowed_set.add("Organization")

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


def check_organisation_scope(target_organisation_id: Optional[int]) -> bool:
    """
    Enforces multi-organisation tenant isolation.
    - Super Admin / Admin: Global access across all organisations.
    - Organisation / Faculty / Student: Strictly restricted to their own organisation.
    """
    user = get_current_user()
    if not user:
        raise UnauthorizedError("Authentication required.")

    role = str(user.get("role") or "").strip().title()
    if role in ("Admin", "Super Admin"):
        return True

    if target_organisation_id is None:
        return True

    user_org_id = user.get("organisation_id")
    if user_org_id is None or int(user_org_id) != int(target_organisation_id):
        raise ForbiddenError("Access denied: You do not have permission to access records belonging to another organisation.")

    return True


def get_effective_organisation_id() -> Optional[int]:
    """
    Resolves the organisation ID that the current user is authorized to query.
    - Super Admin / Admin (has SELECT_ORGANISATION permission):
      1. Explicit query parameter `?organisation_id=`
      2. Explicit header `X-Organisation-ID`
      3. Active session selection `session["selected_organisation_id"]`
      4. If none set, returns None (global view across all organisations).
    - Organisation / Faculty / Student:
      Strictly restricted to user['organisation_id'] from trusted database profile.
      Cannot override via query, header, or session.
    """
    user = get_current_user()
    if not user:
        return None

    if can_select_organisation(user):
        raw_org = request.args.get("organisation_id") or request.headers.get("X-Organisation-ID")
        if raw_org is not None and str(raw_org).strip() != "":
            raw_str = str(raw_org).strip().lower()
            if raw_str in ("0", "none", "null", "all"):
                return None
            if raw_str.isdigit() and int(raw_str) > 0:
                return int(raw_str)

        selected = session.get("selected_organisation_id")
        if selected is not None and str(selected).isdigit() and int(selected) > 0:
            return int(selected)

        return None

    return int(user.get("organisation_id") or 1)


def check_student_scope(target_student_id: int) -> bool:
    """
    Enforces Object-Level Authorization / IDOR Protection & Organisation Isolation:
    - Super Admin / Admin: Full access to all students across all organisations.
    - Organisation: Full access to students belonging to their own organisation.
    - Faculty: Access only to students enrolled in their assigned subjects within their organisation.
    - Student: Access STRICTLY to their own student profile/data.
    """
    user = get_current_user()
    if not user:
        raise UnauthorizedError("Authentication required.")

    student = StudentRepository.get_by_id(target_student_id)
    if not student:
        raise NotFoundError(f"Student with ID {target_student_id} not found.")

    role = str(user.get("role") or "").strip().title()

    # Enforce organisation isolation
    check_organisation_scope(student.get("organisation_id"))

    if role in ("Admin", "Super Admin"):
        return True

    if role in ("Organisation", "Organization"):
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


def check_subject_management_scope(subject_id: int, semester_id: Optional[int] = None) -> bool:
    """
    Enforces authorization on course marks/attendance management & Organisation Isolation:
    - Super Admin / Admin: Full access.
    - Organisation: Full access to subjects within their organisation.
    - Faculty: Only permitted if assigned to this subject within their organisation.
    - Student: Prohibited from management operations.
    """
    user = get_current_user()
    if not user:
        raise UnauthorizedError("Authentication required.")

    subject = SubjectRepository.get_by_id(subject_id)
    if not subject:
        raise NotFoundError(f"Subject with ID {subject_id} not found.")

    # Enforce organisation isolation
    check_organisation_scope(subject.get("organisation_id"))

    role = str(user.get("role") or "").strip().title()

    if role in ("Admin", "Super Admin"):
        return True

    if role in ("Organisation", "Organization"):
        return True

    if role == "Faculty":
        faculty_id = user.get("faculty_id")
        if not faculty_id:
            raise ForbiddenError("Faculty profile not linked.")
        if not FacultyRepository.is_faculty_assigned_to_subject(faculty_id, subject_id, semester_id):
            raise ForbiddenError("Access denied: You are not assigned to instruct or manage this subject.")
        return True

    raise ForbiddenError("Access denied: Students cannot manage course marks or attendance.")
