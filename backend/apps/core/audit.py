from __future__ import annotations

from typing import Any

from .models import AuditLog
from .network import client_ip
from .request_context import get_request_id

__all__ = ("audit", "client_ip")


def audit(action: str, *, actor=None, target: Any = None, request=None, **metadata: Any) -> AuditLog:
    """Write an audit entry. Metadata must not contain personal data or secrets."""
    target_type = ""
    target_id = ""
    if target is not None:
        target_type = type(target).__name__
        target_id = str(getattr(target, "pk", ""))
    if actor is None and request is not None and getattr(request, "user", None) is not None:
        actor = request.user if request.user.is_authenticated else None
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        ip_address=client_ip(request),
        request_id=get_request_id() or "",
        metadata=metadata,
    )
