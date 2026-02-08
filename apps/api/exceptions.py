"""
Custom exception handling for the REST API.

Provides consistent error response format and audit logging for errors.
"""

import logging

from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides consistent error format.
    
    Response format:
    {
        "error": {
            "code": "error_code",
            "message": "Human-readable message",
            "details": {...}  # Optional additional details
        }
    }
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # Get request info for logging
    request = context.get("request")
    view = context.get("view")
    
    if response is not None:
        # Standardize the error format
        error_data = {
            "error": {
                "code": _get_error_code(exc),
                "message": _get_error_message(exc, response),
            }
        }
        
        # Add details if available
        if hasattr(exc, "detail") and isinstance(exc.detail, dict):
            error_data["error"]["details"] = exc.detail
        
        response.data = error_data
        
        # Log the error
        logger.warning(
            "API error: %s %s - %s (%s)",
            request.method if request else "?",
            request.path if request else "?",
            error_data["error"]["code"],
            error_data["error"]["message"],
        )
    else:
        # Handle Django exceptions not caught by DRF
        if isinstance(exc, Http404):
            error_data = {
                "error": {
                    "code": "not_found",
                    "message": "The requested resource was not found.",
                }
            }
            response = Response(error_data, status=status.HTTP_404_NOT_FOUND)
        elif isinstance(exc, PermissionDenied):
            error_data = {
                "error": {
                    "code": "permission_denied",
                    "message": "You do not have permission to perform this action.",
                }
            }
            response = Response(error_data, status=status.HTTP_403_FORBIDDEN)
        elif isinstance(exc, DjangoValidationError):
            error_data = {
                "error": {
                    "code": "validation_error",
                    "message": str(exc),
                }
            }
            response = Response(error_data, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Log unexpected exceptions
            logger.exception(
                "Unhandled API exception: %s %s",
                request.method if request else "?",
                request.path if request else "?",
            )
            error_data = {
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                }
            }
            response = Response(error_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return response


def _get_error_code(exc):
    """Get a machine-readable error code from the exception."""
    if hasattr(exc, "default_code"):
        return exc.default_code
    
    # Map exception types to codes
    code_map = {
        "AuthenticationFailed": "authentication_failed",
        "NotAuthenticated": "not_authenticated",
        "PermissionDenied": "permission_denied",
        "NotFound": "not_found",
        "MethodNotAllowed": "method_not_allowed",
        "Throttled": "rate_limit_exceeded",
        "ValidationError": "validation_error",
    }
    
    exc_name = exc.__class__.__name__
    return code_map.get(exc_name, "error")


def _get_error_message(exc, response):
    """Get a human-readable error message."""
    if hasattr(exc, "detail"):
        if isinstance(exc.detail, str):
            return exc.detail
        elif isinstance(exc.detail, list):
            return exc.detail[0] if exc.detail else "An error occurred."
        elif isinstance(exc.detail, dict):
            # Get first error message from dict
            for key, value in exc.detail.items():
                if isinstance(value, list) and value:
                    return f"{key}: {value[0]}"
                elif isinstance(value, str):
                    return f"{key}: {value}"
            return "Validation error."
    
    return "An error occurred."


class TenantMismatchError(APIException):
    """Raised when a resource doesn't belong to the user's tenant."""
    
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "This resource does not belong to your organization."
    default_code = "tenant_mismatch"


class InvalidStateTransitionError(APIException):
    """Raised when an invalid state transition is attempted."""
    
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This state transition is not allowed."
    default_code = "invalid_state_transition"

