"""
Application Factory for Student Management System.
"""

from flask import Flask, jsonify, request, render_template
from config import config_by_name
from app.utils.exceptions import AppException
from app.utils.responses import error_response, api_response
from app.api import (
    students_bp,
    subjects_bp,
    semesters_bp,
    marks_bp,
    attendance_bp,
    reports_bp,
)


def create_app(config_name: str = "development") -> Flask:
    """Create and configure the Flask application instance."""
    app = Flask(__name__)
    config_class = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(config_class)

    # Register Blueprints
    app.register_blueprint(students_bp)
    app.register_blueprint(subjects_bp)
    app.register_blueprint(semesters_bp)
    app.register_blueprint(marks_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(reports_bp)

    # Health & System Status Endpoints
    @app.route("/", methods=["GET"])
    def root():
        # If requested by a web browser, render the interactive Web Dashboard!
        best = request.accept_mimetypes.best_match(["text/html", "application/json"])
        if best == "text/html" and request.accept_mimetypes[best] > request.accept_mimetypes["application/json"]:
            return render_template("dashboard.html")

        return api_response(
            data={
                "name": "Student Management System API",
                "version": "1.0.0",
                "status": "operational",
                "dashboard": "/dashboard",
                "endpoints": {
                    "students": "/api/v1/students",
                    "subjects": "/api/v1/subjects",
                    "semesters": "/api/v1/semesters",
                    "marks": "/api/v1/marks",
                    "attendance": "/api/v1/attendance",
                    "reports": "/api/v1/reports",
                },
            },
            message="Welcome to Student Management System API",
        )

    @app.route("/dashboard", methods=["GET"])
    def dashboard():
        """Render visual HTML/CSS/JS dashboard."""
        return render_template("dashboard.html")

    @app.route("/health", methods=["GET"])
    def health_check():
        return api_response(
            data={"status": "healthy", "service": "student-management-api"},
            message="Service is healthy",
        )

    # Global Error Handlers
    @app.errorhandler(AppException)
    def handle_app_exception(error: AppException):
        return error_response(
            message=error.message,
            error_code=error.error_code,
            status_code=error.status_code,
            details=error.details,
        )

    @app.errorhandler(400)
    def handle_bad_request(error):
        return error_response(
            message="Bad request or invalid JSON payload.",
            error_code="BAD_REQUEST",
            status_code=400,
        )

    @app.errorhandler(404)
    def handle_not_found(error):
        return error_response(
            message=f"The requested endpoint '{request.path}' was not found.",
            error_code="ENDPOINT_NOT_FOUND",
            status_code=404,
        )

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        return error_response(
            message=f"Method '{request.method}' not allowed on endpoint '{request.path}'.",
            error_code="METHOD_NOT_ALLOWED",
            status_code=405,
        )

    @app.errorhandler(500)
    def handle_internal_error(error):
        return error_response(
            message="An unexpected internal server error occurred.",
            error_code="INTERNAL_SERVER_ERROR",
            status_code=500,
        )

    return app
