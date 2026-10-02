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
def signup():
    """Public user registration open to everyone. Creates account and immediately logs user in."""
    payload = request.get_json(silent=True) or {}
    result = AuthService.public_register(payload)
    user = result["user"]
    token = result["token"]

    # Automatically establish session
    session["user_id"] = user["id"]
    session["role"] = user["role"]

    return api_response(
        data={"user": user, "token": token},
        message=f"Account registered successfully! Welcome {user['username']}.",
        status_code=201,
    )


@auth_bp.route("/register", methods=["POST"])
@roles_required("Admin")
def register_user():
    """Administrator-only user creation."""
    payload = request.get_json(silent=True) or {}
    user = AuthService.register_user(payload, requested_by_role="Admin")
    return api_response(data=user, message="User account registered successfully.", status_code=201)
