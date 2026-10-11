from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, ValidationError, MethodNotAllowed, NotAuthenticated, PermissionDenied
from django.http import Http404


class ContractAPIException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "VALIDATION_ERROR"
    default_detail = "Validation error."

    def __init__(self, message=None, code=None, details=None, status_code=None):
        if status_code is not None:
            self.status_code = status_code
        self.code = code or self.default_code
        self.message = str(message or self.default_detail)
        self.details = details if details is not None else []
        super().__init__(self.message, code=self.code)


class DuplicateError(ContractAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "DUPLICATE"
    default_detail = "Resource already exists."


class InsufficientStockError(ContractAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "INSUFFICIENT_STOCK"
    default_detail = "Insufficient stock available."


class InvalidTransitionError(ContractAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "INVALID_TRANSITION"
    default_detail = "Invalid status transition."


class OrderLockedError(ContractAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "ORDER_LOCKED"
    default_detail = "Order is locked and cannot be edited."


class IdempotencyConflictError(ContractAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "IDEMPOTENCY_CONFLICT"
    default_detail = "Idempotency key reused with different request payload."


class SupplierUnavailableError(ContractAPIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_code = "SUPPLIER_UNAVAILABLE"
    default_detail = "Supplier feed could not be fetched."


def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first to get the standard response.
    response = exception_handler(exc, context)

    # If it's our own ContractAPIException
    if isinstance(exc, ContractAPIException):
        return Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
            status=exc.status_code,
        )

    # Standard 404
    if isinstance(exc, (NotFound, Http404)):
        return Response(
            {
                "error": {
                    "code": "NOT_FOUND",
                    "message": str(exc) if str(exc) and str(exc) != "Not found." else "Resource not found.",
                    "details": [],
                }
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Database integrity error (unique constraint violation)
    from django.db import IntegrityError
    if isinstance(exc, IntegrityError):
        return Response(
            {
                "error": {
                    "code": "DUPLICATE",
                    "message": "Resource already exists.",
                    "details": [str(exc)],
                }
            },
            status=status.HTTP_409_CONFLICT,
        )

    # Standard DRF ValidationError
    if isinstance(exc, ValidationError):
        is_duplicate = False
        details = []

        def check_code(err):
            nonlocal is_duplicate
            code = getattr(err, "code", None)
            if code in ("DUPLICATE", "duplicate", "unique"):
                is_duplicate = True

        if isinstance(exc.detail, dict):
            for field, errs in exc.detail.items():
                if isinstance(errs, list):
                    for err in errs:
                        check_code(err)
                        details.append(f"{field}: {err}")
                else:
                    check_code(errs)
                    details.append(f"{field}: {errs}")
        elif isinstance(exc.detail, list):
            for err in exc.detail:
                check_code(err)
                details.append(str(err))
        else:
            check_code(exc.detail)
            details.append(str(exc.detail))

        msg = details[0] if details else "Validation error."
        if is_duplicate:
            return Response(
                {
                    "error": {
                        "code": "DUPLICATE",
                        "message": msg,
                        "details": details,
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": msg,
                    "details": details,
                }
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Any other DRF handled exception
    if response is not None:
        error_code = "VALIDATION_ERROR"
        if response.status_code == 404:
            error_code = "NOT_FOUND"
        elif response.status_code == 409:
            error_code = "CONFLICT"

        msg = "An error occurred."
        if isinstance(response.data, dict):
            if "detail" in response.data:
                msg = str(response.data["detail"])
            else:
                msg = "; ".join(f"{k}: {v}" for k, v in response.data.items())
        elif isinstance(response.data, list):
            msg = "; ".join(str(d) for d in response.data)

        return Response(
            {
                "error": {
                    "code": error_code,
                    "message": msg,
                    "details": [],
                }
            },
            status=response.status_code,
        )

    return response
