import re
import uuid

from .request_context import set_request_id

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class RequestIdMiddleware:
    """Attach a request id to every request/response and expose it to logging."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        request.request_id = request_id
        set_request_id(request_id)
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response
