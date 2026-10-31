"""
Organisations API blueprint for Super Admin / Admin management and organisation profile.
"""

from flask import Blueprint, request, session
from app.repositories.organisation_repo import OrganisationRepository
from app.utils.auth import (
    can_select_organisation,
    check_organisation_scope,
    get_current_user,
    login_required,
    roles_required,
)
from app.utils.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.utils.responses import api_response

organisations_bp = Blueprint("organisations", __name__, url_prefix="/api/v1/organisations")


@organisations_bp.route("/select", methods=["POST"])
@login_required
@roles_required("Admin", "Super Admin")
def select_organisation():
    """
    RBAC: Only Super Administrators can select or switch active organisation context.
    Pass organisation_id (integer) to switch context to that organisation.
    Pass null, 0, or 'all' to switch back to global (all organisations) context.
    """
    user = get_current_user()
    if not can_select_organisation(user):
        raise ForbiddenError("Access denied: Only Super Administrators can select or switch organisations.")

    payload = request.get_json(silent=True) or {}
    raw_target = payload.get("organisation_id")

    if raw_target is None or raw_target == "" or str(raw_target).strip().lower() in ("0", "none", "null", "all"):
        session.pop("selected_organisation_id", None)
        return api_response(
            data={"selected_organisation_id": None, "organisation": None, "is_global": True},
            message="Switched to Global / All Organisations context.",
        )

    try:
        org_id = int(raw_target)
    except (ValueError, TypeError):
        raise ValidationError("Invalid organisation_id. Must be an integer or null.")

    org = OrganisationRepository.get_by_id(org_id)
    if not org:
        raise NotFoundError(f"Organisation with ID {org_id} does not exist.")

    session["selected_organisation_id"] = org_id
    return api_response(
        data={"selected_organisation_id": org_id, "organisation": org, "is_global": False},
        message=f"Active organisation context set to '{org['name']}'.",
    )


@organisations_bp.route("/active", methods=["GET"])
@login_required
def get_active_organisation_context():
    """
    Get the currently active organisation context for the authenticated user.
    """
    user = get_current_user()
    if can_select_organisation(user):
        selected_id = session.get("selected_organisation_id")
        if selected_id and str(selected_id).isdigit():
            org = OrganisationRepository.get_by_id(int(selected_id))
            if org:
                return api_response(
                    data={
                        "selected_organisation_id": int(selected_id),
                        "is_global": False,
                        "organisation": org,
                        "can_select_organisation": True,
                    },
                    message="Active organisation context retrieved.",
                )
        return api_response(
            data={
                "selected_organisation_id": None,
                "is_global": True,
                "organisation": None,
                "can_select_organisation": True,
            },
            message="Global organisation context active (All organisations).",
        )

    user_org_id = int(user.get("organisation_id") or 1)
    org = OrganisationRepository.get_by_id(user_org_id)
    return api_response(
        data={
            "selected_organisation_id": user_org_id,
            "is_global": False,
            "organisation": org,
            "can_select_organisation": False,
        },
        message="User fixed organisation context retrieved.",
    )


@organisations_bp.route("", methods=["GET"])
@login_required
@roles_required("Admin", "Super Admin")
def list_organisations():
    """List all registered organisations (Super Admin / Admin only)."""
    status = request.args.get("status")
    orgs = OrganisationRepository.list_all(status=status)
    return api_response(data=orgs, message="Organisations retrieved successfully.")


@organisations_bp.route("", methods=["POST"])
@login_required
@roles_required("Admin", "Super Admin")
def create_organisation():
    """Create a new organisation (Super Admin / Admin only)."""
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    code = str(payload.get("code", "")).strip().upper()
    status = str(payload.get("status", "Active")).strip().capitalize()

    if not name or not code:
        raise ValidationError("Organisation 'name' and unique 'code' are required.")

    if OrganisationRepository.get_by_code(code):
        raise ConflictError(f"An organisation with code '{code}' already exists.")

    org_id = OrganisationRepository.create({
        "name": name,
        "code": code,
        "status": status,
    })
    created = OrganisationRepository.get_by_id(org_id)
    return api_response(data=created, message="Organisation created successfully.", status_code=201)


@organisations_bp.route("/me", methods=["GET"])
@login_required
def get_own_organisation():
    """Get organisation details for the authenticated user's organisation."""
    user = get_current_user()
    org_id = user.get("organisation_id", 1)
    org = OrganisationRepository.get_by_id(org_id)
    if not org:
        raise NotFoundError("Organisation record not found.")
    return api_response(data=org, message="Organisation profile retrieved successfully.")


@organisations_bp.route("/<int:org_id>", methods=["GET"])
@login_required
def get_organisation(org_id: int):
    """Retrieve organisation details. Super Admin has global access; Organisation user can only view their own."""
    check_organisation_scope(org_id)
    org = OrganisationRepository.get_by_id(org_id)
    if not org:
        raise NotFoundError(f"Organisation with ID {org_id} not found.")
    return api_response(data=org, message="Organisation retrieved successfully.")


@organisations_bp.route("/<int:org_id>", methods=["PUT", "PATCH"])
@login_required
@roles_required("Admin", "Super Admin")
def update_organisation(org_id: int):
    """Update organisation details (Super Admin / Admin only)."""
    existing = OrganisationRepository.get_by_id(org_id)
    if not existing:
        raise NotFoundError(f"Organisation with ID {org_id} not found.")

    payload = request.get_json(silent=True) or {}
    if "code" in payload and payload["code"]:
        new_code = str(payload["code"]).strip().upper()
        if new_code != existing["code"]:
            other = OrganisationRepository.get_by_code(new_code)
            if other and other["id"] != org_id:
                raise ConflictError(f"Organisation code '{new_code}' is already assigned.")
            payload["code"] = new_code

    OrganisationRepository.update(org_id, payload)
    updated = OrganisationRepository.get_by_id(org_id)
    return api_response(data=updated, message="Organisation updated successfully.")


@organisations_bp.route("/<int:org_id>", methods=["DELETE"])
@login_required
@roles_required("Admin", "Super Admin")
def delete_organisation(org_id: int):
    """Delete or deactivate an organisation (Super Admin / Admin only)."""
    from app import db
    from app.utils.exceptions import ConflictError

    if org_id == 1:
        raise ForbiddenError("Cannot delete default primary organisation.")

    existing = OrganisationRepository.get_by_id(org_id)
    if not existing:
        raise NotFoundError(f"Organisation with ID {org_id} not found.")

    # Check for orphaned records before deletion
    counts = {}
    for table, label in [
        ("students", "student(s)"),
        ("users", "user(s)"),
        ("faculty", "faculty member(s)"),
        ("subjects", "subject(s)"),
        ("semesters", "semester(s)"),
    ]:
        row = db.query_one(f"SELECT COUNT(*) as c FROM `{table}` WHERE organisation_id = %s", (org_id,))
        c = row["c"] if row else 0
        if c > 0:
            counts[label] = c

    if counts:
        detail_str = ", ".join(f"{c} {lbl}" for lbl, c in counts.items())
        raise ConflictError(
            f"Cannot delete organisation: Contains associated records ({detail_str}). "
            f"Please deactivate the organisation instead."
        )

    OrganisationRepository.delete(org_id)
    return api_response(data={"deleted_id": org_id}, message="Organisation deleted successfully.")
