"""Unified API error format.

Every error response looks like::

    {
      "error": {
        "code": "validation_error",
        "message": "Проверьте введённые данные.",
        "details": {"email": ["Введите корректный адрес."]},
        "request_id": "..."
      }
    }

``message`` is always safe to show to a child; technical detail goes to ``details``.
"""

from __future__ import annotations

import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .request_context import get_request_id

logger = logging.getLogger("umnydrug.api")


class DomainError(exceptions.APIException):
    """Business-rule violation with a stable machine-readable code."""

    status_code = status.HTTP_409_CONFLICT
    default_code = "domain_error"
    default_detail = "Операция невозможна."

    def __init__(
        self, message: str | None = None, *, code: str | None = None, status_code: int | None = None
    ):
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail=message or self.default_detail, code=code or self.default_code)


_CODE_BY_STATUS = {
    400: "validation_error",
    401: "not_authenticated",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    423: "locked",
    429: "throttled",
}

_MESSAGE_BY_CODE = {
    "validation_error": "Проверьте введённые данные.",
    "not_authenticated": "Нужно войти в аккаунт.",
    "permission_denied": "Нет доступа к этому ресурсу.",
    "not_found": "Не найдено.",
    "method_not_allowed": "Метод не поддерживается.",
    "payload_too_large": "Файл слишком большой.",
    "unsupported_media_type": "Такой формат не поддерживается.",
    "throttled": "Слишком много запросов. Попробуй чуть позже.",
}

# Statuses whose DRF detail is technical and must not replace the friendly message.
_KEEP_FRIENDLY_MESSAGE = {401, 403, 404, 405, 413, 415, 429}


def _error_payload(code: str, message: str, details=None, extra=None) -> dict:
    error = {"code": code, "message": message, "request_id": get_request_id()}
    if details:
        error["details"] = details
    if extra:
        error.update(extra)
    return {"error": error}


def api_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(
            detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        )
    elif isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API exception", extra={"event": "api.unhandled"})
        return Response(
            _error_payload("server_error", "Что-то пошло не так. Мы уже разбираемся."),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    status_code = response.status_code
    code = _CODE_BY_STATUS.get(status_code, "error")
    message = _MESSAGE_BY_CODE.get(code, "Ошибка запроса.")
    details = None
    extra = None

    if isinstance(exc, exceptions.ValidationError):
        details = exc.detail if isinstance(exc.detail, dict) else {"non_field_errors": exc.detail}
    elif isinstance(exc, DomainError):
        codes = exc.get_codes()
        code = codes if isinstance(codes, str) else code
        message = str(exc.detail)
    elif isinstance(exc, exceptions.Throttled):
        extra = {"retry_after": exc.wait}
    elif isinstance(exc, exceptions.APIException):
        detail = exc.detail
        if isinstance(detail, dict | list):
            details = detail
        elif status_code not in _KEEP_FRIENDLY_MESSAGE:
            message = str(detail)

    response.data = _error_payload(code, message, details, extra)
    return response
