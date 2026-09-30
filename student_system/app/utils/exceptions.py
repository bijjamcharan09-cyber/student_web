"""
Custom application exceptions for Student Management System.
"""

class AppException(Exception):
    """Base application exception."""
    status_code = 500
    error_code = "INTERNAL_SERVER_ERROR"

    def __init__(self, message: str, details=None, status_code=None, error_code=None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code

    def to_dict(self):
        return {
            "success": False,
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
            }
        }


class ValidationError(AppException):
    """Raised when client input fails validation rules."""
    status_code = 400
    error_code = "VALIDATION_ERROR"


class BadRequestError(AppException):
    """Raised for malformed requests or unprocessable syntax."""
    status_code = 400
    error_code = "BAD_REQUEST"


class NotFoundError(AppException):
    """Raised when a requested resource is not found."""
    status_code = 404
    error_code = "NOT_FOUND"


class ConflictError(AppException):
    """Raised when a resource state violates a unique constraint or conflict."""
    status_code = 409
    error_code = "RESOURCE_CONFLICT"


class DatabaseError(AppException):
    """Raised when an underlying database query or transaction fails."""
    status_code = 500
    error_code = "DATABASE_ERROR"
