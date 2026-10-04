"""
Authentication API Blueprint for login, logout, profile checks, and account registration.
"""

from flask import Blueprint, g, request, session
from app.services.auth_service import AuthService
from app.utils.auth import get_current_user, login_required, roles_required
from app.utils.responses import api_response

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate with username/password and return session cookie + bearer token."""
    payload = request.get_json(silent=True) or {}
    username = payload.get("username", "").strip()
    password = payload.get("password", "").strip()

    result = AuthService.authenticate(username, password)
    user = result["user"]
    token = result["token"]

    # Set server-side session
    session["user_id"] = user["id"]
    session["role"] = user["role"]

    return api_response(
        data={"user": user, "token": token},
        message=f"Welcome {user['username']}! Logged in successfully.",
    )


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Clear server-side session."""
    session.clear()
    g.current_user = None
    return api_response(message="Logged out successfully.")


@auth_bp.route("/me", methods=["GET"])
@login_required
def get_current_profile():
    """Get the currently authenticated user profile and roles."""
    user = get_current_user()
    user_clean = {k: v for k, v in user.items() if k != "password_hash"}
    return api_response(data=user_clean, message="Authenticated profile retrieved successfully.")


@auth_bp.route("/signup", methods=["POST"])
def public_student_signup():
    """Public self-registration endpoint for Students only."""
    payload = request.get_json(silent=True) or request.form.to_dict() or {}
    user = AuthService.register_student_public(payload)
    return api_response(data=user, message="Student account registered successfully.", status_code=201)


@auth_bp.route("/register", methods=["POST"])
@roles_required("Admin")
def register_user():
    """Administrator-only user creation."""
    payload = request.get_json(silent=True) or {}
    user = AuthService.register_user(payload, requested_by_role="Admin")
    return api_response(data=user, message="User account registered successfully.", status_code=201)


@auth_bp.route("/users", methods=["GET"])
@roles_required("Admin")
def list_users():
    """Administrator-only list of all users."""
    role = request.args.get("role")
    limit = min(int(request.args.get("limit", 100)), 200)
    offset = int(request.args.get("offset", 0))
    users = AuthService.list_users(role=role, limit=limit, offset=offset)
    return api_response(data=users, message="Users retrieved successfully.")


@auth_bp.route("/users/<int:user_id>", methods=["GET"])
@roles_required("Admin")
def get_user(user_id: int):
    """Administrator-only retrieve user account by ID."""
    from app.repositories.user_repo import UserRepository
    from app.utils.exceptions import NotFoundError
    user = UserRepository.get_by_id(user_id)
    if not user:
        raise NotFoundError(f"User with ID {user_id} not found.")
    user_clean = {k: v for k, v in user.items() if k != "password_hash"}
    return api_response(data=user_clean, message="User account retrieved successfully.")


@auth_bp.route("/users/<int:user_id>", methods=["PUT", "PATCH"])
@roles_required("Admin")
def update_user(user_id: int):
    """Administrator-only update user account."""
    current_user = get_current_user()
    payload = request.get_json(silent=True) or {}
    updated = AuthService.update_user_account(user_id, payload, current_user=current_user)
    return api_response(data=updated, message="User account updated successfully.")


@auth_bp.route("/users/<int:user_id>", methods=["DELETE"])
@roles_required("Admin")
def delete_user(user_id: int):
    """Administrator-only delete user account."""
    current_user = get_current_user()
    AuthService.delete_user_account(user_id, current_user=current_user)
    return api_response(data={"deleted_id": user_id}, message="User account deleted successfully.")
