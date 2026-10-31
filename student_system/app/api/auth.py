"""
Authentication API Blueprint for login, logout, profile checks, and multi-organisation account management.
"""

from flask import Blueprint, g, request, session
from app.services.auth_service import AuthService
from app.repositories.organisation_repo import OrganisationRepository
from app.utils.auth import (
    can_select_organisation,
    get_current_user,
    get_effective_organisation_id,
    is_safe_url,
    login_required,
    revoke_token,
    roles_required,
)
from app.utils.exceptions import ForbiddenError, NotFoundError
from app.utils.responses import api_response

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate with username/password and return session cookie + bearer token."""
    payload = request.get_json(silent=True) or {}
    username = payload.get("username", "").strip()
    password = payload.get("password", "").strip()
    next_url = payload.get("next") or request.args.get("next")

    result = AuthService.authenticate(username, password)
    user = result["user"]
    token = result["token"]

    # Set server-side session
    session["user_id"] = user["id"]
    session["role"] = user["role"]
    session["organisation_id"] = user.get("organisation_id", 1)

    redirect_url = next_url if is_safe_url(next_url) else "/dashboard"

    return api_response(
        data={"user": user, "token": token, "redirect_url": redirect_url},
        message=f"Welcome {user['username']}! Logged in successfully.",
    )


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Clear server-side session and revoke the current bearer token."""
    # Revoke bearer token if present
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        revoke_token(auth_header[7:].strip())
    x_token = request.headers.get("X-Auth-Token", "").strip()
    if x_token:
        revoke_token(x_token)

    session.clear()
    g.current_user = None
    return api_response(message="Logged out successfully.")


@auth_bp.route("/me", methods=["GET"])
@login_required
def get_current_profile():
    """Get the currently authenticated user profile, roles, and organisation selection context."""
    user = get_current_user()
    user_clean = {k: v for k, v in user.items() if k != "password_hash"}
    is_super = can_select_organisation(user)
    user_clean["can_select_organisation"] = is_super

    if is_super:
        sel_id = session.get("selected_organisation_id")
        user_clean["selected_organisation_id"] = int(sel_id) if sel_id and str(sel_id).isdigit() else None
        user_clean["is_global_organisation"] = user_clean["selected_organisation_id"] is None
        user_clean["selected_organisation"] = (
            OrganisationRepository.get_by_id(user_clean["selected_organisation_id"])
            if user_clean["selected_organisation_id"]
            else None
        )
    else:
        org_id = int(user.get("organisation_id") or 1)
        user_clean["selected_organisation_id"] = org_id
        user_clean["is_global_organisation"] = False
        user_clean["selected_organisation"] = OrganisationRepository.get_by_id(org_id)

    return api_response(data=user_clean, message="Authenticated profile retrieved successfully.")


@auth_bp.route("/signup", methods=["POST"])
def public_student_signup():
    """Public self-registration endpoint for Students only."""
    payload = request.get_json(silent=True) or request.form.to_dict() or {}
    user = AuthService.register_student_public(payload)
    return api_response(data=user, message="Student account registered successfully.", status_code=201)


@auth_bp.route("/register", methods=["POST"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def register_user():
    """Administrator and Organisation-level user creation."""
    current_user = get_current_user()
    payload = request.get_json(silent=True) or {}
    user = AuthService.register_user(
        payload,
        requested_by_role=current_user["role"],
        requested_by_user=current_user,
    )
    return api_response(data=user, message="User account registered successfully.", status_code=201)


@auth_bp.route("/users", methods=["GET"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def list_users():
    """List users scoped to caller's organisation (or all for Super Admin)."""
    current_user = get_current_user()
    org_id = get_effective_organisation_id()
    role = request.args.get("role")
    limit = min(int(request.args.get("limit", 100)), 200)
    offset = int(request.args.get("offset", 0))

    users = AuthService.list_users(role=role, organisation_id=org_id, limit=limit, offset=offset)
    return api_response(data=users, message="Users retrieved successfully.")


@auth_bp.route("/users/<int:user_id>", methods=["GET"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def get_user(user_id: int):
    """Retrieve user account by ID with organisation boundary verification."""
    from app.repositories.user_repo import UserRepository
    current_user = get_current_user()
    user = UserRepository.get_by_id(user_id)
    if not user:
        raise NotFoundError(f"User with ID {user_id} not found.")

    # Organisation users cannot view other organisations' users
    current_role = str(current_user.get("role") or "").strip().title()
    if current_role in ("Organisation", "Organization"):
        if int(user["organisation_id"]) != int(current_user["organisation_id"]):
            raise ForbiddenError("Access denied: You cannot view users belonging to another organisation.")

    user_clean = {k: v for k, v in user.items() if k != "password_hash"}
    return api_response(data=user_clean, message="User account retrieved successfully.")


@auth_bp.route("/users/<int:user_id>", methods=["PUT", "PATCH"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def update_user(user_id: int):
    """Update user account with organisation checks."""
    current_user = get_current_user()
    payload = request.get_json(silent=True) or {}
    updated = AuthService.update_user_account(user_id, payload, current_user=current_user)
    return api_response(data=updated, message="User account updated successfully.")


@auth_bp.route("/users/<int:user_id>", methods=["DELETE"])
@login_required
@roles_required("Admin", "Super Admin", "Organisation")
def delete_user(user_id: int):
    """Delete user account with organisation checks."""
    current_user = get_current_user()
    AuthService.delete_user_account(user_id, current_user=current_user)
    return api_response(data={"deleted_id": user_id}, message="User account deleted successfully.")
