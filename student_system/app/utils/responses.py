"""
Standardized API response helper for Flask routes.
"""

from typing import Any, Optional
from flask import jsonify, Response


def api_response(
    data: Optional[Any] = None,
    message: str = "Success",
    status_code: int = 200,
    meta: Optional[dict] = None,
) -> tuple[Response, int]:
    """
    Construct a consistent, standardized JSON API response envelope.
    """
    payload = {
        "success": 200 <= status_code < 300,
        "message": message,
        "data": data,
    }
    if meta is not None:
        payload["meta"] = meta

    return jsonify(payload), status_code


def error_response(
    message: str,
    error_code: str = "ERROR",
    status_code: int = 400,
    details: Optional[Any] = None,
) -> tuple[Response, int]:
    """
    Construct a consistent, standardized error response envelope.
    """
    payload = {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
            "details": details or {},
        }
    }
    return jsonify(payload), status_code
